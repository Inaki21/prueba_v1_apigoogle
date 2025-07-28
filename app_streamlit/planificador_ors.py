import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import folium
import calendar
import time
import openrouteservice as ors
import os # Importamos os para la caché

# --- Parameters and Configuration ---
EXCEL_PATH = 'Horas_trabajo (1).xlsx'
# Asegúrate de que este archivo 'clientes_90min.csv' exista en el MISMO DIRECTORIO que este script.
CLIENTES_COORD_CLUSTER_CSV_PATH = 'clientes_90min.csv'
OUTPUT_CSV_PATH = f'rutas_trabajo_anual_{2025}_optimizadas_con_clusters.csv'
ORS_MATRIX_CACHE_PATH = 'ors_travel_matrix_cache.pkl' # Ruta para el archivo de caché de la matriz

# IMPORTANT! Your OpenRouteService API key
# Replace with your actual API key.
# It's better to load this from environment variables in production.
API_KEY = 'eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImM2ZDM4MDA4NTE1OTQ4Njc4ODZmNGMyZDJhZmMwZDZiIiwiaCI6Im11cm11cjY0In0=' 

# Mapping of Spanish months to numbers
meses_es = {
    'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4,
    'MAYO': 5, 'JUNIO': 6, 'JULIO': 7, 'AGOSTO': 8,
    'SEPTIEMBRE': 9, 'OCTUBRE': 10, 'NOVIEMBRE': 11, 'DICIEMBRE': 12
}

# --- NEW: Define the year for the annual plan ---
YEAR_OBJECTIVE = 2025

# Journey parameters
HORAS_JORNADA_MAX = 8 # Max hours per workday (8 hours in the example)

print(f"Generating annual plan for {YEAR_OBJECTIVE}...")
start_time = time.time()

# --- OpenRouteService Client ---
ors_client = ors.Client(key=API_KEY)

# --- Origin Handling: Company (Ollauri, La Rioja) ---
ORIGIN_NAME = "Empresa (Ollauri, La Rioja)"
ORIGIN_COORDS = [-2.8282690950218656, 42.54387913161117] # [Lon, Lat]
# For Folium, Lat/Lon is [Latitude, Longitude]
origin_folium_coord = [ORIGIN_COORDS[1], ORIGIN_COORDS[0]] 

# --- Data Loading with error handling ---
try:
    # Load the full excel once, specifying header=1 as it starts on the second row (index 1)
    df_excel_full = pd.read_excel(EXCEL_PATH, sheet_name='Horas', header=1) 
    df_clientes_coord_cluster = pd.read_csv(CLIENTES_COORD_CLUSTER_CSV_PATH)
    print(f"\nDebug: df_excel_full loaded. Rows: {len(df_excel_full.index)}")
    print(f"Debug: df_clientes_coord_cluster loaded. Rows: {len(df_clientes_coord_cluster.index)}")
except FileNotFoundError as e:
    print(f"❌ Error: File not found. Ensure all CSV/Excel files are in the same directory as the script. ({e})")
    exit()
except Exception as e:
    print(f"❌ Error loading files: {e}")
    exit()

# --- Normalization of Column Names (for full excel and cluster data) ---
print(f"Debug: Columns of df_excel_full BEFORE normalizing: {df_excel_full.columns.tolist()}")
print(f"Debug: Columns of df_clientes_coord_cluster BEFORE normalizing: {df_clientes_coord_cluster.columns.tolist()}")

df_excel_full.columns = [col.strip().upper() for col in df_excel_full.columns]
df_clientes_coord_cluster.columns = [col.strip().upper() for col in df_clientes_coord_cluster.columns]

print(f"Debug: Columns of df_excel_full AFTER normalizing: {df_excel_full.columns.tolist()}")
print(f"Debug: Columns of df_clientes_coord_cluster AFTER normalizing: {df_clientes_coord_cluster.columns.tolist()}")


# Select and rename columns for df_excel_full.
# We will select specific month columns inside the loop.
# Only keeping 'CLIENTE' and 'LOCALIDAD' here for merging later.
# Ensure 'CLIENTE' is treated as string for consistent merging
df_excel_full['CLIENTE'] = df_excel_full['CLIENTE'].fillna(0).astype(int).astype(str)
df_excel_full['LOCALIDAD'] = df_excel_full['LOCALIDAD'].astype(str).str.strip().str.lower()
print(f"Debug: df_excel_full after selecting common columns. Rows: {len(df_excel_full.index)}")


