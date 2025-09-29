import xarray as xr
import pandas as pd
import sqlite3
import os
import faiss
from sentence_transformers import SentenceTransformer
import numpy as np

# --- CONFIGURATION ---
DB_FILE = "argo_data.db"
ARGO_DATA_DIR = "argo_data"

# --- DATABASE CONNECTION ---
def get_db_connection():
    """Establishes a connection to the SQLite database file."""
    return sqlite3.connect(DB_FILE)

# --- DATA PROCESSING & LOADING ---
def process_and_load_data():
    """
    Main function to process NetCDF files and load data into SQLite and FAISS.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    # Create tables if they don't exist
    cur.execute("""
        CREATE TABLE IF NOT EXISTS argo_metadata (
            float_id TEXT PRIMARY KEY,
            platform_type TEXT,
            country TEXT,
            deployment_date TEXT
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS argo_profiles (
            profile_id INTEGER PRIMARY KEY,
            float_id TEXT,
            cycle_number INTEGER,
            latitude REAL,
            longitude REAL,
            date REAL,
            pressure REAL,
            temperature REAL,
            salinity REAL,
            FOREIGN KEY (float_id) REFERENCES argo_metadata(float_id)
        );
    """)
    conn.commit()

    # Initialize the embedding model and FAISS index
    model = SentenceTransformer('all-MiniLM-L6-v2')
    embedding_dim = model.get_sentence_embedding_dimension()
    faiss_index = faiss.IndexFlatL2(embedding_dim)
    float_metadata_map = {}
    
    # Load existing FAISS index and metadata if they exist
    if os.path.exists("faiss_index.bin") and os.path.exists("metadata_map.npy"):
        faiss_index = faiss.read_index("faiss_index.bin")
        float_metadata_map = np.load('metadata_map.npy', allow_pickle=True).item()
        print("Loaded existing FAISS index and metadata map.")

    print("Starting data ingestion...")
    
    # Use os.walk to iterate through all files in the downloaded directory
    for root, _, files in os.walk(ARGO_DATA_DIR):
        for file in files:
            if file.endswith('.nc'):
                file_path = os.path.join(root, file)
                
                try:
                    with xr.open_dataset(file_path) as ds:
                        # Extract float ID and cycle number
                        float_id = str(ds['PLATFORM_NUMBER'].values[0])
                        cycle_number = int(ds['CYCLE_NUMBER'].values[0])
                        
                        # Check if this profile has already been processed to avoid duplicates
                        cur.execute("SELECT 1 FROM argo_profiles WHERE float_id = ? AND cycle_number = ?", (float_id, cycle_number))
                        if cur.fetchone():
                            print(f"Skipping {file}: already processed.")
                            continue

                        # --- 1. Load into SQLite ---
                        # Insert metadata (if it doesn't already exist)
                        cur.execute("INSERT OR IGNORE INTO argo_metadata (float_id) VALUES (?)", (float_id,))
                        
                        # Extract profile data into a pandas DataFrame and reset the index
                        df = ds.to_dataframe().reset_index()

                        # Select and rename columns to match the database schema
                        df = df[['JULD', 'LATITUDE', 'LONGITUDE', 'PRES', 'TEMP', 'PSAL']]
                        df.rename(columns={'JULD': 'date', 'LATITUDE': 'latitude', 'LONGITUDE': 'longitude',
                                           'PRES': 'pressure', 'TEMP': 'temperature', 'PSAL': 'salinity'}, inplace=True)
                        
                        # Add float_id and cycle_number to the DataFrame
                        df['float_id'] = float_id
                        df['cycle_number'] = cycle_number
                        
                        # Bulk insert into argo_profiles table
                        df.to_sql('argo_profiles', conn, if_exists='append', index=False)
                        print(f"Successfully loaded data for float {float_id}, cycle {cycle_number} into SQLite.")

                        # --- 2. Store in Vector Database (FAISS) ---
                        # Create a summary for embedding
                        date_min = str(ds['JULD'].min().values)
                        date_max = str(ds['JULD'].max().values)
                        lat_mean = float(ds['LATITUDE'].mean().values)
                        lon_mean = float(ds['LONGITUDE'].mean().values)
                        
                        summary = (f"ARGO float {float_id} in the Indian Ocean. "
                                   f"Data from {date_min} to {date_max}. "
                                   f"Mean location: {lat_mean:.2f}N, {lon_mean:.2f}E. "
                                   f"Measures temperature, salinity, and pressure.")
                        
                        # Generate embedding
                        embedding = model.encode(summary, convert_to_tensor=False)

                        # Add embedding to FAISS index
                        faiss_index.add(np.expand_dims(embedding, axis=0))

                        # Store metadata for retrieval later
                        float_metadata_map[faiss_index.ntotal - 1] = {
                            'float_id': float_id,
                            'summary': summary
                        }
                        print(f"Successfully generated and stored embedding for float {float_id}.")

                except Exception as e:
                    print(f"Failed to process file {file_path}: {e}")

    # Save the FAISS index and metadata map to disk for persistence
    faiss.write_index(faiss_index, "faiss_index.bin")
    np.save('metadata_map.npy', float_metadata_map)
    print("FAISS index and metadata map saved to disk.")
    
    cur.close()
    conn.close()
    print("Data ingestion complete. Database connection closed.")

if __name__ == "__main__":
    process_and_load_data()