import streamlit as st
import requests
from typing import List, Dict, Any

# Assuming REQUEST_TIMEOUT is defined in the calling script (frontend.py)
REQUEST_TIMEOUT = 30 

def render_qr_share_button(backend_url: str, chat_history: List[Dict[str, Any]]):
    """
    Renders a Streamlit component to generate and display a QR code for sharing chat history.
    
    The backend_url here must point to the endpoint that saves the history and returns a unique ID.
    """
    st.header("Share Chat")
    
    if st.button("Generate Share QR Code"):
        # --- FIX: Relax the history check to allow sharing a map-only state ---
        
        # Check if the chat history contains more than just the initial welcome message (length > 1)
        # OR if it contains the map state marker (which indicates a route map is ready to share).
        
        # Note: chat_history passed from frontend.py already includes the system_map_state if the map is visible.
        # We assume the *first* message is always the initial welcome message.
        if len(chat_history) <= 1:
            st.warning("Cannot generate QR code: No user interaction or map route to share. Please ask a question or show a route first.")
            return

        with st.spinner("Generating unique share link..."):
            try:
                # Post the full history. The backend saves it and returns a minimal URL/QR Image.
                resp = requests.post(backend_url, json={"history": chat_history}, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
                
                # The response is the QR code image itself
                st.image(resp.content, caption="Scan this to share chat history.", use_container_width=True)
                st.success("QR code generated! (History stored on server.)")
                
            except requests.exceptions.HTTPError as e:
                # Catch specific HTTP errors (like the 500 error)
                error_detail = "Unknown server error."
                try:
                    # Attempt to parse detailed error message from JSON response
                    error_detail = resp.json().get("error", resp.text)
                except Exception:
                    error_detail = resp.text # Fallback to raw text
                st.error(f"Error contacting backend for QR code generation ({resp.status_code}): {error_detail}")
            except requests.exceptions.RequestException as e:
                st.error(f"Error contacting backend for QR code generation: {e}")
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
