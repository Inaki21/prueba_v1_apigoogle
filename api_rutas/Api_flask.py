from flask import Flask, jsonify ,request
import pandas as pd
import csv
from datetime import datetime
from flask_cors import CORS 
from collections import defaultdict
from plan_api import generar_rutas_planificadas
import json

app = Flask(__name__)
CORS(app)  # Permite peticiones desde otras apps (frontend, móviles, etc.)

# Cargar datos
df = pd.read_csv("rutas_trabajo.csv")
df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True)

def leer_csv():
    elementos = []
    with open('rutas_trabajo.csv', newline='', encoding='utf-8') as archivo:
        lector = csv.DictReader(archivo)
        for fila in lector:
            elementos.append(fila)
    return elementos

# Transformar datos
from collections import defaultdict

from collections import defaultdict

from collections import defaultdict

from collections import defaultdict

from collections import defaultdict

def transformar_datos(datos_originales):
    rutas = []

    for registro in datos_originales:
        try:
            registro = {k.strip(): v for k, v in registro.items()}

            fecha = registro['Fecha']
            id_tecnico = int(registro['id_tecnico'])
            lat = registro.get('Lat')
            lon = registro.get('Lon')
            cliente = int(float(registro['Cliente']))
            tiempo = registro.get('Tiempo_Desplazamiento_min')

            visita = {'id_instalacion': cliente}
            if lat and lon:
                visita['lat'] = float(lat)
                visita['long'] = float(lon)
            if tiempo:
                visita['tiempo_llegada'] = float(tiempo)

            # Buscar si ya existe una ruta con esa fecha y técnico
            ruta_existente = next(
                (r for r in rutas if r['fecha'] == fecha and r['tecnicos'] == [id_tecnico]),
                None
            )

            if ruta_existente:
                ruta_existente['visitas'].append(visita)
            else:
                rutas.append({
                    'fecha': fecha,
                    'tecnicos': [id_tecnico],
                    'visitas': [visita]
                })

        except Exception as e:
            print(f"Error procesando registro: {registro}. Error: {str(e)}")
            continue

    # Ordenar rutas por fecha (formato dd/mm/yyyy)
    rutas.sort(key=lambda x: tuple(map(int, x['fecha'].split('/')[::-1])))

    return {'rutas': rutas}






@app.route('/api/elementos', methods=['GET'])
def obtener_elementos():
    datos = leer_csv()
    datos_finales = transformar_datos(datos)
    return jsonify(datos_finales)

@app.route('/api/elementos', methods=['POST'])
def recibir_json():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No se recibió un JSON válido"}), 400

        # Guardar el JSON en un archivo (opcional)
        with open('datos_recibidos.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        # Llamar a la función con el JSON directamente
        resultado = generar_rutas_planificadas('datos_recibidos.json', "matriz_tiempos_final.csv", lat_ollauri=42.539, lon_ollauri=-2.848)

        elemrtos_transformados = transformar_datos(resultado)
        
        # Devolver el resultado como respuesta
        return jsonify({"resultado": elemrtos_transformados}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000)    