# Ensure 'CLIENTE' in df_clientes_coord_cluster is consistent for merging
# Handle potential missing 'CLUSTER' column if the CSV doesn't provide it
required_cluster_cols = ['CLIENTE', 'LOCALIDAD', 'LAT', 'LON']
if 'CLUSTER' not in df_clientes_coord_cluster.columns:
    print("Warning: 'CLUSTER' column not found in df_clientes_coord_cluster. Assigning default cluster 0.")
    df_clientes_coord_cluster['CLUSTER'] = 0 # Default to 0 if not present
    df_clientes_coord_cluster = df_clientes_coord_cluster[required_cluster_cols + ['CLUSTER']]
else:
    df_clientes_coord_cluster = df_clientes_coord_cluster[required_cluster_cols + ['CLUSTER']] # Select necessary columns

df_clientes_coord_cluster['CLIENTE'] = df_clientes_coord_cluster['CLIENTE'].astype(str).str.strip().str.upper()
df_clientes_coord_cluster['LOCALIDAD'] = df_clientes_coord_cluster['LOCALIDAD'].astype(str).str.strip().str.lower()

# Convert LAT/LON to numeric, coercing errors to NaN and then dropping
df_clientes_coord_cluster['LAT'] = pd.to_numeric(df_clientes_coord_cluster['LAT'], errors='coerce')
df_clientes_coord_cluster['LON'] = pd.to_numeric(df_clientes_coord_cluster['LON'], errors='coerce')
original_clientes_rows = len(df_clientes_coord_cluster.index)
df_clientes_coord_cluster = df_clientes_coord_cluster.dropna(subset=['LAT', 'LON'])
print(f"Debug: df_clientes_coord_cluster after dropna on LAT/LON. Original rows: {original_clientes_rows}, Remaining rows: {len(df_clientes_coord_cluster.index)}")

print("\nDebug: Muestreo de df_excel_full antes de merge (primeras 5 filas):")
print(df_excel_full[['CLIENTE', 'LOCALIDAD', 'ENERO']].head()) # Show a sample month column

print("\nDebug: Muestreo de df_clientes_coord_cluster antes de merge (primeras 5 filas):")
print(df_clientes_coord_cluster.head())


# Add the "Empresa" origin to df_clientes_coord_cluster if not present
# Ensure the LOCALIDAD is lower case for consistent matching
if ORIGIN_NAME.lower() not in df_clientes_coord_cluster['LOCALIDAD'].str.lower().values:
    origin_df_row = pd.DataFrame([{
        'CLIENTE': 'BASE', # A dummy client name for the origin
        'LOCALIDAD': ORIGIN_NAME.lower(), # Store locality in lowercase
        'LAT': ORIGIN_COORDS[1], # Latitude for the DataFrame
        'LON': ORIGIN_COORDS[0], # Longitude for the DataFrame
        'CLUSTER': -1 # Special cluster for the origin
    }])
    df_clientes_coord_cluster = pd.concat([origin_df_row, df_clientes_coord_cluster], ignore_index=True)
print(f"Debug: df_clientes_coord_cluster after adding origin. Rows: {len(df_clientes_coord_cluster.index)}")

# Create a mapping of locality to coordinates [lon, lat] for ORS
# This map will be used to look up coordinates for the matrix
locations_for_ors_matrix = {}
locations_for_ors_matrix[ORIGIN_NAME.lower()] = ORIGIN_COORDS # Ensure origin is in lowercase

# Collect all unique client localities from the cluster file to build the full matrix
# This ensures we get all possible travel times upfront, even if a client isn't in Excel for a given month
unique_client_locations_coords = df_clientes_coord_cluster[['LOCALIDAD', 'LON', 'LAT']].drop_duplicates()
for idx, row in unique_client_locations_coords.iterrows():
    loc_name_lower = row['LOCALIDAD'].lower() # Ensure locality is lowercase
    if loc_name_lower not in locations_for_ors_matrix: # Avoid adding origin again if already there
        locations_for_ors_matrix[loc_name_lower] = [row['LON'], row['LAT']]

