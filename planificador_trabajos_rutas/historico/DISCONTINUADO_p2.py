import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# Parámetros
EXCEL_PATH = 'Horas_trabajo (1).xlsx' 
CSV_PATH = 'clientes_90min.csv'
MES_OBJETIVO = 'Agosto'
OUTPUT_MATRIZ = 'matriz_tiempos_final.csv'

# Carga y limpieza de datos
print(f"Generando plan para {MES_OBJETIVO.title()} de 2025...")

df_excel = pd.read_excel(EXCEL_PATH, sheet_name='Horas', header=1)
df_csv = pd.read_csv(CSV_PATH)

df_excel.columns = [col.strip().upper() for col in df_excel.columns]
df_csv.columns = [col.strip().upper() for col in df_csv.columns]

mes = MES_OBJETIVO.strip().upper()
df_excel = df_excel.rename(columns={mes: 'HORAS'})
df_excel = df_excel[['CLIENTE', 'LOCALIDAD', 'HORAS']]
df_csv = df_csv[['CLIENTE', 'LOCALIDAD', 'LAT', 'LON', 'TIEMPO_DESDE_SEDE_MIN']]

# Filtrar y unir datos
clientes_validos = set(df_csv['CLIENTE'])
df = df_excel[df_excel['CLIENTE'].isin(clientes_validos)]
df = df.merge(df_csv[['CLIENTE', 'LAT', 'LON']], on='CLIENTE', how='left')
df = df[df['HORAS'].notna() & (df['HORAS'] > 0)]
df = df.reset_index(drop=True)
df['HORAS'] = df['HORAS'].astype(float)


# Distribuir trabajos (sin repetir clientes)
def distribuir_trabajos(df_trabajos):
    dias_semana = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    fecha = datetime(2025, 7, 1)
    semana_actual = 1
    horas_dia_max = 8
    horas_semana_max = 40
    plan = []

    horas_dia_actual = 0
    horas_semana_actual = 0
    dia_actual = fecha.strftime('%d/%m/%Y')
    trabajos_dia = []
    clientes_asignados = set()

    for _, fila in df_trabajos.sort_values(by='HORAS', ascending=False).iterrows():
        cliente = fila['CLIENTE']
        localidad = fila['LOCALIDAD']
        horas = fila['HORAS']

        if cliente in clientes_asignados:
            continue  # ya está asignado

        # ¿Hay que pasar al siguiente día?
        if horas_dia_actual + horas > horas_dia_max or fecha.strftime('%A') not in dias_semana:
            if trabajos_dia:
                plan.append((semana_actual, fecha.strftime('%A'), dia_actual, trabajos_dia.copy()))
            trabajos_dia.clear()
            horas_dia_actual = 0

            # Avanzamos al siguiente día laborable
            while True:
                fecha += timedelta(days=1)
                if fecha.strftime('%A') in dias_semana:
                    break
            dia_actual = fecha.strftime('%d/%m/%Y')
            if fecha.weekday() == 0:  # lunes, empieza nueva semana
                semana_actual += 1
                horas_semana_actual = 0

        # Si aún cabe el trabajo hoy
        if horas_dia_actual + horas <= horas_dia_max and horas_semana_actual + horas <= horas_semana_max:
            trabajos_dia.append((cliente, localidad, horas))
            horas_dia_actual += horas
            horas_semana_actual += horas
            clientes_asignados.add(cliente)

    # Agregar el último día si hay trabajos pendientes
    if trabajos_dia:
        plan.append((semana_actual, fecha.strftime('%A'), dia_actual, trabajos_dia.copy()))

    return plan


plan = distribuir_trabajos(df)

# Mostrar plan
semana_actual = None
for semana, dia, fecha, tareas in plan:
    if semana != semana_actual:
        print(f"\nSemana {semana}")
        semana_actual = semana
    print(f"  {dia} {fecha}")
    tareas_unicas = list({(c, l, h) for c, l, h in tareas})
    for cliente, localidad, horas in tareas_unicas:
        print(f"    ➤ {cliente}: {localidad} ({horas} h)")
