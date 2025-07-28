import openrouteservice
from itertools import product
import time

# Diccionario de coordenadas [lon, lat]
ciudades_coords = {
    "haro": [-2.858152511919005, 42.5681060494229],
    "sto. domingo": [-2.950749636445161, 42.433119817282204],
    "durana": [-2.639513912965261, 42.88702626937825],
    "vitoria": [-2.6700945850372797, 42.83740036472884],
    "urdiain": [-2.138824319888948, 42.889614724865645],
    "logroño": [-2.4478865559684446, 42.45013177767869],
    "san vicente": [-2.756225378311136, 42.55723123763941],
    "alsasua": [-2.160411690717142, 42.892317105968665],
    "nanclares": [-2.8168162684239704, 42.815165330083616],
    "salinas": [-2.9882562588873665, 42.80254330447877],
    "miranda": [-2.963886889611098, 42.67981995425053],
    "sotes": [-2.6042157809448154, 42.39728023698068],
    "nalda": [-2.4836896934940373, 42.33454755287178],
    "pradejón": [-2.065080895522403, 42.33162748891024],
    "el rasillo": [-2.7015883235318703, 42.19476099225876],
    "nieva": [-2.6669882496729835, 42.21901538839893],
    "cenicero": [-2.632611302334742, 42.48705296252269],
    "laguardia": [-2.5766050847639863, 42.54642310684659],
    "agoncillo": [-2.2943488735734396, 42.449633829721435],
    "briones": [-2.780999982678883, 42.54363626665786],
    "najera": [-2.739775456567488, 42.41516740455801],
    "sesma": [-2.084939920137933, 42.475966103233354],
    "lerín": [-1.9662847839221445, 42.483451147662834],
    "los arcos": [-2.1932569768030103, 42.573982646482136],
    "araia": [-2.313917076959883, 42.88686325403397],
    "fuenmayor": [-2.555735355173662, 42.46763096774849],
}

# Cliente ORS
client = openrouteservice.Client(key="eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImJhZjE1ZWE5ZDZlMzQ5MThhOGE4MmJmMDQ2NzUxMTFjIiwiaCI6Im11cm11cjY0In0=")

# Configuración de bloques
tamano_bloque = 40
pausa_entre_peticiones = 2.5   # segundos entre llamadas individuales
pausa_entre_bloques = 60       # segundos entre bloques para estabilidad

# Combinaciones sin trayectos a uno mismo
ciudades = list(ciudades_coords.keys())
pares = [(origen, destino) for origen, destino in product(ciudades, ciudades) if origen != destino]

# Lista para guardar resultados
lista_tiempos = []

# Procesar en bloques
for i in range(0, len(pares), tamano_bloque):
    bloque = pares[i:i + tamano_bloque]
    print(f"\n🚚 Procesando bloque {i // tamano_bloque + 1} / {(len(pares) + tamano_bloque - 1) // tamano_bloque}")

    for origen, destino in bloque:
        coord_origen = ciudades_coords[origen]
        coord_destino = ciudades_coords[destino]
        try:
            ruta = client.directions([coord_origen, coord_destino], profile='driving-car', format='geojson')
            duracion_min = ruta['features'][0]['properties']['segments'][0]['duration'] / 60
            lista_tiempos.append({
                'origen': origen,
                'destino': destino,
                'tiempo_min': round(duracion_min, 2)
            })
            print(f"✅ {origen} → {destino}: {round(duracion_min, 2)} min")
            time.sleep(pausa_entre_peticiones)
        except Exception as e:
            print(f"⚠️ Error entre {origen} ➡ {destino}: {e}")

    print(f"🧊 Pausa de {pausa_entre_bloques} segundos antes del siguiente bloque...")
    time.sleep(pausa_entre_bloques)

# Mostrar los resultados finales
print("\n✅ Cálculo completado. Tiempos registrados:")
for entrada in lista_tiempos:
    print(f"{entrada['origen']} → {entrada['destino']}: {entrada['tiempo_min']} min")