ordered_loc_names = list(locations_for_ors_matrix.keys()) # Names in the order they'll be sent to ORS
ordered_coords_for_ors = [locations_for_ors_matrix[name] for name in ordered_loc_names] # Coords [Lon, Lat] for ORS

print(f"Debug: Number of locations to send to ORS: {len(ordered_coords_for_ors)}")
print(f"Debug: First 5 locations (LON, LAT): {ordered_coords_for_ors[:5]}")
if ordered_coords_for_ors:
    print(f"Debug: Type of the first location: {type(ordered_coords_for_ors[0])}")
    if ordered_coords_for_ors[0]:
        print(f"Debug: Types of coordinates in the first location: {type(ordered_coords_for_ors[0][0])}, {type(ordered_coords_for_ors[0][1])}")


# --- Function to get ORS matrix (moved outside the loop for efficiency) ---
def get_ors_matrix(locations_coords, locations_names, client):
    print("⏳ Requesting time matrix from OpenRouteService...")
    if not locations_coords:
        print("❌ Error: List of locations for the matrix is empty. Cannot make API call.")
        return None

    # Check for cached matrix first
    if os.path.exists(ORS_MATRIX_CACHE_PATH):
        try:
            cached_matrix = pd.read_pickle(ORS_MATRIX_CACHE_PATH)
            # Basic check if cached matrix matches current locations
            if set(cached_matrix.index) == set(locations_names):
                print(f"✅ Time matrix loaded from cache: {ORS_MATRIX_CACHE_PATH}")
                return cached_matrix
            else:
                print("Cache mismatch: Locations in cache do not match current locations. Re-requesting matrix.")
        except Exception as e:
            print(f"Error loading cached matrix: {e}. Re-requesting matrix.")

    try:
        response = client.distance_matrix(
            locations=locations_coords,
            profile='driving-car',
            metrics=["duration"],
        )
        durations = response["durations"]
        durations_min = np.array(durations) / 60.0
        matriz_df = pd.DataFrame(durations_min, index=locations_names, columns=locations_names)
        matriz_df = matriz_df.map(lambda x: round(x, 1)) 
        print("✅ Time matrix received and processed.")
        # Save to cache
        matriz_df.to_pickle(ORS_MATRIX_CACHE_PATH)
        print(f"Matriz de tiempos guardada en caché: {ORS_MATRIX_CACHE_PATH}")
        return matriz_df
    except ors.exceptions.ApiError as e:
        print(f"❌ Error connecting to OpenRouteService: {e}")
        print("Please check your API_KEY and internet connection. Also consider API rate limits.")
        return None
    except Exception as e:
        print(f"❌ Unexpected error getting ORS matrix: {e}")
        return None

# Get the dynamic time matrix ONCE for all possible locations
matriz_tiempos_dinamica = get_ors_matrix(ordered_coords_for_ors, ordered_loc_names, ors_client)

if matriz_tiempos_dinamica is None:
    print("Could not obtain the time matrix. Exiting program.")
    exit()

# --- Utility Functions (modified for segment durations) ---
def get_time_from_matrix(origen, destino, matriz):
    """Obtains travel time in MINUTES from the dynamic matrix."""
    try:
        # Ensure lookup keys are consistent (lowercase)
        return float(matriz.at[origen.strip().lower(), destino.strip().lower()])
    except KeyError:
        print(f"Warning: Locality '{origen}' or '{destino}' not found in time matrix. Check coordinate data.")
        return None

def calculate_route_travel_time_and_segments(route_localities, matriz):
    """
    Calculates total route time in MINUTES and individual segment times,
    including travel from ORIGIN to the first point and from the last point back to ORIGIN.
    `route_localities` must be a list of locality names (strings) already in lowercase.
    Returns total_time_min, list_of_segment_times_min
    """
    if not route_localities:
        return 0.0, []

    total_time = 0.0
    segment_durations = []
    
    full_route_localities_lower = [ORIGIN_NAME.lower()] + route_localities + [ORIGIN_NAME.lower()]

    for i in range(len(full_route_localities_lower) - 1):
        origen = full_route_localities_lower[i]
        destino = full_route_localities_lower[i + 1]
        time_segment = get_time_from_matrix(origen, destino, matriz)
        if time_segment is None:
            return None, None # Propagate None if any segment fails
        total_time += time_segment
        segment_durations.append(time_segment)
    return total_time, segment_durations

