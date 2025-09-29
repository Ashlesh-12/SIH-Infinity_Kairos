import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import base64
import json
from typing import Any, Dict, List, Optional, Tuple

# Import modular components
from qr_component import render_qr_share_button
from map_feature import render_map_with_route, find_nearest_ports, INDIAN_OCEAN_PORTS 
# NEW IMPORT: Emergency Feature (We use constants and the function from here)
from emergency_feature import render_emergency_call, EMERGENCY_PHONE_NUMBER, EMERGENCY_CONTACT_NAME

# ------------- CONFIG -------------
DEFAULT_BACKEND_URL = "http://127.0.0.1:5000/api/query"
TEST_BACKEND_URL = "http://127.0.0.1:5000/api/test"
QR_CODE_BACKEND_URL = "http://127.0.0.1:5000/api/qr_code"
RESUMMARIZE_BACKEND_URL = "http://127.0.0.1:5000/api/resummarize" 
HISTORY_FETCH_BASE_URL = "http://127.0.0.1:5000/api/history/"
ROUTE_INFO_URL = "http://127.0.0.1:5000/api/route_info" 
REQUEST_TIMEOUT = 30 # seconds

# --- NEW: LANGUAGE CONFIGURATION ---
LANGUAGES = {
    "English": "en",
    "Spanish": "es",
    "French": "fr",
    "Hindi (हिन्दी)": "hi",
    "Kannada (ಕನ್ನಡ)": "kn",
}

