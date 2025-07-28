from flask import Flask, jsonify, request
import pandas as pd
import openrouteservice as ors
from datetime import datetime, timedelta
from flask_cors import CORS
import re
# No longer need OrderedDict if returning a list of dicts
# from collections import OrderedDict

app = Flask(__name__)
CORS(app)

# --- Configuración y Constantes ---
ORIGIN_COORDS = [-2.8282690950218656, 42.54387913161117] # [Lon, Lat]
ORIGIN_NAME = "Empresa (Ollauri, La Rioja)"

# IMPORTANT: Reemplaza con tu clave de API de OpenRouteService
API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImM2ZDM4MDA4NTE1OTQ4Njc4ODZmNGMyZDJhZmMwZDZiIiwiaCI6Im11cm11cjY0In0="
ors_client = ors.Client(key=API_KEY)

# Ruta al archivo CSV generado por planificador_ors.py
CSV_PATH = 'rutas_trabajo_anual_2025_optimizadas_con_clusters.csv'

# --- Carga de Datos Global ---
df_anual_rutas = None # Inicializar como None

def load_data(path):
    """
    Carga los datos del CSV. Se llama una vez al inicio de la aplicación.
    """
    try:
        df = pd.read_csv(path, sep=',')
        df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True)
        df['Localidad'] = df['Localidad'].astype(str).str.title()
        df['AñoISO'], df['SemanaISO'], _ = zip(*df['Fecha'].apply(lambda x: x.isocalendar()))
        df['AñoSemanaISO'] = df.apply(lambda row: f"{row['AñoISO']}-W{row['SemanaISO']:02d}", axis=1)
        return df
    except FileNotFoundError:
        print(f"Error: El archivo '{path}' no se encontró. Asegúrate de que el CSV esté en la misma carpeta.")
        return pd.DataFrame() # Retorna un DataFrame vacío en caso de error
    except Exception as e:
        print(f"Error al cargar los datos: {e}")
        return pd.DataFrame()

# Cargar los datos al inicio de la aplicación
with app.app_context():
    df_anual_rutas = load_data(CSV_PATH)
    if df_anual_rutas.empty:
        print("Advertencia: No se pudieron cargar los datos de rutas. La API funcionará con datos vacíos.")

# --- Funciones Auxiliares ---
def get_route_geometry_and_distance_ors(coords_list_for_ors):
    """
    Calcula la geometría de la ruta y la distancia usando OpenRouteService.
    Las coordenadas deben estar en formato [Lon, Lat].
    """
    if len(coords_list_for_ors) < 2:
        return None, None
    try:
        coords_list_for_ors = [[float(lon), float(lat)] for lon, lat in coords_list_for_ors]
        ruta = ors_client.directions(coords_list_for_ors, profile='driving-car', format='geojson')
        geometry = ruta['features'][0]['geometry']
        distance = ruta['features'][0]['properties']['segments'][0]['distance'] / 1000 # Distancia en km
        return geometry, distance
    except ors.exceptions.ApiError as e:
        print(f"Error en OpenRouteService: {e}. Coords: {coords_list_for_ors}")
        return None, None
    except Exception as e:
        print(f"Error inesperado al obtener geometría de ruta: {e}")
        return None, None

def parse_travel_details(details_string):
    """
    Parsea la cadena 'detalle_desplazamientos_min' en una lista de diccionarios para mantener el orden.
    Ej: "Empresa -> Briones: 5.9 min | Briones -> Haro: 9.6 min"
    Retorna: [{"segmento": "Empresa -> Briones", "duracion_min": 5.9}, ...]
    """
    parsed_details_list = [] # Cambiado a lista
    if not isinstance(details_string, str):
        return parsed_details_list

    segments = details_string.split('|')
    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue
        
        match = re.match(r'(.+):\s*([\d.]+)\s*min', segment)
        if match:
            travel_segment = match.group(1).strip()
            duration_str = match.group(2)
            try:
                duration_min = float(duration_str)
                # Añadido como un diccionario a la lista
                parsed_details_list.append({"segmento": travel_segment, "duracion_min": duration_min})
            except ValueError:
                print(f"Advertencia: No se pudo parsear la duración '{duration_str}' del segmento '{travel_segment}'.")
                continue
        else:
            print(f"Advertencia: Formato de segmento no reconocido: '{segment}'")
    return parsed_details_list # Retorna una lista