def optimize_daily_route_sequence(clients_for_day_df, matriz_tiempos):
    """
    Optimizes the visit sequence for a day using a nearest neighbor heuristic.
    Returns a list of ordered DataFrame rows, the total travel time in minutes,
    and a list of individual segment travel times in minutes.
    """
    if clients_for_day_df.empty:
        return [], 0.0, []

    current_location = ORIGIN_NAME.lower()
    remaining_clients = clients_for_day_df.copy()
    optimized_sequence_rows = []
    total_travel_time_for_optimization = 0.0 # This is used during greedy optimization
    
    # NEW: Store segment times for the final optimized route
    optimized_segment_travel_times = []

    while not remaining_clients.empty:
        next_client_row = None
        min_travel_time_segment = float('inf')
        next_client_idx = None

        for idx, client_row in remaining_clients.iterrows():
            loc = client_row['LOCALIDAD'].lower() # Ensure locality is lowercase for lookup
            time_to_next = get_time_from_matrix(current_location, loc, matriz_tiempos)

            if time_to_next is not None and time_to_next < min_travel_time_segment:
                min_travel_time_segment = time_to_next
                next_client_row = client_row
                next_client_idx = idx

        if next_client_row is None:
            print(f"Warning: Could not find a path from '{current_location}' to any remaining client. This route might be incomplete.")
            break # Exit loop, remaining clients will not be ordered

        total_travel_time_for_optimization += min_travel_time_segment
        optimized_segment_travel_times.append(min_travel_time_segment) # Add segment time
        
        current_location = next_client_row['LOCALIDAD'].lower() # Update current location in lowercase
        optimized_sequence_rows.append(next_client_row)
        remaining_clients = remaining_clients.drop(next_client_idx)

    # Calculate return trip to base after all clients are visited
    if optimized_sequence_rows:
        time_back_to_base = get_time_from_matrix(current_location, ORIGIN_NAME.lower(), matriz_tiempos)
        if time_back_to_base is None:
            return [], None, None # Cannot complete the route
        total_travel_time_for_optimization += time_back_to_base
        optimized_segment_travel_times.append(time_back_to_base) # Add return segment time

    return optimized_sequence_rows, total_travel_time_for_optimization, optimized_segment_travel_times

