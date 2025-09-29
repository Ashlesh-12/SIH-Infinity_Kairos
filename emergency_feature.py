import streamlit as st
import pandas as pd
from typing import Optional, Any, Dict, Tuple
from urllib.parse import quote_plus # NEW IMPORT for URL encoding

# Configuration constants (kept here for isolation)
EMERGENCY_PHONE_NUMBER = "+919380474652" # Simulated Emergency Hotline (911)
EMERGENCY_CONTACT_NAME = "Global Maritime Rescue" 

def render_emergency_call(
    is_map_visible: bool, 
    map_float_data: Optional[pd.DataFrame], 
    t_func: callable,
    emergency_phone: str,
    emergency_contact: str
):
    """
    Renders the Emergency SOS alert buttons (Call, SMS, WhatsApp) in the sidebar.
    
    It uses the last successfully fetched float location as the current vessel position.
    """
    
    st.header(t_func("emergency_call_header"))
    
    last_coords = None
    if is_map_visible and map_float_data is not None and not map_float_data.empty:
        try:
            # Safely extract last known coordinates
            lat = map_float_data['latitude'].iloc[0]
            lon = map_float_data['longitude'].iloc[0]
            last_coords = (lat, lon)
        except Exception:
            last_coords = None 

    if last_coords:
        lat, lon = last_coords
        
        # 1. Prepare Content and Links
        phone_no_clean = emergency_phone.lstrip('+').replace(' ', '')
        
        # Google Maps link for easy navigation
        maps_link = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        
        # Emergency Message Body, including the map link
        message = (
            f"EMERGENCY! Medical incident at sea. "
            f"Vessel location: LAT {lat:.4f}, LON {lon:.4f}. "
            f"Navigate to: {maps_link}"
        )
        
        # Encode the message for safe use in URL schemes
        encoded_message = quote_plus(message)
        
        # SMS link (uses sms: scheme for mobile devices)
        sms_link = f'sms:{emergency_phone}?body={encoded_message}'
        
        # WhatsApp link (web API for broad compatibility)
        whatsapp_link = f'https://wa.me/{phone_no_clean}?text={encoded_message}'
        
        # 2. Display UI
        st.info(t_func("emergency_instruction_1"))
        st.markdown(f"**{t_func('emergency_instruction_2')}**")
        st.markdown(f"`Latitude: {lat:.4f}, Longitude: {lon:.4f}`")
        
        col_call, col_sms, col_whatsapp = st.columns(3)

        with col_call:
            # Call Button (Primary action)
            st.markdown(
                f'<a href="tel:{emergency_phone}" target="_blank">'
                f'<button style="background-color: #ff4b4b; color: white; border: none; padding: 10px 5px; text-align: center; text-decoration: none; display: block; font-size: 14px; margin: 0px; cursor: pointer; border-radius: 8px; width: 100%;">'
                f'📞 Call ({emergency_contact})'
                f'</button></a>',
                unsafe_allow_html=True
            )

        with col_sms:
            # SMS Button
            st.markdown(
                f'<a href="{sms_link}" target="_blank">'
                f'<button style="background-color: #ff8c00; color: white; border: none; padding: 10px 5px; text-align: center; text-decoration: none; display: block; font-size: 14px; margin: 0px; cursor: pointer; border-radius: 8px; width: 100%;">'
                f'✉️ SMS Location'
                f'</button></a>',
                unsafe_allow_html=True
            )

        with col_whatsapp:
            # WhatsApp Button
            st.markdown(
                f'<a href="{whatsapp_link}" target="_blank">'
                f'<button style="background-color: #25D366; color: white; border: none; padding: 10px 5px; text-align: center; text-decoration: none; display: block; font-size: 14px; margin: 0px; cursor: pointer; border-radius: 8px; width: 100%;">'
                f'💬 WhatsApp Loc'
                f'</button></a>',
                unsafe_allow_html=True
            )

    else:
        st.warning(t_func("emergency_no_location"))
        # Render a single disabled button for visual consistency
        st.markdown(
            f'<button style="background-color: #555555; color: white; border: none; padding: 10px 20px; text-align: center; text-decoration: none; display: block; font-size: 16px; margin: 4px 2px; border-radius: 8px; width: 100%;" disabled>'
            f'{t_func("emergency_alert_btn")}'
            f'</button>',
            unsafe_allow_html=True
        )

    st.markdown("---")
