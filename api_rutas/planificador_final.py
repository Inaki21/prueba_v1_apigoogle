import pandas as pd
from datetime import datetime, timedelta
import json
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

# Parámetros de archivo
CSV_PATH = '../csv/clientes_90min.csv'
MATRIZ_TIEMPOS_PATH = '../csv/matriz_tiempos_final.csv'
JSON_PATH = '../csv/example_input.json'

# Coordenadas fijas de Ollauri
LAT_OLLAURI = 42.539
LON_OLLAURI = -2.848

# Cargar JSON
with open(JSON_PATH, "r", encoding="utf-8") as fh:
    input_json_info = json.load(fh)

# Mes objetivo
meses_es = {
    'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4,
    'MAYO': 5, 'JUNIO': 6, 'JULIO': 7, 'AGOSTO': 8,
    'SEPTIEMBRE': 9, 'OCTUBRE': 10, 'NOVIEMBRE': 11, 'DICIEMBRE': 12
}
MES_OBJETIVO = input_json_info['mes']
mes_numero = meses_es[MES_OBJETIVO.strip().upper()]
LISTA_OPERARIOS = input_json_info.get("tecnicos", [])
NUM_OPERARIOS = len(LISTA_OPERARIOS)

# Cargar localizaciones
df = pd.DataFrame(input_json_info['localizaciones'])
df.columns = ['CLIENTE', 'LOCALIDAD', 'LAT', 'LON', 'HORAS']

# Clustering por operario
scaler = StandardScaler()
features_scaled = scaler.fit_transform(df[['LAT', 'LON', 'HORAS']])
kmeans = KMeans(n_clusters=NUM_OPERARIOS, random_state=42)
df['OPERARIO_IDX'] = kmeans.fit_predict(features_scaled)
df['ID_TECNICO'] = df['OPERARIO_IDX'].apply(lambda idx: LISTA_OPERARIOS[idx])

# Matriz de tiempos
matriz_tiempos = pd.read_csv(MATRIZ_TIEMPOS_PATH, index_col=0)
matriz_tiempos.columns = matriz_tiempos.columns.str.strip().str.lower()
matriz_tiempos.index = matriz_tiempos.index.str.strip().str.lower()
for loc in matriz_tiempos.index:
    matriz_tiempos.at[loc, loc] = 0.0

# Día de la semana en español
dias_semana_es = {
    'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
    'Thursday': 'Jueves', 'Friday': 'Viernes'
}

def calcular_tiempo_ruta_con_localidades(localidades, matriz):
    ruta = ['ollauri'] + localidades + ['ollauri']
    tiempo_total = 0
    for i in range(len(ruta) - 1):
        origen = ruta[i]
        destino = ruta[i + 1]
        if origen == destino:
            continue
        try:
            tiempo = float(matriz.at[origen, destino]) / 60.0
            tiempo_total += tiempo
        except KeyError:
            return None
    return tiempo_total

def distribuir_trabajos(df_trabajos, matriz_tiempos):
    dias_semana = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    fecha = datetime(2025, mes_numero, 1)
    semana_actual = 1
    HORAS_JORNADA_MAX = 8
    plan = []
    trabajos_dia = []
    clientes_asignados = set()
    dia_actual = fecha.strftime('%d/%m/%Y')

    for _, fila in df_trabajos.sort_values(by='HORAS', ascending=False).iterrows():
        cliente = fila['CLIENTE']
        localidad = fila['LOCALIDAD'].strip().lower()
        horas = fila['HORAS']

        if cliente in clientes_asignados:
            continue

        localidades_temp = [loc for _, loc, _ in trabajos_dia] + [localidad]
        tiempo_ruta_temp = calcular_tiempo_ruta_con_localidades(localidades_temp, matriz_tiempos)
        if tiempo_ruta_temp is None:
            continue

        horas_total_temp = tiempo_ruta_temp + sum(h for _, _, h in trabajos_dia) + horas

        if horas_total_temp > HORAS_JORNADA_MAX or fecha.strftime('%A') not in dias_semana:
            if trabajos_dia:
                plan.append((semana_actual, fecha.strftime('%A'), dia_actual, trabajos_dia.copy()))
            trabajos_dia.clear()
            while True:
                fecha += timedelta(days=1)
                if fecha.strftime('%A') in dias_semana:
                    break
            dia_actual = fecha.strftime('%d/%m/%Y')
            if fecha.weekday() == 0:
                semana_actual += 1
        trabajos_dia.append((cliente, localidad, horas))
        clientes_asignados.add(cliente)

    if trabajos_dia:
        plan.append((semana_actual, fecha.strftime('%A'), dia_actual, trabajos_dia.copy()))
    return plan

