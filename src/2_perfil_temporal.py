import os
import polars as pl

DATA_DIR = "data/estandarizado"
OUTPUT_DIR = "data/analitica"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def main():
    print("Iniciando creación del Perfil Temporal de Movilidad...")

    try:
        dim_fecha = pl.read_csv(os.path.join(DATA_DIR, "dim_fecha.csv"), try_parse_dates=True)
        dim_detector = pl.read_csv(os.path.join(DATA_DIR, "dim_detector.csv"))
        fact_medicion = pl.scan_csv(os.path.join(DATA_DIR, "fact_medicion.csv"))
    except FileNotFoundError as e:
        print(f"Error: No se encontraron archivos. Ejecuta el pipeline primero. Detalles: {e}")
        return

    dim_fecha = dim_fecha.select(["id", "fecha", "mes"])
    dim_detector = dim_detector.select(["id", "codigo", "avenida", "latitud", "longitud"])

    print("\n1. Agregando métricas por hora, día, mes y detector...")
    perfil = (
        fact_medicion
        .with_columns(
            pl.col("hora").str.to_time("%H:%M:%S%.f", strict=False).alias("hora")
        )
        .join(dim_fecha.lazy(), left_on="fecha_id", right_on="id", how="inner")
        .join(dim_detector.lazy(), left_on="detector_id", right_on="id", how="inner")
        .with_columns([
            pl.col("fecha").dt.weekday().map_elements(
                lambda x: ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'][x-1],
                return_dtype=pl.Utf8
            ).alias("dia_semana"),
            pl.col("hora").dt.hour().alias("hora"),
        ])
        .group_by(["codigo", "avenida", "latitud", "longitud", "mes", "dia_semana", "hora"])
        .agg([
            pl.col("velocidad").mean().alias("velocidad_media"),
            pl.col("volume").sum().alias("volumen_total"),
        ])
        .fill_null(strategy="zero")
        .rename({"codigo": "cod_detector"})
        .collect()
    )

    out_path = os.path.join(OUTPUT_DIR, "perfil_temporal_2022.csv")
    perfil.write_csv(out_path)

    print(f"\nProceso completado! Archivo exportado a: {out_path}")
    print(f"Total de filas agregadas (resolución hora/dia/mes/detector): {perfil.height}")
    print("Muestra de los datos:")
    print(perfil.head())

if __name__ == "__main__":
    main()

"""
=============================================================================
SALIDA PARA POWER BI (perfil_temporal_2022.csv)
=============================================================================
Este script agrega velocidad media y volumen total por hora, día de la
semana, mes y detector, permitiendo analizar patrones temporales de
movilidad en Montevideo.

TODAS LAS COLUMNAS GENERADAS:
- cod_detector: Código del radar/sensor.
- avenida: Nombre de la avenida/calle.
- latitud: Coordenada Y para el Mapa.
- longitud: Coordenada X para el Mapa.
- mes: Número de mes (1=enero, 12=diciembre).
- dia_semana: Día de la semana (monday a sunday).
- hora: Hora del día (0 a 23).
- velocidad_media: Velocidad promedio en esa hora/dia/mes.
- volumen_total: Volumen total de vehículos en esa hora/dia/mes.

VISUALIZACIONES RECOMENDADAS:
1. Evolución Horaria (Líneas):
   - Eje X: hora. Eje Y: volumen_total.
   - Leyenda: dia_semana. (Para comparar el flujo vehicular
     entre días laborales vs fin de semana).
2. Heatmap de Velocidad:
   - Eje X: hora. Eje Y: dia_semana.
     Color: velocidad_media. (Para detectar horas pico de
     congestión según el día).
3. Gráfico de Columnas por Mes:
   - Eje X: mes. Eje Y: volumen_total.
     Leyenda: cod_detector (con slicer). (Para ver tendencias
     estacionales del tránsito).
4. Segmentadores (Slicers):
   - Campos: cod_detector, mes, dia_semana. (Filtros maestros
     para aislar combinaciones específicas de detector y tiempo).
=============================================================================
"""
