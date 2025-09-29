# backend_api.py
import os
import re
import sqlite3
import faiss
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS

# Optional imports that may fail in some environments
try:
    import google.generativeai as genai
except Exception:
    genai = None

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None

# --- CONFIGURATION ---
# Read the API key from an environment variable named GEMINI_API_KEY
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

FAISS_INDEX_FILE = "faiss_index.bin"
METADATA_MAP_FILE = "metadata_map.npy"
DB_FILE = "argo_data.db"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# --- FLASK APP ---
app = Flask(__name__)
CORS(app)

# --- GLOBALS TO LOAD ON STARTUP ---
faiss_index = None
metadata_map = {}
embedding_model = None
model = None

# --- Try to load FAISS + metadata map (optional) ---
try:
    faiss_index = faiss.read_index(FAISS_INDEX_FILE)
    metadata_map = np.load(METADATA_MAP_FILE, allow_pickle=True).item()
    print("FAISS index and metadata map loaded successfully.")
except Exception as e:
    print(f"Warning: Could not load FAISS index or metadata map: {e}")

# --- Try to load SentenceTransformer (optional) ---
if SentenceTransformer:
    try:
        embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        print("SentenceTransformer loaded.")
    except Exception as e:
        print(f"Warning: Could not load embedding model: {e}")
else:
    print("sentence-transformers library not available; RAG disabled.")

# --- Database connection (single connection, check_same_thread=False for Flask dev) ---
try:
    db_connection = sqlite3.connect(DB_FILE, check_same_thread=False)
    print("Connected to SQLite database.")
except Exception as e:
    db_connection = None
    print(f"Warning: Could not connect to SQLite DB: {e}")

# --- Configure Gemini LLM if available and key present ---
if genai and GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        print("Gemini model configured successfully.")
    except Exception as e:
        print(f"Warning initializing Gemini model: {e}")
        model = None
else:
    if not genai:
        print("google.generativeai library not available; LLM disabled.")
    if not GEMINI_API_KEY:
        print("Warning: GEMINI_API_KEY not set. LLM will be disabled.")
    model = None

# --------------------------
# Helper: fallback NL->SQL generator (simple heuristics)
# --------------------------
def fallback_nl_to_sql(query: str):
    q = query.lower()
    # pick columns to select
    cols = []
    for col in ["temperature", "salinity", "pressure", "date", "latitude", "longitude", "cycle_number", "profile_id", "float_id"]:
        if re.search(rf"\b{col}\b", q):
            cols.append(col)
    if not cols:
        cols = ["float_id", "date", "pressure", "temperature", "salinity"]
    select_clause = ", ".join(cols)

    where_clauses = []
    # float id
    m = re.search(r"(?:float\s*(?:id)?\s*[:#]?\s*|float\s*)(\d{1,10})\b", q)
    if m:
        where_clauses.append(f"float_id = {m.group(1)}")

    # equator shortcut
    if "equator" in q:
        where_clauses.append("latitude BETWEEN -1 AND 1")

    # latitude / longitude range pattern
    m = re.search(r"latitude\s+between\s+(-?\d+\.?\d*)\s+and\s+(-?\d+\.?\d*)", q)
    if m:
        where_clauses.append(f"latitude BETWEEN {m.group(1)} AND {m.group(2)}")
    m = re.search(r"longitude\s+between\s+(-?\d+\.?\d*)\s+and\s+(-?\d+\.?\d*)", q)
    if m:
        where_clauses.append(f"longitude BETWEEN {m.group(1)} AND {m.group(2)}")

    # date range
    m = re.search(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2}).*(?:to|and|through).*(\d{4}[-/]\d{1,2}[-/]\d{1,2})", q)
    if m:
        where_clauses.append(f"date BETWEEN '{m.group(1)}' AND '{m.group(2)}'")

    # aggregation: avg/min/max/count <col>
    agg = None
    m = re.search(r"\b(avg|average|mean|max|min|count)\b\s+of\s+(\w+)", q)
    if m:
        op = m.group(1)
        col = m.group(2)
        if op in ("avg", "average", "mean"):
            agg = f"AVG({col}) as avg_{col}"
        elif op == "max":
            agg = f"MAX({col}) as max_{col}"
        elif op == "min":
            agg = f"MIN({col}) as min_{col}"
        elif op == "count":
            agg = f"COUNT({col}) as count_{col}"

    # limit
    m = re.search(r"\blimit\s+(\d{1,4})\b", q)
    limit_clause = f" LIMIT {m.group(1)}" if m else " LIMIT 200"

    base_from = "argo_profiles JOIN argo_metadata USING(float_id)"
    if agg:
        sql = f"SELECT {agg} FROM {base_from}"
    else:
        sql = f"SELECT {select_clause} FROM {base_from}"

    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)

    sql += ";"
    return sql