# --- Job Distribution Logic with Clusters (Modified for annual loop) ---
def distribute_optimized_jobs_for_month(df_jobs_month, matrix_times, month_number_param, year_param):
    days_of_week_en = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    days_of_week_es = {
        'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
        'Thursday': 'Jueves', 'Friday': 'Viernes'
    }

    current_date = datetime(year_param, month_number_param, 1)
    while current_date.weekday() not in [0, 1, 2, 3, 4]: # 0=Monday, 4=Friday
        current_date += timedelta(days=1)

    planning_schedule_month = []
    assigned_clients_month = set() # Track assigned clients only for the current month

    pending_jobs_df_month = df_jobs_month.copy()

    num_days_in_month = calendar.monthrange(year_param, month_number_param)[1]
    max_days_to_process = num_days_in_month * 2 

    days_processed = 0

    while len(assigned_clients_month) < len(df_jobs_month) and days_processed < max_days_to_process:
        days_processed += 1

        if current_date.month != month_number_param and len(assigned_clients_month) == len(df_jobs_month):
            break
        if current_date.month > month_number_param and len(assigned_clients_month) < len(df_jobs_month):
            print(f"\n⚠️ Warning: Exceeded target month ({calendar.month_name[month_number_param].title()}) and still have clients for this month not assigned.")
            break

        day_name_en = current_date.strftime('%A')
        day_name_es = days_of_week_es.get(day_name_en, day_name_en)
        formatted_date_str = current_date.strftime('%d/%m/%Y')

        # Use isocalendar to get ISO week number (starts from 1)
        current_week_num_iso = current_date.isocalendar()[1] 

        clients_for_today_df = pd.DataFrame(columns=df_jobs_month.columns)

        available_jobs = pending_jobs_df_month[~pending_jobs_df_month['CLIENTE'].isin(assigned_clients_month)].copy()

        available_jobs = available_jobs.sort_values(by=['CLUSTER', 'HORAS'], ascending=[True, False])

        for idx, client_info_series in available_jobs.iterrows():
            client_info_df_row = pd.DataFrame([client_info_series])

            temp_clients_for_today_df = pd.concat([clients_for_today_df, client_info_df_row], ignore_index=True)

            # We need the total travel time for the *potential* route for checking against max hours
            _, estimated_travel_time_min, _ = optimize_daily_route_sequence(temp_clients_for_today_df, matrix_times)

            if estimated_travel_time_min is None:
                print(f"Debug: Client {client_info_series['CLIENTE']} ({client_info_series['LOCALIDAD'].title()}) creates unroutable path. Skipping.")
                continue

            accumulated_work_hours = temp_clients_for_today_df['HORAS'].sum()
            total_estimated_workday_hours = (estimated_travel_time_min / 60.0) + accumulated_work_hours

            if total_estimated_workday_hours <= HORAS_JORNADA_MAX:
                clients_for_today_df = temp_clients_for_today_df.copy() # Confirm the addition of the client
            else:
                client_name_debug = client_info_series['CLIENTE']
                locality_name_debug = client_info_series['LOCALIDAD'].title()
                hours_debug = client_info_series['HORAS']
                travel_time_debug_hours = estimated_travel_time_min / 60.0
                current_clients_work_hours_debug = accumulated_work_hours
                print(f"Debug (Month {calendar.month_name[month_number_param].title()}): Client {client_name_debug} ({locality_name_debug}, {hours_debug:.1f}h) CAN'T FIT on {formatted_date_str}. "
                      f"Current accumulated work for the day: {current_clients_work_hours_debug:.1f}h. "
                      f"Estimated travel time for this route: {travel_time_debug_hours:.1f}h. "
                      f"Total estimated workday: {total_estimated_workday_hours:.1f}h (Max: {HORAS_JORNADA_MAX}h). "
                      f"Skipping this client for today.")
                continue # If this client exceeds the workday limit, don't add it and try the next candidate

        if not clients_for_today_df.empty:
            # Once clients for the day are determined, optimize their final sequence
            optimized_daily_clients_sequence_rows, final_travel_time_min, segment_travel_times_list = \
                optimize_daily_route_sequence(clients_for_today_df, matrix_times)

            if final_travel_time_min is None:
                print(f"❌ Critical Error: Final route optimization for {formatted_date_str} failed. Clients: {[c['CLIENTE'] for c in clients_for_today_df.to_dict('records')]}. Skipping this day.")
                current_date += timedelta(days=1)
                while current_date.weekday() not in [0, 1, 2, 3, 4]:
                    current_date += timedelta(days=1)
                continue

            # Prepare for display and record
            optimized_locality_names = [row['LOCALIDAD'].lower() for row in optimized_daily_clients_sequence_rows]
            full_route_display = [ORIGIN_NAME] + [loc.title() for loc in optimized_locality_names] + [ORIGIN_NAME]

            # Create the segment details string
            segment_details_str = []
            full_route_names_for_segments = [ORIGIN_NAME.lower()] + optimized_locality_names + [ORIGIN_NAME.lower()]
            for i in range(len(segment_travel_times_list)):
                segment_details_str.append(
                    f"{full_route_names_for_segments[i].title()} -> {full_route_names_for_segments[i+1].title()}: "
                    f"{segment_travel_times_list[i]:.1f} min"
                )
            formatted_segment_details = " | ".join(segment_details_str)


            # Mark clients as assigned for this month
            for client_row in optimized_daily_clients_sequence_rows:
                assigned_clients_month.add(client_row['CLIENTE'])

            effective_work_hours_day = clients_for_today_df['HORAS'].sum()

            planning_schedule_month.append({
                'semana': current_week_num_iso, # Use ISO week number
                'dia_semana_en': day_name_en,
                'dia_semana_es': day_name_es,
                'fecha': formatted_date_str,
                'mes': calendar.month_name[month_number_param].title(), # Add month name
                'mes_num': month_number_param, # Add month number
                'clientes': clients_for_today_df.to_dict('records'), # Original order for client details
                'localidades_ruta_optimizada_nombres': optimized_locality_names, # Ordered localities in lowercase
                'ruta_nombres_title': full_route_display, # Formatted for display
                'tiempo_desplazamiento_min': final_travel_time_min,
                'detalle_desplazamientos_min': formatted_segment_details, # NUEVA INFORMACIÓN
                'horas_trabajo_efectivas': effective_work_hours_day
            })
        else:
            if not available_jobs.empty and len(assigned_clients_month) < len(df_jobs_month):
                pass 

        current_date += timedelta(days=1)
        while current_date.weekday() not in [0, 1, 2, 3, 4]:
            current_date += timedelta(days=1)

    unassigned_clients_df = df_jobs_month[~df_jobs_month['CLIENTE'].isin(assigned_clients_month)].copy()
    if not unassigned_clients_df.empty:
        print(f"\n--- Unassigned Clients for {calendar.month_name[month_number_param].title()} ---")
        for idx, row in unassigned_clients_df.iterrows():
            print(f"❌ {row['CLIENTE']} ({row['LOCALIDAD'].title()}) - {row['HORAS']:.1f} hours. Likely exceeds workday, no viable route, or could not be assigned within the processed days for this month.")
    else:
        print(f"✅ All clients assigned for {calendar.month_name[month_number_param].title()}.")

    return planning_schedule_month