# Localization dictionary (Updated with map specific keys)
UI_TEXT = {
    "en": {
        "title": "FloatChat: Ocean Data Discovery",
        "intro": "Ask questions about ARGO float data. Frontend auto-generates visualizations when possible.",
        "welcome": "Hello! What ocean data are you curious about?",
        "settings": "Settings",
        "language": "Select Language",
        "use_test_endpoint": "Use /api/test endpoint (debug)",
        "quick_examples": "Quick example queries",
        "ex_temp_pressure": "Show temperature & pressure for float 123",
        "ex_salinity_equator": "Salinity & pressure near equator",
        "ex_avg_temp": "Avg temperature Mar 2002",
        "show_raw": "Show raw JSON response",
        "input_label": "Ask a question about ARGO data...",
        "send": "Send",
        "fetching": "Fetching results...",
        "error_backend": "Error contacting backend: ",
        "no_summary": "No summary returned.",
        "invalid_response": "Invalid response format",
        "plot_controls": "Plot controls",
        "x_axis": "X axis",
        "y_axis": "Y axis",
        "chart_type": "Chart type",
        "no_plot": "Could not visualize returned data: ",
        "no_data": "The SQL query returned no tabular data to plot.",
        "translating": "Translating history...",
        "failed_load_history": "Failed to load history from QR code:",
        "failed_translate_message": "Failed to translate message ",
        "map_controls": "Map Controls", 
        "float_id_input": "Enter Float ID:", 
        "destination_input": "Choose Destination Port:",
        "show_route_btn": "Show Route on Map",
        "float_not_found": "No data found for Float ID '{}'. Please query for it first.",
        "emergency_call_header": "Emergency Medical Alert", # New string
        "emergency_alert_btn": "🚨 SOS: Call Rescue Team", # New string
        "emergency_instruction_1": "Location data is based on the last 'Float ID' search.", # New string
        "emergency_instruction_2": "Click the button to call, and report this location:", # New string
        "emergency_no_location": "Please search for a Float ID first to determine a location.", # New string
    },
    "es": {
        "title": "FloatChat: Descubrimiento de Datos Oceánicos",
        "intro": "Haga preguntas sobre datos de flotadores ARGO. El front-end genera visualizaciones automáticamente cuando es posible.",
        "welcome": "¡Hola! ¿Qué datos oceánicos le interesan?",
        "settings": "Configuración",
        "language": "Seleccionar Idioma",
        "use_test_endpoint": "Usar endpoint /api/test (depuración)",
        "quick_examples": "Consultas de ejemplo rápidas",
        "ex_temp_pressure": "Mostrar temperatura y presión para el flotador 123",
        "ex_salinity_equator": "Salinidad y presión cerca del ecuador",
        "ex_avg_temp": "Temperatura promedio Mar 2002",
        "show_raw": "Mostrar respuesta JSON sin procesar",
        "input_label": "Haga una pregunta sobre datos ARGO...",
        "send": "Enviar",
        "fetching": "Obteniendo resultados...",
        "error_backend": "Error al contactar al backend: ",
        "no_summary": "No se devolvió ningún resumen.",
        "invalid_response": "Formato de respuesta inválido",
        "plot_controls": "Controles de Trazado",
        "x_axis": "Eje X",
        "y_axis": "Eje Y",
        "chart_type": "Tipo de Gráfico",
        "no_plot": "No se pudieron visualizar los datos devueltos: ",
        "no_data": "La consulta SQL no devolvió datos tabulares para trazar.",
        "translating": "Traduciendo historial...",
        "failed_load_history": "Error al cargar el historial desde el código QR:",
        "failed_translate_message": "Error al traducir mensaje ",
        "map_controls": "Controles de Mapa", 
        "float_id_input": "Introducir ID de Flotador:", 
        "destination_input": "Elegir Puerto de Destino:",
        "show_route_btn": "Mostrar Ruta en el Mapa",
        "float_not_found": "No se encontraron datos para el ID de flotador '{}'. Por favor, primero haga una consulta sobre él.",
        "emergency_call_header": "Alerta Médica de Emergencia", # New string
        "emergency_alert_btn": "🚨 SOS: Llamar Equipo de Rescate", # New string
        "emergency_instruction_1": "Los datos de ubicación se basan en la última búsqueda de 'ID de Flotador'.", # New string
        "emergency_instruction_2": "Haga clic para llamar e informe esta ubicación:", # New string
        "emergency_no_location": "Busque primero una ID de Flotador para determinar una ubicación.", # New string
    },
    "fr": {
        "title": "FloatChat: Découverte de Données Océaniques",
        "intro": "Posez des questions sur les données des flotteurs ARGO. Le frontend génère automáticamente des visualizaciones lorsque cela est possible.",
        "welcome": "Bonjour! Quelles données océaniques vous intéressent?",
        "settings": "Paramètres",
        "language": "Sélectionner la Langue",
        "use_test_endpoint": "Utiliser le point de terminaison /api/test (débogage)",
        "quick_examples": "Exemples de requêtes rapides",
        "ex_temp_pressure": "Afficher la température et la pression du flotteur 123",
        "ex_salinity_equator": "Salinité et pression près de l'équateur",
        "ex_avg_temp": "Température moyenne Mars 2002",
        "show_raw": "Afficher la réponse JSON brute",
        "input_label": "Posez une question sur les données ARGO...",
        "send": "Envoyer",
        "fetching": "Récupération des résultats...",
        "error_backend": "Erreur de communication avec le backend: ",
        "no_summary": "Aucun résumé retourné.",
        "invalid_response": "Format de réponse invalide",
        "plot_controls": "Contrôles de Plot",
        "x_axis": "Axe X",
        "y_axis": "Axe Y",
        "chart_type": "Type de Graphique",
        "no_plot": "Impossible de visualiser les données retournées: ",
        "no_data": "La requête SQL n'a retourné aucune donnée tabulaire à tracer.",
        "translating": "Traduction de l'historique en cours...",
        "failed_load_history": "Échec du chargement de l'historique à partir du code QR:",
        "failed_translate_message": "Échec de la traduction du message ",
        "map_controls": "Contrôles de Carte", 
        "float_id_input": "Entrez l'ID du Flotteur:", 
        "destination_input": "Choisissez le Port de Destination:",
        "show_route_btn": "Afficher l'Itinéraire sur la Carte",
        "float_not_found": "Aucune donnée trouvée pour l'ID de Flotteur '{}'. Veuillez d'abord le rechercher.",
        "emergency_call_header": "Alerte Médicale d'Urgence", # New string
        "emergency_alert_btn": "🚨 SOS: Appeler Équipe de Sauvetage", # New string
        "emergency_instruction_1": "Les données de localisation sont basées sur la dernière recherche 'ID de Flotteur'.", # New string
        "emergency_instruction_2": "Cliquez pour appeler et signalez cette position:", # New string
        "emergency_no_location": "Veuillez d'abord rechercher un ID de Flotteur pour déterminer une position.", # New string
    },
    "hi": { 
        "title": "फ्लोटचैट: महासागर डेटा खोज",
        "intro": "ARGO फ्लोट डेटा के बारे में प्रश्न पूछें। फ्रंटएंड संभव होने पर स्वचालित रूप से विज़ुअलाइज़ेशन उत्पन्न करता है।",
        "welcome": "नमस्ते! आप किस महासागर डेटा के बारे में उत्सुक हैं?",
        "settings": "सेटिंग्स",
        "language": "भाषा चुनें",
        "use_test_endpoint": "/api/test एंडपॉइंट का उपयोग करें (डीबग)",
        "quick_examples": "त्वरित उदाहरण प्रश्न",
        "ex_temp_pressure": "फ्लोट 123 के लिए तापमान और दबाव दिखाएं",
        "ex_salinity_equator": "भूमध्य रेखा के पास लवणता और दबाव",
        "ex_avg_temp": "मार्च 2002 का औसत तापमान",
        "show_raw": "कच्चा JSON उत्तर दिखाएं",
        "input_label": "ARGO डेटा के बारे में एक प्रश्न पूछें...",
        "send": "भेजें",
        "fetching": "परिणाम प्राप्त हो रहे हैं...",
        "error_backend": "बैकएंड से संपर्क करने में त्रुटि: ",
        "no_summary": "कोई सारांश नहीं मिला।",
        "invalid_response": "अवैध प्रतिक्रिया प्रारूप",
        "plot_controls": "प्लॉट नियंत्रण",
        "x_axis": "X अक्ष",
        "y_axis": "Y अक्ष",
        "chart_type": "चार्ट प्रकार",
        "no_plot": "वापस किए गए डेटा को विज़ुअलाइज़ नहीं कर सका: ",
        "no_data": "SQL क्वेरी ने प्लॉट करने के लिए कोई सारणीबद्ध डेटा वापस नहीं किया।",
        "translating": "इतिहास का अनुवाद हो रहा है...",
        "failed_load_history": "QR कोड से इतिहास लोड करने में विफल:",
        "failed_translate_message": "संदेश का अनुवाद करने में विफल रहा ",
        "map_controls": "मानचित्र नियंत्रण", 
        "float_id_input": "फ्लोट आईडी दर्ज करें:", 
        "destination_input": "गंतव्य बंदरगाह चुनें:",
        "show_route_btn": "मानचित्र पर मार्ग दिखाएं",
        "float_not_found": "फ्लोट आईडी '{}' के लिए कोई डेटा नहीं मिला। कृपया पहले इसके लिए एक क्वेरी चलाएं।",
        "emergency_call_header": "आपातकालीन चिकित्सा चेतावनी", # New string
        "emergency_alert_btn": "🚨 SOS: बचाव दल को कॉल करें", # New string
        "emergency_instruction_1": "स्थान डेटा अंतिम 'फ्लोट आईडी' खोज पर आधारित है।", # New string
        "emergency_instruction_2": "कॉल करने के लिए बटन पर क्लिक करें और इस स्थान की रिपोर्ट करें:", # New string
        "emergency_no_location": "स्थान निर्धारित करने के लिए कृपया पहले एक फ्लोट आईडी खोजें।", # New string
    },
    "kn": { 
        "title": "ಫ್ಲೋಟ್‌ಚಾಟ್: ಸಾಗರ ದತ್ತಾಂಶ ಶೋಧ",
        "intro": "ARGO ಫ್ಲೋಟ್ ಡೇಟಾ ಬಗ್ಗೆ ಪ್ರಶ್ನೆಗಳನ್ನು ಕೇಳಿ. ಸಾಧ್ಯವಾದಾಗ ಮುಂಭಾಗವು ಸ್ವಯಂಚಾಲಿತವಾಗಿ ದೃಶ್ಯೀಕರಣಗಳನ್ನು ರಚಿಸುತ್ತದೆ.",
        "welcome": "ನಮಸ್ಕಾರ! ನಿಮಗೆ ಯಾವ ಸಾಗರ ದತ್ತಾಂಶದ ಬಗ್ಗೆ ಕುತೂಹಲವಿದೆ?",
        "settings": "ಸೆಟ್ಟಿಂಗ್‌ಗಳು",
        "language": "ಭಾಷೆ ಆಯ್ಕೆಮಾಡಿ",
        "use_test_endpoint": "/api/test ಎಂಡ್‌ಪಾಯಿಂಟ್ ಬಳಸಿ (ಡೀಬಗ್)",
        "quick_examples": "ತ್ವರಿತ ಉದಾಹರಣೆ ಪ್ರಶ್ನೆಗಳು",
        "ex_temp_pressure": "ಫ್ಲೋಟ್ 123 ಗಾಗಿ ತಾಪಮಾನ ಮತ್ತು ಒತ್ತಡವನ್ನು ತೋರಿಸಿ",
        "ex_salinity_equator": "ಸಮಭಾಜಕದ ಬಳಿ ಲವಣಾಂಶ ಮತ್ತು ಒತ್ತಡ",
        "ex_avg_temp": "ಮಾರ್ಚ್ 2002 ರ ಸರಾಸರಿ ತಾಪಮಾನ",
        "show_raw": "ಕಚ್ಚಾ JSON ಪ್ರತಿಕ್ರಿಯೆಯನ್ನು ತೋರಿಸಿ",
        "input_label": "ARGO ದತ್ತಾಂಶದ ಬಗ್ಗೆ ಪ್ರಶ್ನೆ ಕೇಳಿ...",
        "send": "ಕಳುಹಿಸಿ",
        "fetching": "ಫಲಿತಾಂಶಗಳನ್ನು ಪಡೆಯಲಾಗುತ್ತಿದೆ...",
        "error_backend": "ಬ್ಯಾಕೆಂಡ್‌ಗೆ ಸಂಪರ್ಕಿಸುವಲ್ಲಿ ದೋಷ: ",
        "no_summary": "ಯಾವುದೇ ಸಾರಾಂಶ ಹಿಂತಿರುಗಿಸಲಾಗಿಲ್ಲ.",
        "invalid_response": "ಅಮಾನ್ಯ ಪ್ರತಿಕ್ರಿಯೆ ಸ್ವರೂಪ",
        "plot_controls": "ಪ್ಲಾಟ್ ನಿಯಂತ್ರಣಗಳು",
        "x_axis": "X ಅಕ್ಷ",
        "y_axis": "Y ಅಕ್ಷ",
        "chart_type": "ಚಾರ್ಟ್ ಪ್ರಕಾರ",
        "no_plot": "ಹಿಂತಿರುಗಿಸಿದ ಡೇಟಾವನ್ನು ದೃಶ್ಯೀಕರಿಸಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ.",
        "no_data": "SQL ಪ್ರಶ್ನೆಯು ಪ್ಲಾಟ್ ಮಾಡಲು ಯಾವುದೇ ಟ್ಯಾಬ್ಯುಲರ್ ಡೇಟಾವನ್ನು ಹಿಂತಿರುಗಿಸಲಿಲ್ಲ.",
        "translating": "ಇತಿಹಾಸವನ್ನು ಅನುವಾದಿಸಲಾಗುತ್ತಿದೆ...",
        "failed_load_history": "QR ಕೋಡ್‌ನಿಂದ ಇತಿಹಾಸವನ್ನು ಲೋಡ್ ಮಾಡಲು ವಿಫಲವಾಗಿದೆ:",
        "failed_translate_message": "ಸಂದೇಶವನ್ನು ಅನುವಾದಿಸಲು ವಿಫಲವಾಗಿದೆ ",
        "map_controls": "ನಕ್ಷೆ ನಿಯಂತ್ರಣಗಳು", 
        "float_id_input": "ಫ್ಲೋಟ್ ಐಡಿ ನಮೂದಿಸಿ:", 
        "destination_input": "ಗಮ್ಯಸ್ಥಾನ ಬಂದರು ಆಯ್ಕೆಮಾಡಿ:",
        "show_route_btn": "ನಕ್ಷೆಯಲ್ಲಿ ಮಾರ್ಗವನ್ನು ತೋರಿಸು",
        "float_not_found": "ಫ್ಲೋಟ್ ಐಡಿ '{}' ಗಾಗಿ ಯಾವುದೇ ಡೇಟಾ ಕಂಡುಬಂದಿಲ್ಲ. ದಯವಿಟ್ಟು ಮೊದಲು ಅದಕ್ಕಾಗಿ ಒಂದು ಪ್ರಶ್ನೆಯನ್ನು ರನ್ ಮಾಡಿ.",
        "emergency_call_header": "ತುರ್ತು ವೈದ್ಯಕೀಯ ಎಚ್ಚರಿಕೆ", # New string
        "emergency_alert_btn": "🚨 SOS: ರಕ್ಷಣಾ ತಂಡಕ್ಕೆ ಕರೆ ಮಾಡಿ", # New string
        "emergency_instruction_1": "ಸ್ಥಳದ ಡೇಟಾವು ಕೊನೆಯ 'ಫ್ಲೋಟ್ ಐಡಿ' ಹುಡುಕಾಟವನ್ನು ಆಧರಿಸಿದೆ.", # New string
        "emergency_instruction_2": "ಕರೆ ಮಾಡಲು ಬಟನ್ ಕ್ಲಿಕ್ ಮಾಡಿ ಮತ್ತು ಈ ಸ್ಥಳವನ್ನು ವರದಿ ಮಾಡಿ:", # New string
        "emergency_no_location": "ಸ್ಥಳವನ್ನು ನಿರ್ಧರಿಸಲು ದಯವಿಟ್ಟು ಮೊದಲು ಫ್ಲೋಟ್ ಐಡಿಯನ್ನು ಹುಡುಕಿ.", # New string
    }
}
# --- Helper functions (Must be included here for local scoping reasons) ---
def to_numeric_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = pd.to_numeric(df[c], errors="ignore")
    return df