# --------------------------
# RAG retrieval (optional)
# --------------------------
def retrieve_relevant_floats(query_text, k=5):
    if faiss_index is None or embedding_model is None or not metadata_map:
        return []
    emb = embedding_model.encode(query_text, convert_to_tensor=False)
    emb = np.expand_dims(emb, axis=0).astype("float32")
    distances, indices = faiss_index.search(emb, k)
    relevant = []
    for idx in indices[0]:
        relevant.append(metadata_map.get(idx, {}))
    return relevant

# --------------------------
# Natural language to SQL (LLM first, fallback to heuristics)
# --------------------------
def natural_language_to_sql(query, context):
    db_schema = """
    Table: argo_profiles (profile_id, float_id, cycle_number, latitude, longitude, date, pressure, temperature, salinity)
    Table: argo_metadata (float_id, platform_type, country, deployment_date)
    """
    prompt = f"""
You are a professional SQL generator for SQLite. Use the schema below and the context to create a single SELECT statement.
Schema:
{db_schema}
Context:
{context}
User question:
\"\"\"{query}\"\"\"
Only output a single SELECT statement (no explanation).
"""

    if model:
        try:
            resp = model.generate_content(prompt)
            generated = resp.text.strip()
            print("LLM raw response:", generated)
            for t in ["```sql", "```", "`"]:
                generated = generated.replace(t, "")
            generated = generated.strip().rstrip(";")
            if generated.lower().startswith("select"):
                return generated + ";"
            else:
                print("LLM returned text that does not start with SELECT; using fallback.")
        except Exception as e:
            print(f"LLM error when generating SQL: {e}")

    # fallback
    fallback_sql = fallback_nl_to_sql(query)
    print("Using fallback SQL:", fallback_sql)
    return fallback_sql

# --------------------------
# Execute SQL and summarize
# --------------------------
def execute_and_synthesize_response(sql_query, user_query):
    if not db_connection:
        return {"summary": "Server DB not available.", "data": []}
    if not sql_query:
        return {"summary": "Sorry, could not create a valid SQL query.", "data": []}

    # safety: disallow non-SELECT
    if not sql_query.strip().lower().startswith("select"):
        return {"summary": "Only SELECT queries are allowed.", "data": []}

    try:
        if "limit" not in sql_query.lower():
            sql_query = sql_query.rstrip(";") + " LIMIT 500;"
        cursor = db_connection.cursor()
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        col_names = [desc[0] for desc in cursor.description] if cursor.description else []
        rows_as_dicts = [dict(zip(col_names, row)) for row in rows]

        results_str = str(rows_as_dicts)
        if len(results_str) > 2000:
            results_str = results_str[:2000] + "..."

        if model:
            try:
                prompt = f"The user asked: \"{user_query}\"\nThe SQL query returned the following rows:\n{results_str}\nPlease summarize briefly."
                resp = model.generate_content(prompt)
                summary_text = resp.text.strip()
            except Exception as e:
                print(f"LLM summarization error: {e}")
                summary_text = f"Returned {len(rows_as_dicts)} rows (LLM summary failed)."
        else:
            summary_text = f"Returned {len(rows_as_dicts)} rows. (No LLM configured.)"

        return {"summary": summary_text, "data": rows_as_dicts}
    except sqlite3.OperationalError as e:
        print(f"SQLite OperationalError: {e}")
        return {"summary": "Database error (invalid SQL or schema mismatch).", "data": []}
    except Exception as e:
        print(f"Unexpected error executing SQL: {e}")
        return {"summary": f"Unexpected error: {e}", "data": []}

# --------------------------
# High-level handler and routes
# --------------------------
def handle_query(user_query):
    relevant = retrieve_relevant_floats(user_query, k=3)
    context = "\n".join([f"Float ID: {r.get('float_id','')}, Summary: {r.get('summary','')}" for r in relevant])
    sql_query = natural_language_to_sql(user_query, context)
    if not sql_query:
        return {"summary": "I couldn't generate a valid SQL query from your question. Try rephrasing.", "data": []}
    return execute_and_synthesize_response(sql_query, user_query)

@app.route("/api/query", methods=["POST"])
def process_query():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"summary": "Invalid request payload (expected JSON object).", "data": []}), 400
    user_query = payload.get("query")
    if not user_query or not isinstance(user_query, str):
        return jsonify({"summary": "No query provided or query not a string.", "data": []}), 400
    resp = handle_query(user_query)
    return jsonify(resp)

# Test route to verify frontend without DB/LLM
@app.route("/api/test", methods=["GET"])
def api_test():
    sample = [
        {"float_id": 123, "date": "2002-03-05", "pressure": 10.0, "temperature": 24.5, "salinity": 35.1},
        {"float_id": 123, "date": "2002-03-06", "pressure": 50.0, "temperature": 20.9, "salinity": 34.8},
        {"float_id": 123, "date": "2002-03-07", "pressure": 100.0, "temperature": 15.4, "salinity": 34.6},
    ]
    return jsonify({"summary": "This is a test response with sample float data.", "data": sample})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