# --- Main Annual Planning Loop ---
all_yearly_routes_output = pd.DataFrame()
# The 'all_yearly_tramos_output' is no longer needed as the detailed segments are in all_yearly_routes_output
map_data_for_yearly_map = [] 

for month_num in range(1, 13): # Iterate from January (1) to December (12)
    month_name_es = list(meses_es.keys())[list(meses_es.values()).index(month_num)] # Get month name (e.g., 'ENERO')
    print(f"\n--- Starting planning for {month_name_es.title()} {YEAR_OBJECTIVE} ---")

    df_excel_month_data = df_excel_full[['CLIENTE', 'LOCALIDAD', month_name_es]].copy()
    df_excel_month_data = df_excel_month_data.rename(columns={month_name_es: 'HORAS'})

    df_merged_month = df_excel_month_data.merge(
        df_clientes_coord_cluster[['CLIENTE', 'LOCALIDAD', 'LAT', 'LON', 'CLUSTER']],
        on=['CLIENTE', 'LOCALIDAD'],
        how='inner'
    )

    df_merged_month = df_merged_month[df_merged_month['HORAS'].notna() & (df_merged_month['HORAS'] > 0)].copy() 
    
    if df_merged_month.empty:
        print(f"No clients with valid hours for {month_name_es.title()} {YEAR_OBJECTIVE}. Skipping month.")
        continue 

    df_merged_month['HORAS'] = df_merged_month['HORAS'].astype(float)
    df_merged_month['CLUSTER'] = df_merged_month['CLUSTER'].astype(int) 

    monthly_plan = distribute_optimized_jobs_for_month(df_merged_month, matriz_tiempos_dinamica, month_num, YEAR_OBJECTIVE)

    for day_plan in monthly_plan:
        semana = day_plan['semana']
        dia_semana_es = day_plan['dia_semana_es']
        fecha = day_plan['fecha']
        mes_nombre = day_plan['mes']
        mes_num = day_plan['mes_num']
        tasks = day_plan['clientes']
        route_names_title_display = day_plan['ruta_nombres_title']
        travel_time_min = day_plan['tiempo_desplazamiento_min']
        detalle_desplazamientos_min = day_plan['detalle_desplazamientos_min'] # Nueva columna
        effective_work_hours = day_plan['horas_trabajo_efectivas']
        total_journey_hours = (travel_time_min / 60) + effective_work_hours

        for task_item in tasks:
            task_item_df = pd.DataFrame([{
                'Año': YEAR_OBJECTIVE,
                'Mes': mes_nombre,
                'Mes_Num': mes_num,
                'Semana': semana,
                'Día': dia_semana_es,
                'Fecha': fecha,
                'Cliente': str(task_item['CLIENTE']), 
                'Localidad': str(task_item['LOCALIDAD']).title(), 
                'Lat': task_item['LAT'],
                'Lon': task_item['LON'],
                'Horas_Trabajo_Cliente': task_item['HORAS'],
                'Cluster': task_item['CLUSTER'],
                'Tiempo_Desplazamiento_Dia_min': travel_time_min,
                'Detalle_Desplazamientos_min': detalle_desplazamientos_min, # Asignamos la nueva columna
                'Horas_Trabajo_Total_Dia': effective_work_hours,
                'Jornada_Total_Horas': total_journey_hours,
                'Secuencia_Ruta_Dia': ' ➔ '.join(route_names_title_display) 
            }])
            all_yearly_routes_output = pd.concat([all_yearly_routes_output, task_item_df], ignore_index=True)


        route_coords_for_map = []
        for loc_name_display in route_names_title_display:
            loc_name_lower = loc_name_display.lower()
            if loc_name_lower == ORIGIN_NAME.lower():
                route_coords_for_map.append(origin_folium_coord)
            else:
                client_coord_row = df_clientes_coord_cluster[df_clientes_coord_cluster['LOCALIDAD'] == loc_name_lower].iloc[0]
                route_coords_for_map.append([client_coord_row['LAT'], client_coord_row['LON']])

        map_data_for_yearly_map.append({
            'route_display': route_names_title_display,
            'route_coords': route_coords_for_map,
            'day_info': f"{mes_nombre.title()} - Semana {semana} - {dia_semana_es} {fecha}",
            'line_color_index': mes_num - 1 
        })