def detect_date_column(df: pd.DataFrame) -> Optional[str]:
    for c in df.columns:
        if "date" in c.lower():
            try:
                pd.to_datetime(df[c], errors="raise")
                return c
            except Exception:
                parsed = pd.to_datetime(df[c], errors="coerce")
                if parsed.notna().sum() >= max(1, len(parsed) // 4):
                    return c
    return None

def choose_axes(df: pd.DataFrame) -> Tuple[Optional[str], Optional[str], str]:
    df = to_numeric_df(df)
    cols = list(df.columns)
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    if len(df) == 1 and numeric_cols:
        return (None, None, "bar")
    date_col = detect_date_column(df)
    if date_col:
        for pref in ["temperature", "temp", "salinity", "pressure"]:
            for c in cols:
                if pref in c.lower() and c in numeric_cols:
                    return (date_col, c, "line")
        if numeric_cols:
            return (date_col, numeric_cols[0], "line")
    pressure_col = None
    for c in cols:
        if "pressure" == c.lower() or "pressure" in c.lower():
            pressure_col = c
            break
    if pressure_col:
        for pref in ["temperature", "salinity", "temp"]:
            for c in cols:
                if pref in c.lower() and c in numeric_cols:
                    return (c, pressure_col, "line")
        others = [c for c in numeric_cols if c != pressure_col]
        if others:
            return (others[0], pressure_col, "line")
    if len(numeric_cols) >= 2:
        return (numeric_cols[0], numeric_cols[1], "scatter")
    return (None, None, "table")

def plot_dataframe(df: pd.DataFrame, x: Optional[str], y: Optional[str], chart_type: str):
    if chart_type == "bar":
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        if not numeric_cols:
            st.dataframe(df)
            return
        bar_df = pd.DataFrame({
            "metric": numeric_cols,
            "value": [float(df.iloc[0][c]) if pd.notna(df.iloc[0][c]) else None for c in numeric_cols]
        })
        fig = px.bar(bar_df, x="metric", y="value", title="Aggregated values")
        st.plotly_chart(fig, use_container_width=True)
        return
    if chart_type in ("line", "scatter"):
        if x is None or y is None:
            st.dataframe(df)
            return
        if "date" in x.lower():
            try:
                df[x] = pd.to_datetime(df[x], errors="coerce")
            except Exception:
                pass
        if chart_type == "line":
            try:
                df_plot = df.sort_values(by=x)
            except Exception:
                df_plot = df
            fig = px.line(df_plot, x=x, y=y, title=f"{y} vs {x}")
        else:
            fig = px.scatter(df, x=x, y=y, title=f"{y} vs {x}")
        if y and "pressure" in y.lower():
            fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)
        return
    st.dataframe(df)
