import streamlit as st
import pandas as pd
import openrouteservice
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta
import re # Import regex for parsing the route string

# --- Configuration ---
# Define the fixed origin point (company location)
ORIGIN_COORDS = [-2.8282690950218656, 42.54387913161117] # [Lon, Lat] for ORS/Folium
ORIGIN_NAME = "Empresa (Ollauri, La Rioja)"

# IMPORTANT: Replace with your actual OpenRouteService API key
# Asegúrate de que tu clave de API sea válida y esté protegida en un entorno de producción.
API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImM2ZDM4MDA4NTE1OTQ4Njc4ODZmNGMyZDJhZmMwZDZiIiwiaCI6Im11cm11cjY0In0="
client = openrouteservice.Client(key=API_KEY)

# --- Data Loading ---
@st.cache_data
def load_data(path):
    """
    Loads the optimized routes CSV.
    Ensures 'Fecha' is datetime and other columns are correctly handled.
    """
    try:
        df = pd.read_csv(path, sep=',')
        df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True)
        # Ensure 'Localidad' is capitalized for consistent matching
        df['Localidad'] = df['Localidad'].astype(str).str.title()
        return df
    except FileNotFoundError:
        st.error(f"Error: El archivo '{path}' no se encontró. Asegúrate de que el CSV esté en la misma carpeta.")
        st.stop()
    except Exception as e:
        st.error(f"Error al cargar los datos: {e}")
        st.stop()

# Load the new annual CSV file
df_anual_rutas = load_data("rutas_trabajo_anual_2025_optimizadas_con_clusters.csv")

# --- Streamlit App Layout ---
st.set_page_config(layout="wide", page_title="Planificador de Rutas Anual")

st.title("🗺️ Visualizador del Plan de Rutas Anual")

# --- Week Selection ---
# Create 'AñoSemana' for selection (Year-Week format, e.g., "2025-W01")
df_anual_rutas['AñoSemana'] = df_anual_rutas['Fecha'].dt.strftime('%Y-W%U')

# Get all unique year-week combinations
semanas_disponibles_valores = sorted(df_anual_rutas['AñoSemana'].unique())

# Create user-friendly labels for the selectbox
opciones_semana = []
for as_str in semanas_disponibles_valores:
    # Find the earliest actual date in the dataframe for that week to determine the start/end
    fechas_en_semana_df = df_anual_rutas[df_anual_rutas['AñoSemana'] == as_str]['Fecha']
    if not fechas_en_semana_df.empty:
        # Get the actual first Monday of the week for a robust label
        some_date_in_week = fechas_en_semana_df.min()
        inicio_semana = some_date_in_week - timedelta(days=some_date_in_week.weekday())
        fin_semana = inicio_semana + timedelta(days=6)
        
        # Get the week number and month name from the CSV data
        first_row_for_week = df_anual_rutas[df_anual_rutas['AñoSemana'] == as_str].iloc[0]
        semana_num_csv = int(first_row_for_week['Semana'])
        mes_nombre_csv = first_row_for_week['Mes']

        opciones_semana.append(f"Semana {semana_num_csv} de {mes_nombre_csv} ({inicio_semana.strftime('%d %b')} - {fin_semana.strftime('%d %b %Y')})")
    else:
        opciones_semana.append(f"Semana {as_str.split('-W')[1]} (Fechas no disponibles)")

semana_seleccionada_label = st.selectbox("Selecciona una semana para visualizar", options=opciones_semana)

# Get the corresponding 'AñoSemana' value from the selection
idx_semana_seleccionada = opciones_semana.index(semana_seleccionada_label)
semana_seleccionada_valor = semanas_disponibles_valores[idx_semana_seleccionada]

# Filter data for the entire selected week
df_semana_completa = df_anual_rutas[df_anual_rutas["AñoSemana"] == semana_seleccionada_valor].copy()

# Get unique days within the selected week and sort them
dias_en_semana = sorted(df_semana_completa["Fecha"].dt.date.unique())


### ORS Route Geometry Function

