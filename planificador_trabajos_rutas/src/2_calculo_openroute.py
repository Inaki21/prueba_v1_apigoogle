import openrouteservice
from itertools import product
import time
import pandas as pd

# Diccionario de coordenadas [lon, lat]
ciudades_coords = {
    "haro": [-2.85815, 42.56810],
    "sto. domingo": [-2.95075, 42.43312],
    "durana": [-2.63951, 42.88703],
    "vitoria": [-2.67009, 42.83740],
    "urdiain": [-2.13882, 42.88961],
    "logroño": [-2.44789, 42.45013],
    "san vicente": [-2.75623, 42.55723],
    "alsasua": [-2.16041, 42.89232],
    "nanclares": [-2.81682, 42.81517],
    "salinas": [-2.98826, 42.80254],
    "miranda": [-2.96389, 42.67982],
    "sotes": [-2.60422, 42.39728],
    "nalda": [-2.48369, 42.33455],
    "pradejón": [-2.06508, 42.33163],
    "el rasillo": [-2.70159, 42.19476],
    "nieva": [-2.66699, 42.21902],
    "cenicero": [-2.63261, 42.48705],
    "laguardia": [-2.57661, 42.54642],
    "agoncillo": [-2.29435, 42.44963],
    "briones": [-2.78100, 42.54364],
    "najera": [-2.73978, 42.41517],
    "sesma": [-2.08494, 42.47597],
    "lerín": [-1.96628, 42.48345],
    "los arcos": [-2.19326, 42.57398],
    "araia": [-2.31392, 42.88686],
    "fuenmayor": [-2.55574, 42.46763],
    "ollauri": [-2.8283530, 42.54371,]
}

# Cliente ORS
client = openrouteservice.Client(key="eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjY4ZDAwZGUxZWRiNTQwNTc5ZThlNmY2NGFjNDNmYzZkIiwiaCI6Im11cm11cjY0In0=")

# Configuración
tamano_bloque = 40
pausa_entre_peticiones = 2.5
pausa_entre_bloques = 60

# Inicializar matriz vacía con pandas
ciudades = list(ciudades_coords.keys())
matriz_tiempos = pd.DataFrame(index=ciudades, columns=ciudades)

# Procesar en bloques
pares = [(o, d) for o, d in product(ciudades, ciudades) if o != d]

for i in range(0, len(pares), tamano_bloque):
    bloque = pares[i:i + tamano_bloque]
    print(f"\n🚚 Procesando bloque {i // tamano_bloque + 1} / {(len(pares) + tamano_bloque - 1) // tamano_bloque}")

    for origen, destino in bloque:
        coord_o = ciudades_coords[origen]
        coord_d = ciudades_coords[destino]
        try:
            ruta = client.directions([coord_o, coord_d], profile='driving-car', format='geojson')
            tiempo_min = ruta['features'][0]['properties']['segments'][0]['duration'] / 60
            matriz_tiempos.at[origen, destino] = round(tiempo_min, 2)
            print(f"✅ {origen} → {destino}: {round(tiempo_min, 2)} min")
            time.sleep(pausa_entre_peticiones)
        except Exception as e:
            print(f"⚠️ Error entre {origen} ➡ {destino}: {e}")
            matriz_tiempos.at[origen, destino] = None

    print(f"🧊 Pausa de {pausa_entre_bloques} segundos antes del siguiente bloque...")
    time.sleep(pausa_entre_bloques)

# Mostrar matriz final
print("\n✅ Cálculo completado. Matriz de tiempos:")
print(matriz_tiempos)

# Guardar en CSV
matriz_tiempos.to_csv("matriz_tiempos_final.csv", encoding='utf-8', index=True)