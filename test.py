import os
import re
import sqlite3
import faiss
import numpy as np
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import json
import qrcode
from io import BytesIO
import base64
from urllib.parse import quote_plus
import uuid 
import math 
import geopy.distance

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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FAISS_INDEX_FILE = "faiss_index.bin"
METADATA_MAP_FILE = "metadata_map.npy"
DB_FILE = "argo_data.db"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
HISTORY_STORE_FILE = "history_store.json" # File for storing long chat histories

# --- FLASK APP ---
app = Flask(__name__)
CORS(app)

# --- GLOBALS TO LOAD ON STARTUP ---
faiss_index = None
metadata_map = {}
embedding_model = None
model = None
history_store = {} # In-memory cache for chat histories

# --- Helper to load and save history store (for persistent ID lookup) ---
def load_history_store():
    global history_store
    if os.path.exists(HISTORY_STORE_FILE):
        try:
            with open(HISTORY_STORE_FILE, 'r') as f:
                history_store = json.load(f)
            print(f"Loaded {len(history_store)} histories from {HISTORY_STORE_FILE}.")
        except json.JSONDecodeError as e:
            # FIX: If the file is corrupted (JSONDecodeError), delete it and start fresh.
            print(f"ERROR: Corrupt history store detected at {HISTORY_STORE_FILE}. Deleting file.")
            os.remove(HISTORY_STORE_FILE)
            history_store = {}
        except Exception as e:
            print(f"Warning: Could not load history store: {e}")
            history_store = {}
    else:
         print(f"History store file not found. Starting new store.")

