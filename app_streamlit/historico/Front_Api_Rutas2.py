import streamlit as st
import pandas as pd
import openrouteservice
import folium
from streamlit_folium import st_folium

# Cargar CSV
df_concatenado = pd.read_csv("DatasetsRutas/archivo_concatenado.csv")

# Convertir columna de fecha
df_concatenado["Fecha"] = pd.to_datetime(df_concatenado["Fecha"], dayfirst=True)

# Selector de fecha
fecha_seleccionada = st.date_input("Selecciona una fecha", value=df_concatenado["Fecha"].min().date())

# Filtrar rutas por fecha
df_ruta = df_concatenado[df_concatenado["Fecha"].dt.date == fecha_seleccionada]

# Eliminar coordenadas nulas
df_ruta = df_ruta.dropna(subset=["Lat", "Lon"])

# Extraer coordenadas en formato [lon, lat]
coords = df_ruta[["Lon", "Lat"]].values.tolist()

# Mostrar coordenadas para depuración
st.write("📍 Localidades en la ruta:", df_ruta[["Localidad", "Lat", "Lon"]])

# Verificar que haya al menos dos puntos
if len(coords) < 2:
    st.warning("⚠️ Se necesitan al menos dos localidades para calcular una ruta.")
else:
    # Cliente de OpenRouteService 
    client = openrouteservice.Client(key="eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImJhZjE1ZWE5ZDZlMzQ5MThhOGE4MmJmMDQ2NzUxMTFjIiwiaCI6Im11cm11cjY0In0=")  
    
    try:
        # Calcular ruta
        ruta = client.directions(coords, profile='driving-car', format='geojson')

        # Extraer datos
        geometry = ruta['features'][0]['geometry']
        distancia = ruta['features'][0]['properties']['segments'][0]['distance'] / 1000
        duracion = ruta['features'][0]['properties']['segments'][0]['duration'] / 60

        # Mostrar datos
        st.success(f"🚗 Distancia total: {distancia:.2f} km")
        st.success(f"⏱️ Duración estimada: {duracion:.1f} minutos")

        # Crear mapa centrado
        centro = [df_ruta["Lat"].mean(), df_ruta["Lon"].mean()]
        mapa = folium.Map(location=centro, zoom_start=10)

        # Añadir ruta
        folium.GeoJson(ruta).add_to(mapa)

        # Añadir marcadores para todas las localidades
        for _, fila in df_ruta.iterrows():
            folium.Marker(
                location=[fila["Lat"], fila["Lon"]],
                popup=fila["Localidad"],
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(mapa)

        # Mostrar mapa
        st_folium(mapa, width=700, height=500)

    except Exception as e:
        st.error(f"❌ Error al calcular la ruta: {e}")