@st.cache_data(show_spinner="Calculando geometría de ruta (puede tardar si hay muchas rutas)...")
def get_route_geometry_and_distance(coords_list_for_ors):
    """
    Calculates the route geometry and distance using OpenRouteService.
    This function is cached to avoid repeated API calls.
    Coords list should be [Lon, Lat].
    """
    if len(coords_list_for_ors) < 2:
        return None, None
    try:
        # Ensure coordinates are floats
        coords_list_for_ors = [[float(lon), float(lat)] for lon, lat in coords_list_for_ors]

        ruta = client.directions(coords_list_for_ors, profile='driving-car', format='geojson')
        geometry = ruta['features'][0]['geometry']
        distance = ruta['features'][0]['properties']['segments'][0]['distance'] / 1000 # Distance in km
        return geometry, distance
    except openrouteservice.exceptions.ApiError as e:
        st.error(f"Error en OpenRouteService al obtener geometría para la ruta: {e}. "
                 f"Puede que la clave API haya excedido su límite, los puntos no sean válidos, "
                 f"o no exista una ruta para los puntos dados. Coordenadas enviadas: {coords_list_for_ors}")
        return None, None
    except Exception as e:
        st.error(f"Error inesperado al obtener geometría de ruta: {e}")
        return None, None



### Main Daily Route Display Loop