def save_history_store():
    global history_store
    try:
        with open(HISTORY_STORE_FILE, 'w') as f:
            json.dump(history_store, f, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving history store: {e}")

# Load store on startup
load_history_store()
# --------------------------

# --- Try to load FAISS + metadata map (optional) ---
try:
    if os.path.exists(FAISS_INDEX_FILE) and os.path.exists(METADATA_MAP_FILE):
        faiss_index = faiss.read_index(FAISS_INDEX_FILE)
        metadata_map = np.load(METADATA_MAP_FILE, allow_pickle=True).item()
        print("FAISS index and metadata map loaded successfully.")
    else:
        print("FAISS index or metadata map files not found. RAG will be disabled.")
except Exception as e:
    print(f"Warning: Could not load FAISS index or metadata map: {e}")
    faiss_index = None
    metadata_map = {}

# --- Try to load SentenceTransformer ---
if SentenceTransformer:
    try:
        embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        print("SentenceTransformer loaded.")
    except Exception as e:
        print(f"Warning: Could not load embedding model: {e}")
        embedding_model = None
else:
    print("sentence-transformers library not available; RAG disabled.")

# --- Database connection (single connection, check_same_thread=False for Flask dev) ---
try:
    db_connection = sqlite3.connect(DB_FILE, check_same_thread=False)
    print("Connected to SQLite database.")
except Exception as e:
    db_connection = None
    print(f"Warning: Could not connect to SQLite DB: {e}")

# --- Configure Gemini LLM if available and key present (USING GEMINI 2.5 FLASH) ---
if genai and GEMINI_API_KEY:
    try:
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash") # Gemini 2.5 Flash
        print("Gemini 2.5 Flash model configured successfully.")
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
# Helper: fallback NL->SQL generator 
# --------------------------
def fallback_nl_to_sql(query: str):
    q = query.lower()
    cols = []
    
    is_location_query = "latitude" in q or "longitude" in q or "location" in q or "float id" in q
    
    if is_location_query:
        cols = ["float_id", "date", "latitude", "longitude", "pressure", "temperature", "salinity"]
    else:
        for col in ["temperature", "salinity", "pressure", "date", "latitude", "longitude", "cycle_number", "profile_id", "float_id"]:
            if re.search(rf"\b{col}\b", q):
                cols.append(col)
        if not cols:
            cols = ["float_id", "date", "pressure", "temperature", "salinity", "latitude", "longitude"]
            
    select_clause = ", ".join(sorted(list(set(cols))))

    where_clauses = []
    
    lat_m = re.search(r"(?:lat|latitude)\s*[:=]?\s*(-?\d+\.?\d*)", q)
    lon_m = re.search(r"(?:lon|longitude)\s*[:=]?\s*(-?\d+\.?\d*)", q)

    if lat_m and lon_m:
        lat = float(lat_m.group(1))
        lon = float(lon_m.group(1))
        tolerance = 0.5
        where_clauses.append(f"latitude BETWEEN {lat - tolerance} AND {lat + tolerance}")
        where_clauses.append(f"longitude BETWEEN {lon - tolerance} AND {lon + tolerance}")

    m_float_id = re.search(r"(?:float\s*(?:id)?\s*[:#]?\s*|float\s*)\s*(\d{1,10})\b", q)
    if m_float_id:
        where_clauses.append(f"float_id = {m_float_id.group(1)}")
    
    if "equator" in q:
        where_clauses.append("latitude BETWEEN -1 AND 1")
    m = re.search(r"latitude\s+between\s+(-?\d+\.?\d*)\s+and\s+(-?\d+\.?\d*)", q)
    if m:
        where_clauses.append(f"latitude BETWEEN {m.group(1)} AND {m.group(2)}")
    m = re.search(r"longitude\s+between\s+(-?\d+\.?\d*)\s+and\s+(-?\d+\.?\d*)", q)
    if m:
        where_clauses.append(f"longitude BETWEEN {m.group(1)} AND {m.group(2)}")
    m = re.search(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2}).(?:to|and|through).(\d{4}[-/]\d{1,2}[-/]\d{1,2})", q)
    if m:
        where_clauses.append(f"date BETWEEN '{m.group(1)}' AND '{m.group(2)}'")
    
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
            
    m = re.search(r"\blimit\s+(\d{1,4})\b", q)
    limit_clause = f" LIMIT {m.group(1)}" if m else " LIMIT 100"
    base_from = "argo_profiles JOIN argo_metadata USING(float_id)"
    
    order_clause = ""
    
    if m_float_id and not agg and is_location_query:
        order_clause = " ORDER BY date DESC"
        limit_clause = " LIMIT 1" 
    
    if agg:
        sql = f"SELECT {agg} FROM {base_from}"
    else:
        sql = f"SELECT {select_clause} FROM {base_from}"
        
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    
    if lat_m and lon_m:
         sql += f" ORDER BY (latitude - {lat})*(latitude - {lat}) + (longitude - {lon})*(longitude - {lon})"
         
    sql += order_clause + limit_clause + ";"
    return sql
# --------------------------

# --------------------------
# RAG retrieval (DISABLED for performance and stability)
# --------------------------
def retrieve_relevant_floats(query_text, k=3):
    return [] 
    
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
IMPORTANT:
- The column float_id is stored as text in the format b'123456 ' (with b'' prefix and a trailing space).
- Always generate WHERE float_id = "b'<number> '"
- Example: SELECT * FROM argo_profiles WHERE float_id = "b'1900121 '";
"""

    generated = None
    if model:
        try:
            resp = model.generate_content(prompt)
            generated = resp.text.strip()
            print("LLM raw response:", generated)
            for t in ["```sql", "```", "`"]:
                generated = generated.replace(t, "")
            generated = generated.strip().rstrip(";")
        except Exception as e:
            print(f"LLM API error during SQL generation: {e}. Falling back to heuristic.")

    if not generated or not generated.lower().startswith("select"):
        generated = fallback_nl_to_sql(query)
        print("Using fallback SQL:", generated)

    # --- FIX: Rewrite float_id matches into b'number ' format ---
    def fix_float_id(match):
        num = match.group(1)
        return f'float_id = "b\'{num} \'"'

    generated = re.sub(r"float_id\s*=\s*'(\d+)'", fix_float_id, generated)
    generated = re.sub(r'float_id\s*=\s*"(\d+)"', fix_float_id, generated)

    return generated.strip() + ";"


def execute_and_synthesize_response(sql_query, user_query, language_code):
    if not db_connection:
        return {"summary": "Server DB not available.", "data": []}
    if not sql_query:
        return {"summary": "Sorry, could not create a valid SQL query.", "data": []}
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
        
        summary_text = f"Returned {len(rows_as_dicts)} rows."
        
        if model:
            try:
                prompt = f"""
