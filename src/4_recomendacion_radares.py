import os
import polars as pl
import numpy as np

DATA_DIR = "data/analitica"
OUTPUT_DIR = "data/analitica"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def main():
    in_path = os.path.join(DATA_DIR, "tramos_analitica_2022.csv")
    if not os.path.exists(in_path):
        print(f"Error: No se encontró {in_path}. Corre src/1_analitica_espacial.py primero.")
        return

    tramos = pl.read_csv(in_path)
    
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
    
    tramos = tramos.with_columns([
        (((pl.col("norm_vel") * 0.40) + 
          (pl.col("norm_acc") * 0.40) + 
          (pl.col("norm_vol") * 0.20)) * 100).alias("score_radar")
    ])
    
    p85 = tramos.select(pl.col("score_radar").quantile(0.85)).item()
    p50 = tramos.select(pl.col("score_radar").quantile(0.50)).item()
    
    tramos = tramos.with_columns(
        pl.when(pl.col("score_radar") >= p85).then(pl.lit("Prioridad Alta (Instalar)"))
        .when(pl.col("score_radar") >= p50).then(pl.lit("Prioridad Media (Monitorear)"))
        .otherwise(pl.lit("Prioridad Baja (Seguro)")).alias("prioridad_radar")
    )
    
    tramos = tramos.with_columns(
        pl.when(pl.col("prioridad_radar") == "Prioridad Alta (Instalar)").then(pl.lit("Rojo"))
        .when(pl.col("prioridad_radar") == "Prioridad Media (Monitorear)").then(pl.lit("Amarillo"))
        .otherwise(pl.lit("Gris")).alias("color_radar_powerbi")
    )
    
    tramos = tramos.drop(["norm_vel", "norm_acc", "norm_vol"])
    
    out_path = os.path.join(OUTPUT_DIR, "recomendacion_radares_2022.csv")
    tramos.write_csv(out_path)

if __name__ == "__main__":
    main()