for dia_actual in dias_en_semana:
    st.markdown("---") # Horizontal line for separation
    st.subheader(f"📅 Ruta para el día: {dia_actual.strftime('%A, %d/%m/%Y')}")

    # Filter data for the current day
    df_ruta_dia = df_semana_completa[df_semana_completa["Fecha"].dt.date == dia_actual].copy()

    if df_ruta_dia.empty:
        st.info(f"ℹ️ No hay rutas planificadas para el {dia_actual.strftime('%d/%m/%Y')}.")
        continue

    # Get unique route sequence and total travel time for the day
    # Assuming these values are consistent across all rows for a given day
    full_route_string = df_ruta_dia['Secuencia_Ruta_Dia'].iloc[0]
    travel_time_min_csv = df_ruta_dia['Tiempo_Desplazamiento_Dia_min'].iloc[0]
    total_effective_work_hours = df_ruta_dia['Horas_Trabajo_Total_Dia'].iloc[0]
    total_journey_hours = df_ruta_dia['Jornada_Total_Horas'].iloc[0]
    
    # Parse the route string to get the ordered locality names (e.g., "Empresa ➔ Cliente A ➔ Cliente B ➔ Empresa")
    locality_names_in_order = [name.strip() for name in full_route_string.split('➔')]
    
    coords_for_ors_daily_route = [] # Stores [Lon, Lat] for ORS
    
    # This list will hold details for all markers to be added to the map
    markers_to_add = []

    # Map parsed locality names to their actual coordinates and prepare marker data
    for i, loc_name_display in enumerate(locality_names_in_order):
        # Handle the origin point
        if loc_name_display == ORIGIN_NAME:
            coords_for_ors_daily_route.append(ORIGIN_COORDS)
            # Add origin as the first marker for the route
            if not any(m['Type'] == 'Origin' for m in markers_to_add):
                markers_to_add.append({
                    'Localidad': ORIGIN_NAME,
                    'Lat': ORIGIN_COORDS[1],
                    'Lon': ORIGIN_COORDS[0],
                    'Type': 'Origin',
                    'Popup': f"<b>{ORIGIN_NAME}</b> (Inicio y Fin)"
                })
        else:
            # Find all client visits for this locality on this day
            # Use .str.lower() for robust matching
            matching_clients_today = df_ruta_dia[
                df_ruta_dia['Localidad'].str.lower() == loc_name_display.lower()
            ]

            if not matching_clients_today.empty:
                # Get the first set of coordinates for this locality for ORS routing
                # (assuming all clients in the same locality share the same Lat/Lon for routing purposes)
                client_row_coords = matching_clients_today.iloc[0]
                coords_for_ors_daily_route.append([client_row_coords['Lon'], client_row_coords['Lat']])
                
                # Prepare popup text for the marker, including all clients at this locality
                popup_text = f"<b>{client_row_coords['Localidad'].title()}</b>"
                for _, client_info in matching_clients_today.iterrows():
                    popup_text += f"<br>Cliente: {client_info['Cliente']} ({client_info['Horas_Trabajo_Cliente']:.1f}h)"
                    popup_text += f"<br>Cluster: {client_info['Cluster']}"

                # Add a marker for this locality if it hasn't been added yet
                # This ensures each unique physical location gets one marker with aggregated info
                if not any(m['Lat'] == client_row_coords['Lat'] and m['Lon'] == client_row_coords['Lon'] for m in markers_to_add):
                     markers_to_add.append({
                        'Localidad': client_row_coords['Localidad'],
                        'Lat': client_row_coords['Lat'],
                        'Lon': client_row_coords['Lon'],
                        'Type': 'Client',
                        'Popup': popup_text,
                        'Cluster': client_row_coords['Cluster'] # For consistent coloring
                    })
            else:
                st.warning(f"⚠️ Coordenadas no encontradas para '{loc_name_display}'. No se puede añadir al mapa.")

    # Get route geometry and distance using the cached function
    geometry_dia, distancia_dia = get_route_geometry_and_distance(coords_for_ors_daily_route)

    if geometry_dia is None:
        st.info(f"ℹ️ No se pudo calcular la ruta para el {dia_actual.strftime('%d/%m/%Y')}. Revisa los datos de coordenadas y la clave API.")
    else:
        st.success(f"⏱️ Duración estimada de viaje (ida y vuelta): **{travel_time_min_csv:.1f} minutos**")
        st.success(f"👷 Horas de trabajo efectivas en localidades: **{total_effective_work_hours:.1f} horas**")
        st.success(f"⏳ **Jornada total estimada del día (viaje + trabajo): {total_journey_hours:.1f} horas**")

        st.markdown(f"**Secuencia de Ruta:** {full_route_string}")

        # Create map centered on the route's bounds
        mapa_dia = folium.Map(location=[ORIGIN_COORDS[1], ORIGIN_COORDS[0]], zoom_start=9)

        # Add route polyline
        folium.GeoJson(geometry_dia).add_to(mapa_dia)

        # Add markers for all unique locations in the route sequence
        for loc_data in markers_to_add:
            if loc_data['Type'] == 'Origin':
                folium.Marker(
                    location=[loc_data['Lat'], loc_data['Lon']],
                    popup=loc_data['Popup'],
                    icon=folium.Icon(color="green", icon="home", prefix='fa')
                ).add_to(mapa_dia)
            else:
                # Cluster colors (matching the planner for consistency)
                cluster_colors = {
                    -1: 'black', 0: 'blue', 1: 'red', 2: 'green', 3: 'purple', 4: 'orange',
                    5: 'darkred', 6: 'lightblue', 7: 'cadetblue', 8: 'darkgreen',
                    9: 'darkblue', 10: 'lightgreen', 11: 'darkpurple', 12: 'pink',
                    13: 'gray', 14: 'lightgray', 15: 'beige', 16: 'darkblue', 17: 'lightred'
                }
                marker_color = cluster_colors.get(loc_data.get('Cluster'), 'blue') # Default to blue if cluster not found

                folium.Marker(
                    location=[loc_data['Lat'], loc_data['Lon']],
                    popup=loc_data['Popup'],
                    icon=folium.Icon(color=marker_color, icon="briefcase", prefix='fa') # Use briefcase icon for clients
                ).add_to(mapa_dia)
        
        # Fit map to bounds of the route geometry
        if geometry_dia and 'coordinates' in geometry_dia:
            # Extract all lat/lon from the geometry and fit bounds
            lons_route = [p[0] for p in geometry_dia['coordinates']]
            lats_route = [p[1] for p in geometry_dia['coordinates']]
            if lons_route and lats_route:
                mapa_dia.fit_bounds([[min(lats_route), min(lons_route)], [max(lats_route), max(lons_route)]])
            
        # Display map for the current day
        st_folium(mapa_dia, width=1000, height=600, key=f"map_{dia_actual.strftime('%Y%m%d')}")