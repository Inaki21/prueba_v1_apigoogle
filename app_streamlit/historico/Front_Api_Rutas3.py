import streamlit as st
import pandas as pd
import openrouteservice
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta

# Cargar CSV
# Usamos st.cache_data para cargar el CSV solo una vez
@st.cache_data
def load_data(path):
    df = pd.read_csv(path)
    df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True)
    df['AñoSemana'] = df['Fecha'].dt.strftime('%Y-W%U')
    return df

df_concatenado = load_data("DatasetsRutas/archivo_concatenado.csv")

# --- Modificación para la selección semanal ---

# Obtener todas las combinaciones únicas de año y semana
semanas_disponibles = sorted(df_concatenado['AñoSemana'].unique())

# Crear etiquetas más amigables para el selectbox
opciones_semana = []
for as_str in semanas_disponibles:
    # Encontrar la primera fecha real en el dataframe para esa semana
    fechas_en_semana_df = df_concatenado[df_concatenado['AñoSemana'] == as_str]['Fecha']
    if not fechas_en_semana_df.empty:
        fechas_en_semana = fechas_en_semana_df.min()
        # Calcular la fecha de inicio de la semana (lunes)
        inicio_semana = fechas_en_semana - timedelta(days=fechas_en_semana.weekday())
        fin_semana = inicio_semana + timedelta(days=6)
        opciones_semana.append(f"Semana {int(as_str.split('-W')[1])} ({inicio_semana.strftime('%d %b')} - {fin_semana.strftime('%d %b %Y')})")
    else:
        opciones_semana.append(f"Semana {int(as_str.split('-W')[1])} (Fechas no disponibles)")


# Selector de semana
semana_seleccionada_label = st.selectbox("Selecciona una semana", options=opciones_semana)

# Obtener el 'AñoSemana' correspondiente a la selección
idx_semana_seleccionada = opciones_semana.index(semana_seleccionada_label)
semana_seleccionada_valor = semanas_disponibles[idx_semana_seleccionada]

# Filtrar rutas por semana completa
df_semana_completa = df_concatenado[df_concatenado["AñoSemana"] == semana_seleccionada_valor]

# --- Fin de la modificación para la selección semanal ---

# Obtener los días únicos dentro de la semana seleccionada y ordenarlos
dias_en_semana = sorted(df_semana_completa["Fecha"].dt.date.unique())

# Cliente de OpenRouteService 
# Asegúrate de que tu clave de API sea válida y esté bien protegida en un entorno de producción.
client = openrouteservice.Client(key="eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImJhZjE1ZWE5ZDZlMzQ5MThhOGE4MmJmMDQ2NzUxMTFjIiwiaCI6Im11cm11cjY0In0=") 

# Función para calcular la ruta con caché
@st.cache_data(show_spinner="Calculando ruta...")
def get_route_data(coords_list):
    """
    Calcula la ruta usando OpenRouteService.
    Esta función está cacheada para evitar llamadas repetidas a la API.
    """
    if len(coords_list) < 2:
        return None, None, None # No hay suficientes puntos para una ruta
    try:
        ruta = client.directions(coords_list, profile='driving-car', format='geojson')
        geometry = ruta['features'][0]['geometry']
        distance = ruta['features'][0]['properties']['segments'][0]['distance'] / 1000
        duration = ruta['features'][0]['properties']['segments'][0]['duration'] / 60
        return geometry, distance, duration
    except Exception as e:
        st.error(f"Error en OpenRouteService: {e}. Puede que la clave API haya excedido su límite o los puntos no sean válidos.")
        return None, None, None

# Iterar sobre cada día de la semana seleccionada
for dia_actual in dias_en_semana:
    st.subheader(f"📅 Ruta para el día: {dia_actual.strftime('%d/%m/%Y')}")

    # Filtrar rutas para el día actual
    df_ruta_dia = df_semana_completa[df_semana_completa["Fecha"].dt.date == dia_actual]

    # Eliminar coordenadas nulas para el día actual
    df_ruta_dia = df_ruta_dia.dropna(subset=["Lat", "Lon"])

    # Extraer coordenadas en formato [lon, lat] y ordenar
    df_ruta_dia = df_ruta_dia.sort_values(by='Horas') 
    coords_dia = df_ruta_dia[["Lon", "Lat"]].values.tolist()

    # Mostrar localidades para depuración del día
    st.write("📍 Localidades del día:", df_ruta_dia[["Localidad", "Lat", "Lon"]])

    # Obtener datos de la ruta usando la función cacheada
    geometry_dia, distancia_dia, duracion_dia = get_route_data(coords_dia)

    if geometry_dia is None:
        st.info(f"ℹ️ No hay suficientes localidades o hubo un error al calcular la ruta para el {dia_actual.strftime('%d/%m/%Y')}.")
    else:
        # Mostrar datos
        st.success(f"🚗 Distancia total estimada: {distancia_dia:.2f} km")
        st.success(f"⏱️ Duración estimada: {duracion_dia:.1f} minutos")

        # Crear mapa centrado para el día actual
        centro_dia = [df_ruta_dia["Lat"].mean(), df_ruta_dia["Lon"].mean()]
        mapa_dia = folium.Map(location=centro_dia, zoom_start=10)

        # Añadir ruta para el día actual
        folium.GeoJson(geometry_dia).add_to(mapa_dia)

        # Añadir marcadores para todas las localidades del día actual
        for _, fila in df_ruta_dia.iterrows():
            folium.Marker(
                location=[fila["Lat"], fila["Lon"]],
                popup=f"{fila['Localidad']} (Cliente: {fila['Cliente']})", 
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(mapa_dia)

        # Mostrar mapa para el día actual
        st_folium(mapa_dia, width=700, height=500, key=f"map_{dia_actual.strftime('%Y%m%d')}")

