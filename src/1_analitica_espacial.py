import os
import polars as pl
import numpy as np

DATA_DIR = "data/estandarizado"
OUTPUT_DIR = "data/analitica"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def haversine_vectorized(lat1, lon1, lat2, lon2):
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    r = 6371000
    return c * r

def main():
    print("Iniciando análisis espacial y cálculo de métricas...")

    print("\n1. Cargando datos...")
    dim_detector = pl.read_csv(os.path.join(DATA_DIR, "dim_detector.csv"))
    dim_ubicacion = pl.read_csv(os.path.join(DATA_DIR, "dim_ubicacion.csv"))

    try:
        fact_medicion = pl.scan_csv(os.path.join(DATA_DIR, "fact_medicion.csv"))
        fact_siniestros = pl.read_csv(os.path.join(DATA_DIR, "fact_siniestros.csv"))
    except FileNotFoundError as e:
        print(f"Error: No se encontraron archivos estandarizados. Ejecuta el pipeline primero. Detalles: {e}")
        return

    print("\n2. Agrupando métricas de Velocidad y Volumen por detector...")

    stats_detector = (
        fact_medicion
        .join(dim_detector.lazy(), left_on='detector_id', right_on='id', how='inner')
        .group_by("codigo")
        .agg([
            pl.col("velocidad").mean().alias("velocidad_media"),
            pl.col("volume").sum().alias("volumen_total"),
        ])
        .collect()
    )

    tramos = dim_detector.join(
        stats_detector, on="codigo", how="left"
    ).fill_null(strategy="zero").rename({"codigo": "cod_detector"})

    print(f"   {tramos.height} detectores con datos")

    print("\n3. Realizando Cruce Espacial: Asignando siniestros al detector más cercano...")

    fact_siniestros = fact_siniestros.join(
        dim_ubicacion.select(["id", "latitud", "longitud"]),
        left_on="ubicacion_id", right_on="id", how="inner"
    )

    det_lats = tramos["latitud"].to_numpy()
    det_lons = tramos["longitud"].to_numpy()
    det_cods = tramos["cod_detector"].to_numpy()

    siniestro_lats = fact_siniestros["latitud"].to_numpy()
    siniestro_lons = fact_siniestros["longitud"].to_numpy()

    closest_detectors = []
    min_distances = []

    for i in range(len(siniestro_lats)):
        slat = siniestro_lats[i]
        slon = siniestro_lons[i]

        if np.isnan(slat) or np.isnan(slon):
            closest_detectors.append(None)
            min_distances.append(None)
            continue

        distances = haversine_vectorized(slat, slon, det_lats, det_lons)
        min_idx = np.argmin(distances)

        closest_detectors.append(det_cods[min_idx])
        min_distances.append(distances[min_idx])

    fact_siniestros = fact_siniestros.with_columns([
        pl.Series("cod_detector_asignado", closest_detectors),
        pl.Series("distancia_a_detector_m", min_distances)
    ])

    siniestros_validos = fact_siniestros.filter(pl.col("distancia_a_detector_m") <= 500)

    stats_siniestros = (
        siniestros_validos
        .group_by("cod_detector_asignado")
        .agg([
            pl.len().alias("cantidad_siniestros")
        ])
        .rename({"cod_detector_asignado": "cod_detector"})
    )

    tramos = tramos.join(stats_siniestros, on="cod_detector", how="left")
    tramos = tramos.fill_null(strategy="zero")

    print("\n4. Calculando Índices de Eficiencia y Riesgo...")

    max_vol = tramos["volumen_total"].max()
    max_vel = tramos["velocidad_media"].max()

    if max_vol == 0: max_vol = 1
    if max_vel == 0: max_vel = 1

    tramos = tramos.with_columns([
        (pl.col("volumen_total") / max_vol).alias("volumen_norm"),
        (pl.col("velocidad_media") / max_vel).alias("velocidad_norm")
    ])

    tramos = tramos.with_columns([
        (pl.col("volumen_norm") * pl.col("velocidad_norm") * 100).alias("indice_eficiencia"),
        (pl.col("cantidad_siniestros") / (pl.col("volumen_norm") + 0.001)).alias("indice_riesgo_raw")
    ])

    max_riesgo = tramos["indice_riesgo_raw"].max()
    if max_riesgo == 0: max_riesgo = 1

    tramos = tramos.with_columns([
        ((pl.col("indice_riesgo_raw") / max_riesgo) * 100).alias("indice_riesgo")
    ]).drop(["volumen_norm", "velocidad_norm", "indice_riesgo_raw"])

    out_path = os.path.join(OUTPUT_DIR, "tramos_analitica_2022.csv")
    tramos.write_csv(out_path)

    print(f"\nProceso completado! Archivo exportado a: {out_path}")
    print(f"Total de tramos analizados: {tramos.height}")
    print("Muestra de los datos:")
    print(tramos.head())

if __name__ == "__main__":
    main()
