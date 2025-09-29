import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import geopy.distance
from typing import List, Dict, Any

# Defining a standardized list of ports, covering the initial set and key Indian Ocean locations
# We use this restricted list in the frontend dropdown and routing logic.
GLOBAL_OCEAN_PORTS = [
    # Indian Ocean / Africa / Asia
    {"name": "Durban, South Africa", "lat": -29.8587, "lon": 31.0218},
    {"name": "Mombasa, Kenya", "lat": -4.0500, "lon": 39.6667},
    {"name": "Chennai, India", "lat": 13.0827, "lon": 80.2707},
    {"name": "Colombo, Sri Lanka", "lat": 6.9271, "lon": 79.8612},
    {"name": "Chittagong, Bangladesh", "lat": 22.3475, "lon": 91.8123},
    {"name": "Port Louis, Mauritius", "lat": -20.1610, "lon": 57.5029},
    
    # Pacific Ocean / East Asia
    {"name": "Singapore", "lat": 1.290270, "lon": 103.851959},
    {"name": "Shanghai, China", "lat": 31.2304, "lon": 121.4737},
    {"name": "Yokohama, Japan", "lat": 35.4437, "lon": 139.6380},
    {"name": "Los Angeles, USA", "lat": 33.7297, "lon": -118.2625},
    {"name": "Sydney, Australia", "lat": -33.8688, "lon": 151.2093},
    
    # Atlantic Ocean / Europe / Americas
    {"name": "Rotterdam, Netherlands", "lat": 51.9244, "lon": 4.4777},
    {"name": "New York, USA", "lat": 40.7306, "lon": -73.9865},
    {"name": "Santos, Brazil", "lat": -23.9910, "lon": -46.3813},
    {"name": "Lagos, Nigeria", "lat": 6.4531, "lon": 3.3958}
]

# Alias the primary port list used by the rest of the application
INDIAN_OCEAN_PORTS = GLOBAL_OCEAN_PORTS 

def to_numeric_df(df: pd.DataFrame) -> pd.DataFrame:
    """Try to convert object columns that look numeric to numeric dtype."""
    df = df.copy()
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = pd.to_numeric(df[c], errors="ignore")
    return df

def find_nearest_ports(float_lat: float, float_lon: float, num_ports: int = 4) -> List[Dict[str, Any]]:
    """
    Finds the 'num_ports' nearest ports (1 primary + 3 alternates) to a given float's coordinates.
    """
    if not isinstance(float_lat, (int, float)) or not isinstance(float_lon, (int, float)):
        return []
    
    distances = []
    float_coords = (float_lat, float_lon)
    
    # Use the GLOBAL_OCEAN_PORTS list for routing calculations
    for port in GLOBAL_OCEAN_PORTS:
        port_coords = (port["lat"], port["lon"])
        distance_km = geopy.distance.distance(float_coords, port_coords).km
        distances.append({
            "name": port["name"],
            "lat": port["lat"],
            "lon": port["lon"],
            "distance_from_float": round(distance_km, 2)
        })
            
    # Sort by distance and return the top 'num_ports'
    distances.sort(key=lambda x: x['distance_from_float'])
    return distances[:num_ports]


