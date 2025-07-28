import streamlit as st
import openrouteservice
import folium
from streamlit_folium import st_folium

st.title("Mapa de ruta Bilbao → Vitoria")
ciudades = ["Bilbao", "Logroño", "Haro", "Vitoria", "Miranda"]
origen_ciudad = st.selectbox("Selecciona ciudad de origen", ciudades, key="origen")
destino_ciudad = st.selectbox("Selecciona ciudad de destino", ciudades, key="destino")

def obtener_coordenadas(ciudad):
    ciudad = ciudad.lower()
    coordenadas = {
        "vitoria": [-2.67268, 42.84998],
        "miranda": [-2.947, 42.684],
        "haro": [-2.8476, 42.57634],
        "logroño": [-2.44541, 42.46712],
        "bilbao": [-2.93341, 43.26035],
    }
    return coordenadas.get(ciudad, None)
# Coordenadas en formato [lon, lat]
origen = obtener_coordenadas(origen_ciudad)   # Bilbao
destino = obtener_coordenadas(destino_ciudad) # Vitoria-Gasteiz

# Cliente ORS
client = openrouteservice.Client(key="eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImJhZjE1ZWE5ZDZlMzQ5MThhOGE4MmJmMDQ2NzUxMTFjIiwiaCI6Im11cm11cjY0In0=")  # ← pon tu clave aquí

# Calcular ruta
coords = [origen, destino]
ruta = client.directions(coords, profile='driving-car', format='geojson')

# Extraer datos
geometry = ruta['features'][0]['geometry']
distancia = ruta['features'][0]['properties']['segments'][0]['distance'] / 1000
duracion = ruta['features'][0]['properties']['segments'][0]['duration'] / 60


# Mostrar datos
st.success(f"🚗 Distancia: {distancia:.2f} km")
st.success(f"⏱️ Duración estimada: {duracion:.1f} minutos")

# Crear mapa
centro = [(origen[1] + destino[1]) / 2, (origen[0] + destino[0]) / 2]
mapa = folium.Map(location=centro, zoom_start=9)

# Añadir ruta como GeoJSON completo
folium.GeoJson({
    "type": "Feature",
    "geometry": geometry,
    "properties": {}
}, name="Ruta").add_to(mapa)

# Añadir marcadores
folium.Marker(location=[origen[1], origen[0]], popup="Bilbao", icon=folium.Icon(color="green")).add_to(mapa)
folium.Marker(location=[destino[1], destino[0]], popup="Vitoria", icon=folium.Icon(color="red")).add_to(mapa)

# Mostrar mapa
st_folium(mapa, width=700, height=500)

# Asumiendo que tienes múltiples geometrías
#rutas = [geometry1, geometry2, geometry3]

#for i, geo in enumerate(rutas, start=1):
    #folium.GeoJson({
        #"type": "Feature",
        #"geometry": geo,
        #"properties": {}
    #}, name=f"Ruta {i}").add_to(mapa)