# --- Endpoints de la API ---

@app.route('/')
def home():
    return "API del Planificador de Rutas está en funcionamiento. Usa /api/semanas-disponibles, /api/plan-semanal/<año_semana>, /api/ruta-geometria-dia/<fecha> o /api/rutas-geometria-semanal/<año_semana>"

@app.route('/api/semanas-disponibles', methods=['GET'])
def get_available_weeks():
    """
    Endpoint para obtener un resumen de las semanas disponibles en el dataset anual.
    Devuelve una lista de objetos con 'label' (para mostrar) y 'value' (para filtrar).
    """
    if df_anual_rutas is None or df_anual_rutas.empty:
        return jsonify({"error": "No hay datos de rutas cargados."}), 500

    semanas_disponibles_valores = sorted(df_anual_rutas['AñoSemanaISO'].unique())
    semanas_resumen = []

    for as_iso_str in semanas_disponibles_valores:
        fechas_en_semana_df = df_anual_rutas[df_anual_rutas['AñoSemanaISO'] == as_iso_str]['Fecha']
        if not fechas_en_semana_df.empty:
            some_date_in_week = fechas_en_semana_df.min()
            
            iso_year, iso_week, iso_weekday = some_date_in_week.isocalendar()
            inicio_semana = some_date_in_week - timedelta(days=iso_weekday - 1)
            fin_semana = inicio_semana + timedelta(days=6)
            
            mes_nombre_actual = inicio_semana.strftime('%B')

            semanas_resumen.append({
                "valor_semana": as_iso_str,
                "label": f"Semana {iso_week} de {mes_nombre_actual} ({inicio_semana.strftime('%d %b')} - {fin_semana.strftime('%d %b %Y')})",
                "dias_con_ruta": sorted([d.strftime('%Y-%m-%d') for d in fechas_en_semana_df.dt.date.unique()])
            })
        else:
            semanas_resumen.append({
                "valor_semana": as_iso_str,
                "label": f"Semana {as_iso_str.split('-W')[1]} (Fechas no disponibles)",
                "dias_con_ruta": []
            })
    
    return jsonify(semanas_resumen)

