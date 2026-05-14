import os
import polars as pl
import numpy as np

DATA_DIR = "data/analitica"
OUTPUT_DIR = "data/analitica"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def main():
    print("Iniciando Modelo de Recomendación de Radares...")
    
    in_path = os.path.join(DATA_DIR, "tramos_analitica_2022.csv")
    if not os.path.exists(in_path):
        print(f"Error: No se encontró {in_path}. Corre src/1_analitica_espacial.py primero.")
        return

    tramos = pl.read_csv(in_path)
    
    # 1. Normalización Min-Max (0 a 1) para las 3 variables clave
    print("1. Normalizando variables (Velocidad, Accidentes, Volumen)...")
    
    max_vel = tramos["velocidad_media"].max()
    max_acc = tramos["cantidad_siniestros"].max()
    max_vol = tramos["volumen_total"].max()
    
    if max_vel == 0: max_vel = 1
    if max_acc == 0: max_acc = 1
    if max_vol == 0: max_vol = 1
    
    tramos = tramos.with_columns([
        (pl.col("velocidad_media") / max_vel).alias("norm_vel"),
        (pl.col("cantidad_siniestros") / max_acc).alias("norm_acc"),
        (pl.col("volumen_total") / max_vol).alias("norm_vol")
    ])
    
    # 2. Algoritmo de Scoring (40% Velocidad, 40% Accidentes, 20% Volumen)
    print("2. Calculando Score de Necesidad de Fiscalización (0-100)...")
    
    tramos = tramos.with_columns([
        (((pl.col("norm_vel") * 0.40) + 
          (pl.col("norm_acc") * 0.40) + 
          (pl.col("norm_vol") * 0.20)) * 100).alias("score_radar")
    ])
    
    # 3. Categorización de Prioridades usando Cuartiles (Percentiles)
    print("3. Asignando niveles de prioridad...")
    
    # Usamos percentiles: Top 15% es Alta Prioridad, siguiente 35% Media, resto Baja.
    p85 = tramos.select(pl.col("score_radar").quantile(0.85)).item()
    p50 = tramos.select(pl.col("score_radar").quantile(0.50)).item()
    
    tramos = tramos.with_columns(
        pl.when(pl.col("score_radar") >= p85).then(pl.lit("Prioridad Alta (Instalar)"))
        .when(pl.col("score_radar") >= p50).then(pl.lit("Prioridad Media (Monitorear)"))
        .otherwise(pl.lit("Prioridad Baja (Seguro)")).alias("prioridad_radar")
    )
    
    # Colores para PowerBI
    tramos = tramos.with_columns(
        pl.when(pl.col("prioridad_radar") == "Prioridad Alta (Instalar)").then(pl.lit("Rojo"))
        .when(pl.col("prioridad_radar") == "Prioridad Media (Monitorear)").then(pl.lit("Amarillo"))
        .otherwise(pl.lit("Gris")).alias("color_radar_powerbi")
    )
    
    # Limpiamos las columnas temporales de normalización
    tramos = tramos.drop(["norm_vel", "norm_acc", "norm_vol"])
    
    # 4. Exportar
    out_path = os.path.join(OUTPUT_DIR, "recomendacion_radares_2022.csv")
    tramos.write_csv(out_path)
    
    print(f"\n¡Modelo completado! Archivo guardado en {out_path}")
    print("\nResumen de Recomendaciones:")
    print(tramos.group_by("prioridad_radar").agg(pl.len().alias("cantidad_calles")).sort("cantidad_calles"))

if __name__ == "__main__":
    main()

"""
=============================================================================
SALIDA PARA POWER BI (recomendacion_radares_2022.csv)
=============================================================================
Este script genera un modelo prescriptivo para instalar radares de velocidad.
TODAS LAS COLUMNAS GENERADAS:
- detector_id: ID interno del sensor.
- cod_detector: Código del radar/sensor.
- avenida: Nombre exacto de la calle/avenida.
- latitud: Coordenada Y para el Mapa.
- longitud: Coordenada X para el Mapa.
- velocidad_media: Promedio anual de velocidad.
- volumen_total: Suma de autos anual.
- cantidad_siniestros: Total de accidentes.
- indice_eficiencia: Indicador base de fluidez.
- indice_riesgo: Indicador base de peligrosidad.
- score_radar (0-100): Puntuación matemática del modelo de fiscalización.
- prioridad_radar: Etiqueta de decisión ("Prioridad Alta (Instalar)", "Media", "Baja").
- color_radar_powerbi: Colores sugeridos (Rojo, Amarillo, Gris) para visuales.

VISUALIZACIONES RECOMENDADAS:
1. Mapa (Mapa de Inversión en Radares):
   - Ubicación: latitud y longitud. Leyenda: prioridad_radar. (Para mostrar a la Intendencia exactamente dónde enviar a los técnicos a instalar equipos).
2. Gráfico de Embudos (Funnel Chart):
   - Categoría: prioridad_radar. Valores: Recuento de cod_detector. (Muestra visualmente cuántas calles entran en el filtro crítico para presupuesto).
3. Tabla de Acción (Top Prioridades):
   - Filtro (Slicer): prioridad_radar = "Prioridad Alta (Instalar)"
   - Filas: avenida. Valores: score_radar, velocidad_media, cantidad_siniestros. (Se le entrega a la gerencia como reporte final).
=============================================================================
"""
