import requests
import json
import time

def obtener_coordenadas_osm(lugar, user_agent="DesafioBootcampTheBridgeVitoria0725"):
    """
    Obtiene las coordenadas (latitud, longitud) de un lugar usando la API Nominatim de OpenStreetMap.

    Args:
        lugar (str): El nombre del lugar que se desea buscar (ej. "Sevilla", "Granada, Granada", "Calle Mayor 1, Madrid").
        user_agent (str): Un identificador para la aplicación, recomendado por Nominatim.

    Returns:
        tuple or None: Una tupla (latitud, longitud) si se encuentra el lugar, o None si no se encuentra.
    """
    base_url = "https://nominatim.openstreetmap.org/search?"
    params = {
        'q': lugar,
        'format': 'json',  # Queremos la respuesta en formato JSON
        'limit': 1,        # Solo el primer resultado
        'addressdetails': 1, # Para obtener detalles de la dirección si los hay
        'countrycodes': "es" # Sólo mostrará resultados de España 
    }
    headers = {
        'User-Agent': user_agent # identificador de la aplicación (p.ej., 'DesafioBootcampTheBridgeVitoria0725')
    }

    try:
        response = requests.get(base_url, params=params, headers=headers)
        response.raise_for_status()  # Lanza una excepción si la respuesta no es exitosa (4xx o 5xx)
        data = response.json()

        if data:
            # Nominatim devuelve una lista de resultados, tomamos el primero
            primer_resultado = data[0]
            latitud = primer_resultado.get('lat')
            longitud = primer_resultado.get('lon')
            nombre_encontrado = primer_resultado.get('display_name')

            print(f"Lugar encontrado: {nombre_encontrado}")
            return float(latitud), float(longitud)
        else:
            print(f"No se encontraron coordenadas para: '{lugar}'")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error al conectar con la API de OpenStreetMap: {e}")
        return None
    except json.JSONDecodeError:
        print("Error al decodificar la respuesta JSON.")
        return None
    finally:
        # Pausar un poco para respetar los límites de la API
        time.sleep(1) # Esperar 1 segundo entre solicitudes



# --- Ejemplo de uso ---
if __name__ == "__main__":
    # Ejemplos de lugares en España
    lugares_a_buscar = [
        "HARO,LA RIOJA",
        "STO. DOMINGO DE LA CALZADA, LA RIOJA",
        "DURANA, ALAVA",
        "HARO, LA RIOJA",
        "VITORIA, ALAVA",
        "URDIAIN, NAVARRA",
        "Ollauri, La Rioja",
        "Lugar que no existe XYZ" # Para probar un caso sin resultado
    ]

    print("--- Obteniendo coordenadas ---")
    for lugar in lugares_a_buscar:
        print(f"\nBuscando: '{lugar}'...")
        coords = obtener_coordenadas_osm(lugar, user_agent="MiScriptPythonGeocodingPersonal")
        if coords:
            lat, lon = coords
            print(f"  Latitud: {lat}, Longitud: {lon}")
        else:
            print(f"  No se pudieron obtener coordenadas para '{lugar}'.")

    print("\n--- Búsqueda finalizada ---")