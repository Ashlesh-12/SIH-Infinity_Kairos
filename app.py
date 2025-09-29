# app.py
import streamlit as st
import plotly.express as px
import requests
import pandas as pd

# --- CONFIGURATION ---
BACKEND_URL = "http://127.0.0.1:5000/api/query"

# --- STREAMLIT FRONTEND ---
st.set_page_config(page_title="FloatChat", layout="wide")
st.title("FloatChat: Ocean Data Discovery")
st.markdown("Ask me anything about ARGO float data in the Indian Ocean!")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hello! What ocean data are you curious about?"}]

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "data" in message and message["data"]:
            df = pd.DataFrame(message["data"])
            
            # This is a very basic plotting logic. You'll need to expand this.
            if 'salinity' in df.columns and 'pressure' in df.columns:
                fig = px.line(df, x="salinity", y="pressure", title="Salinity Profile")
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(fig, use_container_width=True)
            elif 'temperature' in df.columns and 'pressure' in df.columns:
                 fig = px.line(df, x="temperature", y="pressure", title="Temperature Profile")
                 fig.update_yaxes(autorange="reversed")
                 st.plotly_chart(fig, use_container_width=True)
            # You can add more plot types here

# Accept user input
if prompt := st.chat_input("Ask a question about ARGO data..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.spinner("Thinking..."):
        try:
            # Send the query to the backend API
            response = requests.post(BACKEND_URL, json={"query": prompt})
            response.raise_for_status()  # Raise an exception for bad status codes
            response_data = response.json()
            
            text_response = response_data.get("summary", "An error occurred.")
            data_to_plot = response_data.get("data", [])
        except requests.exceptions.RequestException as e:
            text_response = f"Could not connect to the backend server. Error: {e}"
            data_to_plot = []

    with st.chat_message("assistant"):
        st.markdown(text_response)
        if data_to_plot:
            df = pd.DataFrame(data_to_plot)
            if 'salinity' in df.columns and 'pressure' in df.columns:
                fig = px.line(df, x="salinity", y="pressure", title="Salinity Profile")
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(fig, use_container_width=True)
            elif 'temperature' in df.columns and 'pressure' in df.columns:
                fig = px.line(df, x="temperature", y="pressure", title="Temperature Profile")
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(fig, use_container_width=True)
            # You can add more plot types here

    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": text_response, "data": data_to_plot})