@app.route('/api/plan-semanal/<string:year_week_iso>', methods=['GET'])
def get_weekly_plan(year_week_iso):
    """
    Endpoint para obtener el plan de rutas detallado para una semana específica.
    Incluye el 'detalle_desplazamientos_min' y 'duraciones_viajes_individuales_min' (ordenado como lista) para cada día.
    """
    if df_anual_rutas is None or df_anual_rutas.empty:
        return jsonify({"error": "No hay datos de rutas cargados."}), 500

    df_semana_completa = df_anual_rutas[df_anual_rutas["AñoSemanaISO"] == year_week_iso].copy()

    if df_semana_completa.empty:
        return jsonify({"message": f"No hay rutas planificadas para la semana '{year_week_iso}'."}), 404

    dias_en_semana = sorted(df_semana_completa["Fecha"].dt.date.unique())
    weekly_plan_data = []

    for dia_actual in dias_en_semana:
        df_ruta_dia = df_semana_completa[df_semana_completa["Fecha"].dt.date == dia_actual].copy()

        if df_ruta_dia.empty:
            continue

        full_route_string = df_ruta_dia['Secuencia_Ruta_Dia'].iloc[0]
        travel_time_min_csv = df_ruta_dia['Tiempo_Desplazamiento_Dia_min'].iloc[0]
        total_effective_work_hours = df_ruta_dia['Horas_Trabajo_Total_Dia'].iloc[0]
        total_journey_hours = df_ruta_dia['Jornada_Total_Horas'].iloc[0]
        detailed_displacements_str = df_ruta_dia['Detalle_Desplazamientos_min'].iloc[0]
        
        # Parsear el detalle de desplazamientos en una lista de diccionarios
        parsed_individual_durations = parse_travel_details(detailed_displacements_str)

        locality_names_in_order = [name.strip() for name in full_route_string.split('➔')]
        
        coords_for_ors_daily_route = []
        markers_data = []

        for loc_name_display in locality_names_in_order:
            if loc_name_display == ORIGIN_NAME:
                coords_for_ors_daily_route.append(ORIGIN_COORDS)
                if not any(m.get('Localidad') == ORIGIN_NAME for m in markers_data):
                    markers_data.append({
                        'Localidad': ORIGIN_NAME,
                        'Lat': ORIGIN_COORDS[1],
                        'Lon': ORIGIN_COORDS[0],
                        'Type': 'Origin'
                    })
            else:
                matching_clients = df_ruta_dia[df_ruta_dia['Localidad'].str.lower() == loc_name_display.lower()]
                
                if not matching_clients.empty:
                    client_row_coords = matching_clients.iloc[0] 
                    coords_for_ors_daily_route.append([client_row_coords['Lon'], client_row_coords['Lat']])
                    
                    if not any(m.get('Lat') == client_row_coords['Lat'] and m.get('Lon') == client_row_coords['Lon'] for m in markers_data):
                        first_client_info = matching_clients.iloc[0] 
                        
                        markers_data.append({
                            'Localidad': first_client_info['Localidad'],
                            'Lat': first_client_info['Lat'],
                            'Lon': first_client_info['Lon'],
                            'Type': 'Client',
                            'ClienteID': str(first_client_info['Cliente']),
                            'HorasTrabajo': float(first_client_info['Horas_Trabajo_Cliente']),
                            'Cluster': int(first_client_info['Cluster'])
                        })
                else:
                    print(f"Advertencia: Coordenadas no encontradas en el CSV para '{loc_name_display}'.")

        day_plan_data = {
            "fecha": dia_actual.strftime('%A, %d/%m/%Y'),
            "fecha_iso": dia_actual.strftime('%Y-%m-%d'),
            "distancia_km": round(travel_time_min_csv * 0.5, 2), # Placeholder, la real se calcula en el endpoint de geometría
            "tiempo_viaje_min": round(travel_time_min_csv, 1),
            "horas_trabajo_efectivas": round(total_effective_work_hours, 1),
            "jornada_total_horas": round(total_journey_hours, 1),
            "secuencia_ruta_display": full_route_string,
            "detalle_desplazamientos_min": detailed_displacements_str,
            "duraciones_viajes_individuales_min": parsed_individual_durations, # AHORA ES UNA LISTA ORDENADA
            "markers": markers_data,
            "route_geometry_url": f"/api/ruta-geometria-dia/{dia_actual.strftime('%Y-%m-%d')}"
        }
        weekly_plan_data.append(day_plan_data)

    return jsonify(weekly_plan_data)

@app.route('/api/ruta-geometria-dia/<string:date_str>', methods=['GET'])
def get_daily_route_geometry(date_str):
    """
    Endpoint para obtener solo la geometría de la ruta y la distancia/tiempo para un día específico.
    Incluye el 'detalle_desplazamientos_min' y 'duraciones_viajes_individuales_min' (ordenado como lista).
    """
    if df_anual_rutas is None or df_anual_rutas.empty:
        return jsonify({"error": "No hay datos de rutas cargados."}), 500

    try:
        dia_actual = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"error": "Formato de fecha inválido. Usa YYYY-MM-DD."}), 400

    df_ruta_dia = df_anual_rutas[df_anual_rutas["Fecha"].dt.date == dia_actual].copy()

    if df_ruta_dia.empty:
        return jsonify({"message": f"No hay ruta planificada para el {date_str}."}), 404

    full_route_string = df_ruta_dia['Secuencia_Ruta_Dia'].iloc[0]
    travel_time_min_csv = df_ruta_dia['Tiempo_Desplazamiento_Dia_min'].iloc[0]
    detailed_displacements_str = df_ruta_dia['Detalle_Desplazamientos_min'].iloc[0]
    
    # Parsear el detalle de desplazamientos en una lista de diccionarios
    parsed_individual_durations = parse_travel_details(detailed_displacements_str)

    locality_names_in_order = [name.strip() for name in full_route_string.split('➔')]
    coords_for_ors_daily_route = []

    for loc_name_display in locality_names_in_order:
        if loc_name_display == ORIGIN_NAME:
            coords_for_ors_daily_route.append(ORIGIN_COORDS)
        else:
            matching_clients = df_ruta_dia[df_ruta_dia['Localidad'].str.lower() == loc_name_display.lower()]
            if not matching_clients.empty:
                client_row = matching_clients.iloc[0] 
                coords_for_ors_daily_route.append([client_row['Lon'], client_row['Lat']])
            else:
                print(f"Advertencia (geometría): Coordenadas no encontradas para '{loc_name_display}'.")

    geometry_dia, distancia_dia = get_route_geometry_and_distance_ors(coords_for_ors_daily_route)

    if geometry_dia is None:
        return jsonify({"error": "No se pudo calcular la geometría de la ruta para este día. Revisa los logs del servidor.", "details": "ORS API call failed or invalid coordinates."}), 500
    
    response_data = {
        "fecha": dia_actual.strftime('%Y-%m-%d'),
        "total_distance_km": round(distancia_dia, 2),
        "total_travel_time_min": round(travel_time_min_csv, 1),
        "detalle_desplazamientos_min": detailed_displacements_str,
        "duraciones_viajes_individuales_min": parsed_individual_durations, # AHORA ES UNA LISTA ORDENADA
        "route_geometry_geojson": geometry_dia
    }
    
    return jsonify(response_data)