# --- End of Helpers ---

# --- Language change callback function ---
def update_language():
    new_language_code = LANGUAGES[st.session_state.selected_lang_name]
    old_language_code = st.session_state.lang_code
    
    if old_language_code == new_language_code:
        return
        
    st.session_state.lang_code = new_language_code
    
    # We must reset the map controls and prompt input value to force the language change visually
    # by ensuring their keys are updated on the next rerun.
    # Note: The next block in the main app logic handles the rerun after this function finishes.
    
    if len(st.session_state.messages) > 1:
        st.session_state.do_translate = True
    
# Function to get localized text
def t(key: str) -> str:
    if "lang_code" not in st.session_state:
        return UI_TEXT["en"].get(key, key)
    return UI_TEXT.get(st.session_state.lang_code, UI_TEXT["en"]).get(key, key) 

# ------------- STREAMLIT UI -------------
st.set_page_config(page_title="FloatChat", layout="wide")


# Initialize state 
if "lang_code" not in st.session_state:
    st.session_state.lang_code = LANGUAGES["English"]
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": t("welcome"), "data": [], "user_query": ""}] 
if "do_translate" not in st.session_state:
    st.session_state.do_translate = False 

# --- NEW: Map State Persistence ---
if "map_is_visible" not in st.session_state:
    st.session_state.map_is_visible = False