def render_map_with_route(
    float_df: pd.DataFrame, 
    float_id: str, 
    dest_name: str, 
    t_func: callable
):
    """
    Renders a map showing float location, the 4 nearest ports, and 4 corresponding routes to the destination.
    The primary route (nearest port) is highlighted in red.
    """
    if float_df.empty:
        st.warning("No data for the specified Float ID was found. Cannot render map.")
        return

    # Check for required columns and valid data
    if 'latitude' not in float_df.columns or 'longitude' not in float_df.columns or float_df['latitude'].empty:
        st.warning("Data for the specified Float ID does not contain valid latitude and/or longitude. Cannot render map.")
        return
        
    # Get dynamic float location
    float_lat = float_df['latitude'].iloc[0]
    float_lon = float_df['longitude'].iloc[0]
    
    # Get the top 4 nearest ports (1 primary + 3 alternates)
    nearest_ports = find_nearest_ports(float_lat, float_lon, num_ports=4)
    
    if not nearest_ports:
        st.error("No nearest port could be found for the float's location.")
        return

    # Find destination port coordinates in the GLOBAL list
    dest_port = next((p for p in GLOBAL_OCEAN_PORTS if dest_name.lower() in p["name"].lower()), None)

    if not dest_port:
        st.error(f"Destination port '{dest_name}' not found in the available port list.")
        return

    fig = go.Figure()
    route_details = []

    # 1. Add float marker (Start) - Enhanced hover text
    fig.add_trace(go.Scattermapbox(
        lat=[float_lat], 
        lon=[float_lon], 
        mode='markers', 
        marker=go.scattermapbox.Marker(size=14, color='orange', symbol='circle'),
        name=f"Float ID: {float_id}", 
        text=[f"**Float ID:** {float_id}<br>**Location:** {float_lat:.2f}, {float_lon:.2f}<br>**Nearest Port:** {nearest_ports[0]['name']}"],
        hoverinfo='text' # Ensure hover is active
    ))

    # 2. Add all ports as markers
    port_lats = [p['lat'] for p in GLOBAL_OCEAN_PORTS]
    port_lons = [p['lon'] for p in GLOBAL_OCEAN_PORTS]
    port_names = [p['name'] for p in GLOBAL_OCEAN_PORTS]
    port_hover_text = [f"**Port:** {name}<br>**Location:** {lat:.2f}, {lon:.2f}" for name, lat, lon in zip(port_names, port_lats, port_lons)]
    
    fig.add_trace(go.Scattermapbox(
        lat=port_lats, 
        lon=port_lons, 
        mode='markers', 
        marker=go.scattermapbox.Marker(size=10, color='blue', symbol='square'),
        name="Ports",
        text=port_hover_text,
        hoverinfo='text' # Ensure hover is active
    ))

    # 3. Draw multiple route lines (Primary in Red, Alternates in Gray) - Enhanced hover for ALL routes
    for i, port in enumerate(nearest_ports):
        is_primary = (i == 0)
        color = 'red' if is_primary else 'gray'
        line_width = 3 if is_primary else 1.5
        
        # Distance from port to destination
        distance_port_to_dest = geopy.distance.distance(
            (port['lat'], port['lon']), 
            (dest_port['lat'], dest_port['lon'])
        ).km
        total_distance = port['distance_from_float'] + distance_port_to_dest
        
        route_text_float_to_port = f"**Float to Port (Path {i+1})**<br>From Float ID: {float_id}<br>To Port: {port['name']}<br>Distance: {port['distance_from_float']:.2f} km"
        route_text_port_to_dest = f"**Port to Destination (Path {i+1})**<br>From Port: {port['name']}<br>To Destination: {dest_name}<br>Distance: {distance_port_to_dest:.2f} km"
        
        # CRITICAL CHANGE: hoverinfo is now 'text' for all routes
        hover_config = 'text' 

        # Line 1: Float to Port
        fig.add_trace(go.Scattermapbox(
            lat=[float_lat, port['lat']],
            lon=[float_lon, port['lon']],
            mode='lines',
            line=go.scattermapbox.Line(width=line_width, color=color),
            name=f"Path {i+1} Start: {port['name']}" if is_primary else None,
            text=[route_text_float_to_port, route_text_float_to_port],
            hoverinfo=hover_config 
        ))
        
        # Line 2: Port to Destination
        fig.add_trace(go.Scattermapbox(
            lat=[port['lat'], dest_port['lat']],
            lon=[port['lon'], dest_port['lon']],
            mode='lines',
            line=go.scattermapbox.Line(width=line_width, color=color),
            name=f"Route: {port['name']} to {dest_name}" if is_primary else None,
            text=[route_text_port_to_dest, route_text_port_to_dest],
            hoverinfo=hover_config
        ))

        route_details.append({
            "name": port['name'],
            "total_distance": round(total_distance, 2),
            "distance_to_port": port['distance_from_float'],
            "is_primary": is_primary
        })

    # Update map layout
    fig.update_layout(
        mapbox_style="open-street-map",
        mapbox_center={"lat": float_lat, "lon": float_lon}, # Center map on the float's location
        mapbox_zoom=2,
        title=f"Float ID {float_id} to {dest_name} (Primary Route + 3 Alternates)",
        showlegend=False, 
        margin={"r":0,"t":40,"l":0,"b":0}
    )
    
    st.plotly_chart(fig, use_container_width=True)

    # Summary and instructions
    st.markdown(f"""
    ### Route Information (4 Shortest Paths)
    * **Float ID:** `{float_id}`
    * **Destination Port:** `{dest_name}`
    
    The system automatically detects the current location of **Float ID {float_id}** and calculates the total estimated distance to **`{dest_name}`** via the four nearest ports.
    
    | Path Option | Transfer Port | Total Distance (km) | Instruction |
    |:------------|:--------------|:--------------------|:------------|
    | **Primary (Red)** | **{route_details[0]['name']}** | **{route_details[0]['total_distance']}** | Go **{route_details[0]['distance_to_port']} km** to port, then continue to destination. |
    | Alternate 1 (Gray) | {route_details[1]['name']} | {route_details[1]['total_distance']} | Backup path via {route_details[1]['name']}. |
    | Alternate 2 (Gray) | {route_details[2]['name']} | {route_details[2]['total_distance']} | Backup path via {route_details[2]['name']}. |
    | Alternate 3 (Gray) | {route_details[3]['name']} | {route_details[3]['total_distance']} | Backup path via {route_details[3]['name']}. |
    
    ***
    
    **Note:** All paths are Great-Circle distances. You should select an alternate route if the primary (red) port is affected by weather or closures.
    """)