import os
import polars as pl
import numpy as np

DATA_DIR = "data/estandarizado"
OUTPUT_DIR = "data/analitica"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def haversine_vectorized(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # Convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])
    
    # Haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a)) 
    r = 6371000 # Radius of earth in meters
    return c * r

def main():
    print("Iniciando análisis espacial y cálculo de métricas...")
    
    # 1. Cargar dimensiones y hechos
    print("\n1. Cargando datos...")
    dim_detector = pl.read_csv(os.path.join(DATA_DIR, "dim_detector.csv"))
    
    # Cargamos hechos de forma lazy para ahorrar memoria
    try:
        fact_velocidad = pl.scan_csv(os.path.join(DATA_DIR, "fact_velocidad_2022.csv"))
        fact_conteo = pl.scan_csv(os.path.join(DATA_DIR, "fact_conteo_2022.csv"))
        fact_siniestros = pl.read_csv(os.path.join(DATA_DIR, "fact_siniestros_2022.csv"))
    except FileNotFoundError as e:
        print(f"Error: No se encontraron los archivos estandarizados. Asegúrate de correr estandarizar_2022.py primero. Detalles: {e}")
        return

    # 2. Agrupar velocidad y conteo por detector
    print("\n2. Agrupando métricas de Velocidad y Volumen por detector...")
    
    stats_velocidad = (
        fact_velocidad
        .group_by("cod_detector")
        .agg([
            pl.col("velocidad").mean().alias("velocidad_media")
        ])
        .collect()
    )
    
    stats_conteo = (
        fact_conteo
        .group_by("cod_detector")
        .agg([
            pl.col("volume").sum().alias("volumen_total") # 'volume' o 'volumen_hora', usamos volume asumiendo que es granular.
        ])
        .collect()
    )
    
    # Unir las estadísticas al dim_detector
    tramos = dim_detector.join(stats_velocidad, on="cod_detector", how="left")
    tramos = tramos.join(stats_conteo, on="cod_detector", how="left")
    
    # Limpiar nulos (por si un detector no tiene datos de velocidad o volumen)
    tramos = tramos.fill_null(strategy="zero")
    
    # 3. Cruce Espacial (Siniestros a Detectores)
    print("\n3. Realizando Cruce Espacial: Asignando siniestros al detector más cercano...")
    
    # Extraer arrays de coordenadas de los detectores
    det_lats = tramos["latitud"].to_numpy()
    det_lons = tramos["longitud"].to_numpy()
    det_cods = tramos["cod_detector"].to_numpy()
    
    # Para cada siniestro, encontrar el cod_detector más cercano
    siniestro_lats = fact_siniestros["latitud"].to_numpy()
    siniestro_lons = fact_siniestros["longitud"].to_numpy()
    
    closest_detectors = []
    min_distances = []
    
    # Calculo vectorizado por cada siniestro
    for i in range(len(siniestro_lats)):
        slat = siniestro_lats[i]
        slon = siniestro_lons[i]
        
        # Ignorar siniestros sin coordenadas válidas
        if np.isnan(slat) or np.isnan(slon):
            closest_detectors.append(None)
            min_distances.append(None)
            continue
            
        distances = haversine_vectorized(slat, slon, det_lats, det_lons)
        min_idx = np.argmin(distances)
        
        closest_detectors.append(det_cods[min_idx])
        min_distances.append(distances[min_idx])
    
    # Agregar el detector asignado a los siniestros
    fact_siniestros = fact_siniestros.with_columns([
        pl.Series("cod_detector_asignado", closest_detectors),
        pl.Series("distancia_a_detector_m", min_distances)
    ])
    
    # Opcional: Filtrar siniestros que estén DEMASIADO lejos de cualquier detector (ej. > 1000m)
    # Por ahora los dejamos, pero lo limitamos a una distancia razonable en los conteos.
    # Vamos a contar cuántos siniestros hubo por detector (solo los que cayeron a < 500m para ser precisos)
    siniestros_validos = fact_siniestros.filter(pl.col("distancia_a_detector_m") <= 500)
    
    stats_siniestros = (
        siniestros_validos
        .group_by("cod_detector_asignado")
        .agg([
            pl.count().alias("cantidad_siniestros")
        ])
        .rename({"cod_detector_asignado": "cod_detector"})
    )
    
    tramos = tramos.join(stats_siniestros, on="cod_detector", how="left")
    tramos = tramos.fill_null(strategy="zero")
    
    # 4. Cálculo de Índices de Eficiencia y Riesgo
    print("\n4. Calculando Índices de Eficiencia y Riesgo...")
    
    # Normalizar Volumen y Velocidad (Min-Max Scaling) para el índice de eficiencia
    max_vol = tramos["volumen_total"].max()
    max_vel = tramos["velocidad_media"].max()
    
    if max_vol == 0: max_vol = 1
    if max_vel == 0: max_vel = 1
        
    tramos = tramos.with_columns([
        (pl.col("volumen_total") / max_vol).alias("volumen_norm"),
        (pl.col("velocidad_media") / max_vel).alias("velocidad_norm")
    ])
    
    tramos = tramos.with_columns([
        # Índice de Eficiencia: Volumen * Velocidad. (Muchos autos a alta velocidad = muy eficiente)
        (pl.col("volumen_norm") * pl.col("velocidad_norm") * 100).alias("indice_eficiencia"),
        
        # Índice de Riesgo: Siniestros / Volumen Normalizado (evitar division por cero)
        # Multiplicamos por un factor (ej. 1000) para que el número sea legible
        (pl.col("cantidad_siniestros") / (pl.col("volumen_norm") + 0.001) ).alias("indice_riesgo_raw")
    ])
    
    # Normalizar riesgo a 0-100 para PowerBI
    max_riesgo = tramos["indice_riesgo_raw"].max()
    if max_riesgo == 0: max_riesgo = 1
    
    tramos = tramos.with_columns([
        ((pl.col("indice_riesgo_raw") / max_riesgo) * 100).alias("indice_riesgo")
    ]).drop(["volumen_norm", "velocidad_norm", "indice_riesgo_raw"])
    
    # 5. Exportar resultados
    out_path = os.path.join(OUTPUT_DIR, "tramos_analitica_2022.csv")
    tramos.write_csv(out_path)
    
    print(f"\n¡Proceso completado! Archivo exportado a: {out_path}")
    print(f"Total de tramos analizados: {tramos.height}")
    print("Muestra de los datos:")
    print(tramos.head())

if __name__ == "__main__":
    main()

"""
=============================================================================
SALIDA PARA POWER BI (tramos_analitica_2022.csv)
=============================================================================
Este script genera la base geográfica y las métricas crudas por cuadra/tramo.
TODAS LAS COLUMNAS GENERADAS:
- detector_id: ID interno del sensor.
- cod_detector: Código del radar/sensor.
- avenida: Nombre exacto de la calle/avenida.
- latitud: Coordenada Y para el Mapa.
- longitud: Coordenada X para el Mapa.
- velocidad_media: Promedio anual de velocidad en ese punto.
- volumen_total: Suma de autos que pasaron por ahí en el año.
- cantidad_siniestros: Total de accidentes geográficamente cercanos a ese radar.
- indice_eficiencia (0-100): Qué tan fluido y con volumen es el tramo (más es mejor).
- indice_riesgo (0-100): Tasa de siniestros normalizada por el volumen (más es peor).

VISUALIZACIONES RECOMENDADAS:
1. Gráfico de Dispersión (Scatter Plot): 
   - Eje X: indice_eficiencia, Eje Y: indice_riesgo. (Permite detectar avenidas ineficientes y peligrosas al mismo tiempo).
2. Tabla / Matriz (Ranking): 
   - Filas: avenida. Valores: cantidad_siniestros, volumen_total. (Ordenado de mayor a menor para obtener el "Top 10 Peores Avenidas").
3. Gráfico de Barras Horizontales: 
   - Eje Y: avenida, Eje X: indice_eficiencia.
=============================================================================
"""
