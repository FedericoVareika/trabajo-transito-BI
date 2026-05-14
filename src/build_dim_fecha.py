import os
import polars as pl
from pipeline_utils import (
    DATA_DIR, OUTPUT_DIR, load_and_standardize,
    parse_fecha, list_csv_files, is_valid_csv, SIN_MAPPING,
)

VP_DIR = os.path.join(DATA_DIR, "velocidad_promedio")
CV_DIR = os.path.join(DATA_DIR, "conteo_vehicular")
SIN_DIR = os.path.join(DATA_DIR, "lesionados_en_siniestros")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    parts = []

    for d in [VP_DIR, CV_DIR]:
        for f in list_csv_files(d):
            p = os.path.join(d, f)
            if not is_valid_csv(p):
                continue
            df = (load_and_standardize(p)
                  .pipe(parse_fecha)
                  .select(['fecha_dt']).unique())
            parts.append(df)

    for f in list_csv_files(SIN_DIR):
        p = os.path.join(SIN_DIR, f)
        if not is_valid_csv(p):
            continue
        df = (load_and_standardize(p, SIN_MAPPING)
              .pipe(parse_fecha)
              .select(['fecha_dt']).unique())
        parts.append(df)

    if not parts:
        print("No hay datos para dim_fecha")
        return

    dim = (pl.concat(parts).filter(pl.col('fecha_dt').is_not_null())
           .unique().sort('fecha_dt')
           .with_columns([
               pl.col('fecha_dt').dt.year().alias('anio'),
               pl.col('fecha_dt').dt.month().alias('mes'),
               pl.col('fecha_dt').dt.day().alias('dia'),
           ])
           .with_row_index(name='id', offset=1)
           .select(['id', 'fecha_dt', 'anio', 'mes', 'dia'])
           .rename({'fecha_dt': 'fecha'})
           .collect())

    out_path = os.path.join(OUTPUT_DIR, 'dim_fecha.csv')
    dim.write_csv(out_path)
    print(f"dim_fecha.csv: {dim.height:,} filas")


if __name__ == "__main__":
    main()