if "map_float_data" not in st.session_state:
    st.session_state.map_float_data = None
if "map_float_id" not in st.session_state:
    st.session_state.map_float_id = ""
if "map_dest" not in st.session_state:
    st.session_state.map_dest = ""
if "fetch_map_data" not in st.session_state: # Ensure fetch flag is initialized
    st.session_state.fetch_map_data = False


st.title(t("title"))
st.markdown(t("intro"))
st.markdown("---") 

# Check for history in URL query parameters (UPDATED FOR MAP SHARING)
query_params = st.query_params
if "history_id" in query_params:
    history_id = query_params["history_id"]
    if isinstance(history_id, list):
        history_id = history_id[0]
    
    # NEW LOGIC: Fetch history from backend using the ID
    # Use a flag to ensure we only load history once per session from the URL
    if not st.session_state.get("history_loaded", False):
        with st.spinner("Fetching shared history..."):
            try:
                resp = requests.get(f"{HISTORY_FETCH_BASE_URL}{history_id}", timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
                loaded_history = resp.json().get("history", [])
                
                initial_message_is_default = (len(st.session_state.messages) == 1 and st.session_state.messages[0]["content"] == t("welcome"))
                
                if initial_message_is_default and loaded_history:
                    
                    # --- Check for and extract map state marker ---
                    map_state_message = next((m for m in loaded_history if m.get("role") == "system_map_state"), None)
                    
                    if map_state_message:
                        st.session_state.map_float_id = map_state_message["map_id"]
                        st.session_state.map_dest = map_state_message["map_dest"]
                        st.session_state.fetch_map_data = True # Trigger map load
                        
                        # Filter out the system message before setting chat history
                        st.session_state.messages = [m for m in loaded_history if m.get("role") != "system_map_state"]
                    else:
                        st.session_state.messages = loaded_history
                    
                    st.session_state.history_loaded = True # Mark as loaded
                    # CRITICAL FIX: Rerun immediately to render loaded history/trigger map fetch
                    st.rerun() 
                
            except Exception as e:
                st.error(f"Failed to fetch shared history: {e}")
    
# Sidebar controls
with st.sidebar:
    st.header(t("settings"))

    # --- Language Dropdown with Callback ---
    st.selectbox(
        t("language"),
        options=list(LANGUAGES.keys()),
        index=list(LANGUAGES.values()).index(st.session_state.lang_code),
        key="selected_lang_name",
        on_change=update_language, 
    )
    
    st.markdown("---")

    # --- EMERGENCY FEATURE CALL (Using the new modular component) ---
    render_emergency_call(
        st.session_state.map_is_visible,
        st.session_state.map_float_data,
        t, # Pass the localization function
        EMERGENCY_PHONE_NUMBER,
        EMERGENCY_CONTACT_NAME
    )


    use_test_endpoint = st.checkbox(t("use_test_endpoint"), value=False)
    backend_url = TEST_BACKEND_URL if use_test_endpoint else DEFAULT_BACKEND_URL
    st.write("Backend URL:")
    st.code(backend_url)
    st.markdown("---")
    st.markdown(t("quick_examples"))
    if st.button(t("ex_temp_pressure")):
        st.session_state._example = "Show temperature and pressure for float 123"
        st.session_state._auto_submit = True
    if st.button(t("ex_salinity_equator")):
        st.session_state._example = "Show salinity and pressure for floats near the equator"
        st.session_state._auto_submit = True
    if st.button(t("ex_avg_temp")):
        st.session_state._example = "Average temperature between 2002-03-01 and 2002-03-31"
        st.session_state._auto_submit = True
    st.markdown("---")
    show_raw = st.checkbox(t("show_raw"), value=False)
    
    # --- MAP CONTROLS (Localization Fix Applied) ---
    st.header(t("map_controls"))
    
    # Use t() in keys to force re-render on language change
    selected_float_id = st.text_input(t("float_id_input"), 
                                      value=st.session_state.get("map_float_id", ""), 
                                      key=t("map_float_id_input"))
    port_names = [p['name'] for p in INDIAN_OCEAN_PORTS] # Use GLOBAL_OCEAN_PORTS for dropdown
    
    # Set default index for selectbox based on existing map_dest
    default_dest_index = port_names.index(st.session_state.map_dest) if st.session_state.map_dest in port_names else 3
    
    # Use t() in keys to force re-render on language change
    dest_port_name = st.selectbox(t("destination_input"), 
                                  options=port_names, 
                                  key=t("map_dest_port_select"), 
                                  index=default_dest_index)

    if st.button(t("show_route_btn")):
        # Store state variables
        st.session_state.map_is_visible = False # Hide until data is fetched
        st.session_state.map_float_data = None
        st.session_state.map_float_id = selected_float_id
        st.session_state.map_dest = dest_port_name
        st.session_state.fetch_map_data = True # Trigger data fetch logic below
    
    st.markdown("---")

    # --- QR Code Generation prep (Map Persistence for Sharing) ---
    # Create a copy of the history and append map state if visible
    history_to_share = st.session_state.messages.copy()
    if st.session_state.map_is_visible and st.session_state.map_float_id and st.session_state.map_dest:
        # Append a temporary system message holding the map state for sharing
        map_state_message = {
            "role": "system_map_state", 
            "map_id": st.session_state.map_float_id,
            "map_dest": st.session_state.map_dest
        }
        history_to_share.append(map_state_message)
        
    render_qr_share_button(QR_CODE_BACKEND_URL, history_to_share)


# --- History Translation Logic (Unchanged) ---
if st.session_state.get("do_translate"):
    st.session_state.do_translate = False
    temp_messages = []
    
    with st.spinner(t("translating")):
        for i, m in enumerate(st.session_state.messages):
            if m["role"] == "assistant" and m.get("data") and m.get("user_query"):
                try:
                    payload = {
                        "user_query": m.get("user_query"),
                        "data": m["data"],
                        "language": st.session_state.lang_code
                    }
                    resp = requests.post(RESUMMARIZE_BACKEND_URL, json=payload, timeout=REQUEST_TIMEOUT)
                    resp.raise_for_status()
                    translated_json = resp.json()
                    
                    new_message = m.copy()
                    new_message["content"] = translated_json.get("summary", m["content"])
                    temp_messages.append(new_message)
                except Exception as e:
                    st.error(f"Translation failed for message {i+1}. Keeping original text. Error: {e}")
                    temp_messages.append(m)
            else:
                if i == 0 and m["role"] == "assistant":
                    m["content"] = t("welcome")
                temp_messages.append(m)
        
        st.session_state.messages = temp_messages
        st.rerun() 

# --- Map Data Fetching Logic (Triggers when map button is pressed or history is loaded) ---
if st.session_state.get("fetch_map_data", False):
    # Reset flag immediately to prevent infinite loop
    st.session_state.fetch_map_data = False 
    
    float_id_to_find = st.session_state.map_float_id
    
    if float_id_to_find:
        with st.spinner(f"Fetching location for float ID {float_id_to_find}..."):
            # Ensure the float ID is cleaned for the query if necessary
            query_prompt = f"Show the latitude and longitude for float ID {float_id_to_find}"
            try:
                payload = {"query": query_prompt, "language": st.session_state.lang_code}
                resp = requests.post(DEFAULT_BACKEND_URL, json=payload, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
                response_json = resp.json()
                
                float_data = response_json.get("data", [])
                
                if float_data and 'latitude' in float_data[0] and 'longitude' in float_data[0]:
                    # Convert to DataFrame
                    float_df = pd.DataFrame(float_data)
                    float_df['latitude'] = pd.to_numeric(float_df['latitude'], errors='coerce')
                    float_df['longitude'] = pd.to_numeric(float_df['longitude'], errors='coerce')
                    float_df.dropna(subset=['latitude', 'longitude'], inplace=True)

                    if not float_df.empty:
                        # Store data and set visibility
                        st.session_state.map_float_data = float_df
                        st.session_state.map_is_visible = True
                    else:
                        st.warning(t("float_not_found").format(float_id_to_find))
                        st.session_state.map_is_visible = False
                else:
                    st.warning(t("float_not_found").format(float_id_to_find))
                    st.session_state.map_is_visible = False
            except Exception as e:
                st.error(f"Failed to fetch float location from backend: {e}")
                st.session_state.map_is_visible = False
    else:
        st.warning("Please enter a Float ID to show the route.")
        st.session_state.map_is_visible = False

    # Force a rerun to display the map based on the new state
    st.rerun()

# --- Display logic ---

# 1. Render the map if the persistent state variable is True
if st.session_state.map_is_visible and st.session_state.map_float_data is not None:
    # Renders the multi-path route
    render_map_with_route(
        st.session_state.map_float_data, 
        st.session_state.map_float_id, 
        st.session_state.map_dest, 
        t
    )
    st.markdown("---")

# 2. Render chat history 
for m in st.session_state.messages:
    # Ensure welcome message localization is correct
    if m["role"] == "assistant" and (m["content"] == UI_TEXT["en"]["welcome"] or "Hello!" in m["content"]):
        m["content"] = t("welcome")
    
    # Skip rendering the system map state message if it somehow survived
    if m["role"] == "system_map_state":
        continue

    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        data_preview = m.get("data", [])
        if isinstance(data_preview, list) and data_preview:
            try:
                df = pd.DataFrame(data_preview)
                df = to_numeric_df(df)
                x_col, y_col, chart_type = choose_axes(df)
                plot_dataframe(df, x_col, y_col, chart_type)
            except Exception:
                st.write("Could not preview historical data.")

# Prefill example and auto_submit flag
prefill = st.session_state.pop("_example", "")
auto_submit = st.session_state.pop("_auto_submit", False)

# Input form 
with st.form(key=f"chat_form_{st.session_state.lang_code}", clear_on_submit=True): # FIX 1: Dynamic key for the form
    
    # Use the localized input label and a key that changes with the language code
    user_input = st.text_input(t("input_label"), 
                               value=prefill, 
                               key=f"user_input_{st.session_state.lang_code}") 
    
    # Use the localized send button label
    submit = st.form_submit_button(t("send"), 
                                   key=f"send_button_{st.session_state.lang_code}")

do_submit = submit or auto_submit

if do_submit and user_input:
    prompt = user_input.strip()
    
    st.session_state.messages.append({"role": "user", "content": prompt, "user_query": prompt, "data": []}) 
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.spinner(t("fetching")):
        try:
            payload = {"query": prompt, "language": st.session_state.lang_code}
            resp = requests.post(backend_url, json=payload, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            response_json: Dict[str, Any] = resp.json()
        except requests.exceptions.RequestException as e:
            error_message = f'{t("error_backend")}{e}'
            response_json = {"summary": error_message, "data": []}
        except Exception as e:
            response_json = {"summary": f'An unexpected error occurred during request: {e}', "data": []}

    if isinstance(response_json, str):
        response_json = {"summary": response_json, "data": []}
    if not isinstance(response_json, dict):
        response_json = {"summary": t("invalid_response"), "data": []}

    summary = response_json.get("summary") or t("no_summary")
    data = response_json.get("data") or []

    with st.chat_message("assistant"):
        st.markdown(summary)
        if show_raw:
            st.expander("Raw JSON").write(response_json)

        if isinstance(data, list) and len(data) > 0:
            try:
                df = pd.DataFrame(data)
                df = to_numeric_df(df)
                x_col, y_col, chart_type = choose_axes(df)
                cols_for_select = list(df.columns)
                if chart_type != "bar" and len(cols_for_select) > 1:
                    st.markdown(f"### {t('plot_controls')}")
                    
                    default_x = x_col if (x_col in cols_for_select) else cols_for_select[0]
                    default_y = y_col if (y_col in cols_for_select) else (cols_for_select[1] if len(cols_for_select) > 1 else cols_for_select[0])
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        # Use t() in keys to force re-render on language change
                        chosen_x = st.selectbox(t("x_axis"), options=cols_for_select, index=cols_for_select.index(default_x) if default_x in cols_for_select else 0, key=t("x_select_"+str(len(st.session_state.messages))))
                    with col2:
                        # Use t() in keys to force re-render on language change
                        chosen_y = st.selectbox(t("y_axis"), options=cols_for_select, index=cols_for_select.index(default_y) if default_y in cols_for_select else (1 if len(cols_for_select) > 1 else 0), key=t("y_select_"+str(len(st.session_state.messages))))
                    # Use t() in keys to force re-render on language change
                    chart_type = st.selectbox(t("chart_type"), options=["line", "scatter", "bar", "table"], index=["line", "scatter", "bar", "table"].index(chart_type) if chart_type in ["line","scatter","bar"] else 0, key=t("chart_select_"+str(len(st.session_state.messages))))
                    x_col, y_col = chosen_x, chosen_y

                plot_dataframe(df, x_col, y_col, chart_type)
            except Exception as e:
                st.write(f'{t("no_plot")}{e}')
        else:
            st.info(t("no_data"))
    
    st.session_state.messages.append({"role": "assistant", "content": summary, "data": data, "user_query": prompt})
    st.rerun()
