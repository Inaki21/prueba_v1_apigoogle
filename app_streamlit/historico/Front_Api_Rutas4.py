import streamlit as st
import pandas as pd
import openrouteservice
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta

# Define the fixed origin point (company location)
# Define el punto de origen fijo (ubicación de la empresa)
ORIGIN_COORDS = [-2.8282690950218656, 42.54387913161117] # [Lon, Lat]
ORIGIN_NAME = "Empresa (Ollauri, La Rioja)"

# Load CSV data
# Cargar datos CSV
@st.cache_data
def load_data(path):
    df = pd.read_csv(path)
    df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True)
    df['AñoSemana'] = df['Fecha'].dt.strftime('%Y-W%U')
    return df

df_concatenado = load_data("DatasetsRutas/archivo_concatenado.csv")

# --- Modification for weekly selection ---
# --- Modificación para la selección semanal ---

# Get all unique year-week combinations
# Obtener todas las combinaciones únicas de año-semana
semanas_disponibles = sorted(df_concatenado['AñoSemana'].unique())

# Create user-friendly labels for the selectbox
# Crear etiquetas amigables para el usuario para el selectbox
opciones_semana = []
for as_str in semanas_disponibles:
    # Find the earliest actual date in the dataframe for that week
    # Encontrar la fecha más temprana real en el dataframe para esa semana
    fechas_en_semana_df = df_concatenado[df_concatenado['AñoSemana'] == as_str]['Fecha']
    if not fechas_en_semana_df.empty:
        fechas_en_semana = fechas_en_semana_df.min()
        # Calculate the start date of the week (Monday)
        # Calcular la fecha de inicio de la semana (Lunes)
        inicio_semana = fechas_en_semana - timedelta(days=fechas_en_semana.weekday())
        fin_semana = inicio_semana + timedelta(days=6)
        opciones_semana.append(f"Semana {int(as_str.split('-W')[1])} ({inicio_semana.strftime('%d %b')} - {fin_semana.strftime('%d %b %Y')})")
    else:
        opciones_semana.append(f"Semana {int(as_str.split('-W')[1])} (Fechas no disponibles)")

# Week selector
# Selector de semana
semana_seleccionada_label = st.selectbox("Selecciona una semana", options=opciones_semana)

# Get the corresponding 'AñoSemana' value from the selection
# Obtener el valor 'AñoSemana' correspondiente a la selección
idx_semana_seleccionada = opciones_semana.index(semana_seleccionada_label)
semana_seleccionada_valor = semanas_disponibles[idx_semana_seleccionada]

# Filter routes for the entire selected week
# Filtrar rutas para la semana completa seleccionada
df_semana_completa = df_concatenado[df_concatenado["AñoSemana"] == semana_seleccionada_valor]

# --- End of weekly selection modification ---
# --- Fin de la modificación para la selección semanal ---

# Get unique days within the selected week and sort them
# Obtener los días únicos dentro de la semana seleccionada y ordenarlos
dias_en_semana = sorted(df_semana_completa["Fecha"].dt.date.unique())

# OpenRouteService client
# Cliente de OpenRouteService
# Ensure your API key is valid and protected in a production environment.
# Asegúrate de que tu clave de API sea válida y esté protegida en un entorno de producción.
client = openrouteservice.Client(key="eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImJhZjE1ZWE5ZDZlMzQ5MThhOGE4MmJmMDQ2NzUxMTFjIiwiaCI6Im11cm11cjY0In0=") 

# Function to calculate route geometry and distance with caching
# Función para calcular la geometría y distancia de la ruta con caché
@st.cache_data(show_spinner="Calculando geometría de ruta...")
def get_route_geometry_and_distance(coords_list_for_ors):
    """
    Calculates the route geometry and distance using OpenRouteService.
    This function is cached to avoid repeated API calls.
    """
    if len(coords_list_for_ors) < 2:
        return None, None
    try:
        ruta = client.directions(coords_list_for_ors, profile='driving-car', format='geojson')
        geometry = ruta['features'][0]['geometry']
        distance = ruta['features'][0]['properties']['segments'][0]['distance'] / 1000 # Keep ORS distance
        return geometry, distance
    except Exception as e:
        st.error(f"Error en OpenRouteService al obtener geometría: {e}. Puede que la clave API haya excedido su límite o los puntos no sean válidos.")
        return None, None