# --- Final Output Generation ---

# Generate a single annual map
mapa_anual = folium.Map(location=origin_folium_coord, zoom_start=8)
folium.Marker(location=origin_folium_coord, popup=f"<b>{ORIGIN_NAME} (Base)</b>", icon=folium.Icon(color='black', icon='home', prefix='fa')).add_to(mapa_anual)

# Paleta de colores para los clusters (ampliada)
cluster_colors = {
    -1: 'black', 
    0: 'blue', 1: 'red', 2: 'green', 3: 'purple', 4: 'orange',
    5: 'darkred', 6: 'lightblue', 7: 'cadetblue', 8: 'darkgreen',
    9: 'darkblue', 10: 'lightgreen', 11: 'darkpurple', 12: 'pink',
    13: 'gray', 14: 'lightgray', 15: 'beige', 16: 'darkblue', 17: 'lightred'
}

# Add all client markers (unique locations) to the annual map
for idx, row in df_clientes_coord_cluster.iterrows():
    if row['LOCALIDAD'] != ORIGIN_NAME.lower(): 
        client_id_display = row['CLIENTE'] if row['CLIENTE'] != 'BASE' else '' 
        marker_color = cluster_colors.get(row['CLUSTER'], 'gray')
        folium.Marker(location=[row['LAT'], row['LON']],
                      popup=f"<b>{client_id_display}</b><br>{row['LOCALIDAD'].title()}<br>Cluster: {row['CLUSTER']}",
                      icon=folium.Icon(color=marker_color, icon='briefcase', prefix='fa')).add_to(mapa_anual)

# Define a broader palette of colors for monthly routes
monthly_line_colors = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b',
    '#e377c2', '#7f7f7f', '#bcbd22', '#17becf', '#aec7e8', '##ffbb78',
    '#98df8a', '#ff9896', '#c5b0d5', '#c49c94', '#f7b6d2', '#c7c7c7',
    '#dbdb8d', '#9edae5'
]


# Add polylines for all routes from `map_data_for_yearly_map`
for route_data in map_data_for_yearly_map:
    color_to_use = monthly_line_colors[route_data['line_color_index'] % len(monthly_line_colors)]
    folium.PolyLine(route_data['route_coords'],
                    color=color_to_use,
                    weight=4, opacity=0.7,
                    tooltip=route_data['day_info']).add_to(mapa_anual)


# Save CSVs and Final Map
if not all_yearly_routes_output.empty:
    all_yearly_routes_output.to_csv(OUTPUT_CSV_PATH, index=False, encoding='utf-8-sig')
    print(f"\n✅ Optimized annual routes saved to '{OUTPUT_CSV_PATH}'.")

    # Muestra un resumen de las primeras filas y columnas
    print("\nPrimeras 5 filas del plan anual generado:")
    print(all_yearly_routes_output.head())
    print("\nColumnas del DataFrame final:")
    print(all_yearly_routes_output.columns.tolist())
else:
    print("\n❌ No se generaron rutas para el plan anual. El archivo CSV de salida no será creado.")

# Save the annual map
MAP_OUTPUT_PATH = f'mapa_anual_rutas_{YEAR_OBJECTIVE}.html'
mapa_anual.save(MAP_OUTPUT_PATH)
print(f"✅ Annual routes map saved to '{MAP_OUTPUT_PATH}'.")

end_time = time.time()
print(f"\n--- Script completed in {end_time - start_time:.2f} seconds ---")