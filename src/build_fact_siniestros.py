import os
import polars as pl
from pipeline_utils import (
    DATA_DIR, OUTPUT_DIR, load_and_standardize,
    parse_fecha, extract_hour,
    list_csv_files, is_valid_csv, SIN_MAPPING, utm_to_latlon,
)

SIN_DIR = os.path.join(DATA_DIR, "lesionados_en_siniestros")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    dim_fecha_path = os.path.join(OUTPUT_DIR, 'dim_fecha.csv')
    dim_ubicacion_path = os.path.join(OUTPUT_DIR, 'dim_ubicacion.csv')

    if not os.path.exists(dim_fecha_path):
        print("dim_fecha.csv no encontrado. Ejecuta build_dim_fecha.py primero.")
        return
    if not os.path.exists(dim_ubicacion_path):
        print("dim_ubicacion.csv no encontrado. Ejecuta build_dim_ubicacion.py primero.")
        return

    dim_fecha = pl.read_csv(dim_fecha_path, try_parse_dates=True)
    dim_ubicacion = pl.read_csv(dim_ubicacion_path)

    parts = []
    for f in list_csv_files(SIN_DIR):
        p = os.path.join(SIN_DIR, f)
        if not is_valid_csv(p):
            continue

        c = (load_and_standardize(p, SIN_MAPPING)
             .pipe(parse_fecha).pipe(extract_hour)
             .select(['fecha_dt', 'hora_int', 'tipo_resultado', 'tipo_siniestro',
                      'usa_cinturon', 'usa_casco', 'edad', 'sexo', 'x', 'y'])
             .unique().collect())

        if c.is_empty():
            continue

        ll = [utm_to_latlon(r['x'], r['y']) for r in c.iter_rows(named=True)]
        c = c.with_columns([
            pl.Series([x[0] for x in ll]).alias('latitud'),
            pl.Series([x[1] for x in ll]).alias('longitud'),
        ]).drop(['x', 'y'])
        str_cols = [col for col, dtype in c.schema.items() if dtype == pl.Utf8]
        if str_cols:
            c = c.with_columns([pl.col(col).str.strip_chars() for col in str_cols])
        parts.append(c.lazy())

    if not parts:
        print("No hay datos para fact_siniestros")
        return

    out_path = os.path.join(OUTPUT_DIR, 'fact_siniestros.csv')

    (pl.concat(parts)
     .join(dim_fecha.lazy(), left_on='fecha_dt', right_on='fecha', how='left')
     .join(dim_ubicacion.lazy(), on=['latitud', 'longitud'], how='inner')
     .select([
         pl.col('id').alias('fecha_id'),
         pl.col('id_right').alias('ubicacion_id'),
         'tipo_resultado', 'tipo_siniestro',
         'usa_cinturon', 'usa_casco', 'edad', 'sexo',
     ])
     .sink_csv(out_path))

    print("fact_siniestros.csv exportado")


if __name__ == "__main__":
    main()