@app.route('/api/rutas-geometria-semanal/<string:year_week_iso>', methods=['GET'])
def get_weekly_route_geometries(year_week_iso):
    """
    Endpoint para obtener las geometrías GeoJSON de todas las rutas para una semana específica.
    NO incluye el 'detalle_desplazamientos_min' ni 'duraciones_viajes_individuales_min' aquí
    para mantener esta respuesta enfocada en la geometría.
    Para el detalle, consulta /api/ruta-geometria-dia/<fecha> o /api/plan-semanal/<año_semana>.
    """
    if df_anual_rutas is None or df_anual_rutas.empty:
        return jsonify({"error": "No hay datos de rutas cargados."}), 500

    df_semana_completa = df_anual_rutas[df_anual_rutas["AñoSemanaISO"] == year_week_iso].copy()

    if df_semana_completa.empty:
        return jsonify({"message": f"No hay rutas planificadas para la semana '{year_week_iso}'."}), 404

    dias_en_semana = sorted(df_semana_completa["Fecha"].dt.date.unique())
    weekly_geometries = {}

    for dia_actual in dias_en_semana:
        df_ruta_dia = df_semana_completa[df_semana_completa["Fecha"].dt.date == dia_actual].copy()

        if df_ruta_dia.empty:
            continue

        full_route_string = df_ruta_dia['Secuencia_Ruta_Dia'].iloc[0]
        travel_time_min_csv = df_ruta_dia['Tiempo_Desplazamiento_Dia_min'].iloc[0]

        locality_names_in_order = [name.strip() for name in full_route_string.split('➔')]
        coords_for_ors_daily_route = []

        for loc_name_display in locality_names_in_order:
            if loc_name_display == ORIGIN_NAME:
                coords_for_ors_daily_route.append(ORIGIN_COORDS)
            else:
                matching_clients = df_ruta_dia[df_ruta_dia['Localidad'].str.lower() == loc_name_display.lower()]
                if not matching_clients.empty:
                    client_row = matching_clients.iloc[0] 
                    coords_for_ors_daily_route.append([client_row['Lon'], client_row['Lat']])
                else:
                    print(f"Advertencia (geometría semanal): Coordenadas no encontradas para '{loc_name_display}'.")
        
        geometry_dia, distancia_dia = get_route_geometry_and_distance_ors(coords_for_ors_daily_route)

        if geometry_dia is None:
            print(f"Error: No se pudo obtener geometría para el día {dia_actual.strftime('%Y-%m-%d')} de la semana {year_week_iso}.")
            weekly_geometries[dia_actual.strftime('%Y-%m-%d')] = {
                "error": "No se pudo generar la geometría de la ruta."
            }
        else:
            weekly_geometries[dia_actual.strftime('%Y-%m-%d')] = {
                "total_distance_km": round(distancia_dia, 2),
                "total_travel_time_min": round(travel_time_min_csv, 1),
                "route_geometry_geojson": geometry_dia
            }
    
    return jsonify(weekly_geometries)


if __name__ == '__main__':
    app.run(debug=True, port=5000)