# Iterate over each day of the selected week
# Iterar sobre cada día de la semana seleccionada
for dia_actual in dias_en_semana:
    st.subheader(f"📅 Ruta para el día: {dia_actual.strftime('%d/%m/%Y')}")

    # Filter routes for the current day
    # Filtrar rutas para el día actual
    df_ruta_dia = df_semana_completa[df_semana_completa["Fecha"].dt.date == dia_actual]

    # Remove null coordinates for the current day
    # Eliminar coordenadas nulas para el día actual
    df_ruta_dia = df_ruta_dia.dropna(subset=["Lat", "Lon"])

    # Extract coordinates in [lon, lat] format and sort them
    # Extraer coordenadas en formato [lon, lat] y ordenarlas
    # Sort by 'Horas' to get a logical route order if no explicit order field exists.
    # Ordenar por 'Horas' para obtener un orden lógico de la ruta si no existe un campo de orden explícito.
    df_ruta_dia = df_ruta_dia.sort_values(by='Horas') 
    
    # Prepend the origin coordinates to the daily route coordinates and append for return trip
    # Anteponer las coordenadas de origen al inicio y al final de la ruta diaria
    coords_dia = [ORIGIN_COORDS] + df_ruta_dia[["Lon", "Lat"]].values.tolist() + [ORIGIN_COORDS]

    # Create a DataFrame for the origin point for display purposes
    # Crear un DataFrame para el punto de origen con fines de visualización
    origin_display_df = pd.DataFrame([{'Localidad': ORIGIN_NAME, 'Lat': ORIGIN_COORDS[1], 'Lon': ORIGIN_COORDS[0]}])
    
    # Concatenate the origin DataFrame with the daily route DataFrame for display
    # Concatenar el DataFrame de origen con el DataFrame de la ruta diaria para visualización
    # Include the origin again at the end to represent the return trip
    # Incluir el origen de nuevo al final para representar el viaje de regreso
    displayed_locations = pd.concat([origin_display_df, df_ruta_dia[["Localidad", "Lat", "Lon"]], origin_display_df], ignore_index=True)

    # Display locations for debugging the day
    # Mostrar ubicaciones para depuración del día
    st.write("📍 Localidades del día (incluyendo origen y regreso):", displayed_locations)

    # Get route geometry and distance using the cached function
    # Obtener geometría y distancia de la ruta usando la función cacheada
    geometry_dia, distancia_dia = get_route_geometry_and_distance(coords_dia)

    if geometry_dia is None:
        st.info(f"ℹ️ No hay suficientes localidades o hubo un error al calcular la ruta para el {dia_actual.strftime('%d/%m/%Y')}.")
    else:
        # Get travel duration from CSV (assuming it's the total round trip for the day)
        # Obtener duración del desplazamiento desde el CSV (asumiendo que es el total de ida y vuelta para el día)
        # We take the value from the first row for the day, as it should be consistent for all entries of that day's route.
        duracion_viaje_dia_csv = df_ruta_dia['Tiempo_Desplazamiento_min'].iloc[0]

        # Calculate total work hours for the day
        # Calcular el total de horas de trabajo para el día
        total_horas_trabajo_dia = df_ruta_dia['Horas'].sum()

        # Calculate total estimated duration for the day (travel from CSV + work)
        # Calcular la duración total estimada para el día (viaje del CSV + trabajo)
        total_duracion_dia_min = duracion_viaje_dia_csv + (total_horas_trabajo_dia * 60) # Sum travel in minutes + work in minutes

        # Convert total daily duration to hours
        # Convertir la duración total del día a horas
        total_duracion_dia_horas = total_duracion_dia_min / 60


        # Display data
        # Mostrar datos
        st.success(f"🚗 Distancia total estimada (ida y vuelta): {distancia_dia:.2f} km")
        st.success(f"⏱️ Duración estimada del viaje (ida y vuelta): {duracion_viaje_dia_csv:.1f} minutos")
        st.success(f"👷 Duración estimada de trabajo en localidades: {total_horas_trabajo_dia:.1f} horas")
        st.success(f"⏳ **Duración total estimada del día (viaje + trabajo): {total_duracion_dia_horas:.1f} horas**")


        # Create map centered for the current day
        # Crear mapa centrado para el día actual
        # Center the map considering both origin and destinations
        # Centrar el mapa considerando tanto el origen como los destinos
        all_lats = [ORIGIN_COORDS[1]] + df_ruta_dia["Lat"].tolist() + [ORIGIN_COORDS[1]]
        all_lons = [ORIGIN_COORDS[0]] + df_ruta_dia["Lon"].tolist() + [ORIGIN_COORDS[0]]
        
        centro_dia = [sum(all_lats) / len(all_lats), sum(all_lons) / len(all_lons)]
        mapa_dia = folium.Map(location=centro_dia, zoom_start=10)

        # Add route for the current day
        # Añadir ruta para el día actual
        folium.GeoJson(geometry_dia).add_to(mapa_dia)

        # Add marker for the origin point (start and end)
        # Añadir marcador para el punto de origen (inicio y fin)
        folium.Marker(
            location=[ORIGIN_COORDS[1], ORIGIN_COORDS[0]],
            popup=ORIGIN_NAME + " (Inicio y Fin)",
            icon=folium.Icon(color="green", icon="home") # Green icon for origin
        ).add_to(mapa_dia)

        # Add markers for all destinations of the current day
        # Añadir marcadores para todos los destinos del día actual
        for _, fila in df_ruta_dia.iterrows():
            folium.Marker(
                location=[fila["Lat"], fila["Lon"]],
                popup=f"{fila['Localidad']} (Cliente: {fila['Cliente']})", 
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(mapa_dia)

        # Display map for the current day
        # Mostrar mapa para el día actual
        st_folium(mapa_dia, width=700, height=500, key=f"map_{dia_actual.strftime('%Y%m%d')}")