The user asked: "{user_query}"
The SQL query returned the following rows:\n{results_str}\nPlease summarize briefly and respond only in the language with ISO code: {language_code}.
"""
                resp = model.generate_content(prompt)
                summary_text = resp.text.strip()
                
                if not summary_text:
                    summary_text = f"Returned {len(rows_as_dicts)} rows (LLM returned empty response)."
            except Exception as e:
                print(f"LLM summarization error: {e}")
                
                if "quota" in str(e).lower() or "429" in str(e):
                     summary_text = f"Returned {len(rows_as_dicts)} rows. LLM Quota Exceeded (429). Please check your API usage limits."
                else:
                    summary_text = f"Returned {len(rows_as_dicts)} rows (LLM summary failed: {e})."
        else:
            summary_text += " (No LLM configured.)"
            
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
def handle_query(user_query, language_code):
    context = "" 
    sql_query = natural_language_to_sql(user_query, context)
    if not sql_query:
        return {"summary": "I couldn't generate a valid SQL query from your question. Try rephrasing.", "data": []}
    return execute_and_synthesize_response(sql_query, user_query, language_code)

@app.route("/api/query", methods=["POST"])
def process_query():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"summary": "Invalid request payload (expected JSON object).", "data": []}), 400
    
    user_query = payload.get("query")
    language_code = payload.get("language", "en") 
    
    if not user_query or not isinstance(user_query, str):
        return jsonify({"summary": "No query provided or query not a string.", "data": []}), 400
    
    resp = handle_query(user_query, language_code)
    return jsonify(resp)

@app.route("/api/test", methods=["GET"])
def api_test():
    sample = [
        {"float_id": 123, "date": "2002-03-05", "pressure": 10.0, "temperature": 24.5, "salinity": 35.1},
        {"float_id": 123, "date": "2002-03-06", "pressure": 50.0, "temperature": 20.9, "salinity": 34.8},
        {"float_id": 123, "date": "2002-03-07", "pressure": 100.0, "temperature": 15.4, "salinity": 34.6},
    ]
    return jsonify({"summary": "This is a test response with sample float data.", "data": sample})

# --------------------------
# History Fetch Endpoint (For fetching chat history by ID)
# --------------------------
@app.route("/api/history/<history_id>", methods=["GET"])
def fetch_history(history_id):
    """Fetches chat history using a unique ID."""
    global history_store
    
    history = history_store.get(history_id)
    if history:
        return jsonify({"history": history}), 200
    else:
        return jsonify({"error": "History ID not found or expired."}), 404

# --------------------------
# Language Conversion/Resummarization Endpoint
# --------------------------
@app.route("/api/resummarize", methods=["POST"])
def resummarize_message():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"summary": "Invalid request payload.", "data": []}), 400

    user_query = payload.get("user_query")
    data_list = payload.get("data", [])
    language_code = payload.get("language", "en")

    if not model or not user_query or not data_list:
        return jsonify({"summary": "Translation skipped: LLM not available or missing data.", "data": data_list}), 200

    results_str = str(data_list)
    if len(results_str) > 2000:
        results_str = results_str[:2000] + "..."

    try:
        prompt = f"""