def calcular_duracion_ruta(localidades, matriz):
    ruta = ['ollauri'] + localidades + ['ollauri']
    tiempo_total = 0
    for i in range(len(ruta) - 1):
        origen = ruta[i]
        destino = ruta[i + 1]
        if origen == destino:
            continue
        try:
            tiempo = float(matriz.at[origen, destino])
            tiempo_total += tiempo
        except KeyError:
            print(f"Tiempo no encontrado entre {origen} y {destino}")
    return tiempo_total, ruta

def agregar_tramos_a_csv(semana, dia, fecha, ruta, matriz, tecnico_id, df):
    # Fila inicial: partida desde Ollauri
    rutas_para_csv.append({
        'Semana': semana, 'Día': dia, 'Fecha': fecha,
        'Cliente': 0, 'Localidad': 'Ollauri',
        'Lat': LAT_OLLAURI, 'Lon': LON_OLLAURI,
        'Horas': 0.0, 'Tiempo_Desplazamiento_min': 0.0,
        'id_tecnico': tecnico_id
    })

    for i in range(len(ruta) - 1):
        origen = ruta[i]
        destino = ruta[i + 1]
        if origen == destino:
            continue
        
        try:
            tiempo = float(matriz.at[origen, destino])
        except KeyError:
            tiempo = 0.0

        if destino == "ollauri":
            lat_destino, lon_destino = LAT_OLLAURI, LON_OLLAURI
            horas_destino = 0.0
            cliente_destino = 0
        else:
            fila = df[df['LOCALIDAD'].str.strip().str.lower() == destino].iloc[0]
            lat_destino = fila['LAT']
            lon_destino = fila['LON']
            horas_destino = fila['HORAS']
            cliente_destino = fila['CLIENTE']

        rutas_para_csv.append({
            'Semana': semana, 'Día': dia, 'Fecha': fecha,
            'Cliente': cliente_destino, 'Localidad': destino.title(),
            'Lat': lat_destino, 'Lon': lon_destino,
            'Horas': horas_destino, 'Tiempo_Desplazamiento_min': tiempo,
            'id_tecnico': tecnico_id
        })

    
# Generar planificación
rutas_para_csv = []
plan_por_operario = {}
for tecnico_id in LISTA_OPERARIOS:
    df_op = df[df['ID_TECNICO'] == tecnico_id]
    plan_por_operario[tecnico_id] = distribuir_trabajos(df_op, matriz_tiempos)

for tecnico_id, plan in plan_por_operario.items():
    for semana, dia, fecha, tareas in plan:
        dia_es = dias_semana_es.get(dia, dia)
        localidades = [loc for _, loc, _ in tareas]
        _, ruta = calcular_duracion_ruta(localidades, matriz_tiempos)
        agregar_tramos_a_csv(semana, dia_es, fecha, ruta, matriz_tiempos, tecnico_id, df)


# Guardar rutas
MES_NOMBRE_ARCHIVO = MES_OBJETIVO.strip().lower()
df_rutas = pd.DataFrame(rutas_para_csv)
df_rutas.to_csv(f'rutas_trabajo.csv', index=False)