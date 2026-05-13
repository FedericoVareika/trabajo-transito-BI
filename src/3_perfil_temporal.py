import os
import polars as pl

DATA_DIR = "data/estandarizado"
OUTPUT_DIR = "data/analitica"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def main():
    print("Iniciando creación del Perfil Temporal de Movilidad...")
    
    try:
        dim_fecha = pl.read_csv(os.path.join(DATA_DIR, "dim_fecha.csv"))
        fact_velocidad = pl.scan_csv(os.path.join(DATA_DIR, "fact_velocidad_2022.csv"))
        fact_conteo = pl.scan_csv(os.path.join(DATA_DIR, "fact_conteo_2022.csv"))
    except FileNotFoundError as e:
        print(f"Error: No se encontraron los archivos. Debes correr estandarizar_2022.py primero. Detalles: {e}")
        return

    # Nos interesan solo algunas columnas de la fecha para el perfil
    dim_fecha = dim_fecha.select(["fecha", "hora", "mes", "dia_semana"]).unique()

    print("\n1. Agregando Velocidad...")
    perfil_vel = (
        fact_velocidad
        .join(dim_fecha.lazy(), on=["fecha", "hora"], how="left")
        .group_by(["cod_detector", "mes", "dia_semana", "hora"])
        .agg([
            pl.col("velocidad").mean().alias("velocidad_media")
        ])
    )

    print("2. Agregando Volumen...")
    perfil_vol = (
        fact_conteo
        .join(dim_fecha.lazy(), on=["fecha", "hora"], how="left")
        .group_by(["cod_detector", "mes", "dia_semana", "hora"])
        .agg([
            pl.col("volume").sum().alias("volumen_total")
        ])
    )

    print("3. Uniendo perfiles...")
    # Full outer join porque puede haber horas con volumen pero sin datos de velocidad o viceversa
    perfil_temporal = perfil_vel.join(
        perfil_vol, 
        on=["cod_detector", "mes", "dia_semana", "hora"], 
        how="full", 
        coalesce=True
    ).fill_null(strategy="zero").collect()

    out_path = os.path.join(OUTPUT_DIR, "perfil_temporal_2022.csv")
    perfil_temporal.write_csv(out_path)
    
    print(f"\n¡Proceso completado! Archivo exportado a: {out_path}")
    print(f"Total de filas agregadas (resolución hora/dia/mes/calle): {perfil_temporal.height}")
    print("Muestra de los datos:")
    print(perfil_temporal.head())

if __name__ == "__main__":
    main()

"""
=============================================================================
SALIDA PARA POWER BI (perfil_temporal_2022.csv)
=============================================================================
Este script genera la tabla de dimensiones temporales para gráficos de tendencia.
TODAS LAS COLUMNAS GENERADAS:
- cod_detector: Para cruzar con el resto de datos o filtrar una sola calle.
- mes: Mes del año (1 a 12).
- dia_semana: Día de la semana (ej. 0=Lunes, 6=Domingo).
- hora: Hora del día (0 a 23).
- velocidad_media: Promedio de velocidad para esa hora exacta.
- volumen_total: Sumatoria de vehículos que pasaron en esa hora.

VISUALIZACIONES RECOMENDADAS:
1. Gráfico de Líneas (Curva de Hora Pico):
   - Eje X: hora. Eje Y: velocidad_media. Leyenda: dia_semana. (Compara la hora pico entre días hábiles vs fines de semana).
2. Gráfico de Columnas Agrupadas y Líneas (Estacionalidad):
   - Eje X: mes. Eje Y (Columna): volumen_total. Eje Y (Línea): velocidad_media.
3. Mapa de Calor (Visual de Matriz):
   - Filas: dia_semana. Columnas: hora. Valores: volumen_total (Color de fondo de celda dinámico para ver rápidamente cuándo hay más flujo).
=============================================================================
"""