The original user question was: "{user_query}"
The SQL query returned the following rows:
{results_str}
Please summarize briefly, translating the context of the data and response to the language with ISO code: {language_code}. Do not include the data itself in the response.
"""
        resp = model.generate_content(prompt)
        summary_text = resp.text.strip()
        
        if not summary_text:
            summary_text = f"Translation to {language_code} failed (LLM returned empty response)."
            
        return jsonify({"summary": summary_text, "data": data_list})
    except Exception as e:
        print(f"LLM resummarization error: {e}")
        return jsonify({"summary": f"Translation failed due to LLM error: {e}", "data": data_list}), 500


# --------------------------
# QR Code Endpoint (Fixed to use History ID for 'unlimited' prompts)
# --------------------------
@app.route("/api/qr_code", methods=["POST"])
def generate_qr():
    global history_store
    
    try:
        payload = request.get_json(silent=True)
        chat_history = payload.get("history", [])

        if not chat_history:
            return jsonify({"error": "No chat history provided."}), 400
        
        # 1. Generate a unique ID for this chat session
        history_id = str(uuid.uuid4())

        # 2. Store the full history in the in-memory store and file
        history_store[history_id] = chat_history
        save_history_store() # Persist the store
        
        # 3. Construct the minimal URL using only the history_id
        frontend_url = request.host_url.replace(":5000", ":8501")
        qr_url = f"{frontend_url}?history_id={history_id}" # Pass ID instead of data!

        # 4. Generate the QR code for the short ID URL
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10, 
            border=5
        )
        qr.add_data(qr_url)
        qr.make(fit=True)
        
        if qr.version is None or qr.version > 40:
             return jsonify({"error": f"Internal Error: QR URL encoding failed (required version {qr.version})."}), 500


        img = qr.make_image(fill_color="black", back_color="white")
        
        buf = BytesIO()
        img.save(buf)
        buf.seek(0)
        
        return send_file(buf, mimetype="image/png")
    except Exception as e:
        print(f"QR Code generation error: {e}")
        return jsonify({"error": str(e)}), 500

# --------------------------
# ROUTE INFORMATION HELPERS
# --------------------------

def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    """Calculates the Great-Circle distance between two points in kilometers."""
    R = 6371.0 
    
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance = R * c
    return round(distance, 2)

def calculate_initial_bearing(lat1, lon1, lat2, lon2):
    """Calculates the initial bearing (compass direction) from point 1 to point 2."""
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    y = math.sin(lon2_rad - lon1_rad) * math.cos(lat2_rad)
    x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(lon2_rad - lon1_rad)
    
    bearing_rad = math.atan2(y, x)
    
    bearing_deg = math.degrees(bearing_rad)
    bearing_deg = (bearing_deg + 360) % 360
    
    directions = ["North", "North-East", "East", "South-East", "South", "South-West", "West", "North-West"]
    index = round(bearing_deg / 45) % 8
    
    return directions[index]

# --------------------------
# ROUTE INFORMATION ENDPOINT
# --------------------------

@app.route("/api/route_info", methods=["POST"])
def get_route_info():
    """Calculates straight-line distance and direction between two points."""
    try:
        payload = request.get_json(silent=True)
        
        start_lat = float(payload.get('start_lat'))
        start_lon = float(payload.get('start_lon'))
        end_lat = float(payload.get('end_lat'))
        end_lon = float(payload.get('end_lon'))

        if None in [start_lat, start_lon, end_lat, end_lon]:
            return jsonify({"error": "Missing coordinates in payload."}), 400

        distance = calculate_haversine_distance(start_lat, start_lon, end_lat, end_lon)
        direction = calculate_initial_bearing(start_lat, start_lon, end_lat, end_lon)

        response = {
            "distance_km": distance,
            "instruction": f"Go {direction} for {distance} kilometers (straight line distance).",
            "direction": direction
        }
        return jsonify(response)
        
    except ValueError:
        return jsonify({"error": "Latitude/Longitude must be valid numbers."}), 400
    except Exception as e:
        print(f"Route calculation error: {e}")
        return jsonify({"error": f"Internal calculation error: {e}"}), 500


if __name__ == "__main__": 
    app.run(host="127.0.0.1", port=5000, debug=True)
