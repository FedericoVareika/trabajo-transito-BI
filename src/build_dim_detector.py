import os
import polars as pl
from pipeline_utils import (
    DATA_DIR, OUTPUT_DIR, load_and_standardize,
    list_csv_files, is_valid_csv,
)

VP_DIR = os.path.join(DATA_DIR, "velocidad_promedio")
CV_DIR = os.path.join(DATA_DIR, "conteo_vehicular")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    parts = []

    for d in [VP_DIR, CV_DIR]:
        for f in list_csv_files(d):
            p = os.path.join(d, f)
            if not is_valid_csv(p):
                continue
            df = (load_and_standardize(p)
                  .select(['cod_detector', 'dsc_avenida',
                           'dsc_int_anterior', 'dsc_int_siguiente',
                           'latitud', 'longitud'])
                  .unique(subset='cod_detector')
                  .with_columns([
                      pl.col('latitud').cast(pl.Float64),
                      pl.col('longitud').cast(pl.Float64),
                  ])
                  .rename({
                      'dsc_avenida': 'avenida',
                      'dsc_int_anterior': 'int_anterior',
                      'dsc_int_siguiente': 'int_siguiente',
                  }))
            parts.append(df)

    if not parts:
        print("No hay datos para dim_detector")
        return

    dim = (pl.concat(parts)
           .unique(subset='cod_detector')
           .sort('cod_detector')
           .with_row_index(name='id', offset=1)
           .rename({'cod_detector': 'codigo'})
           .select(['id', 'codigo', 'avenida', 'int_anterior',
                    'int_siguiente', 'latitud', 'longitud'])
           .collect())

    out_path = os.path.join(OUTPUT_DIR, 'dim_detector.csv')
    dim.write_csv(out_path)
    print(f"dim_detector.csv: {dim.height:,} filas")


if __name__ == "__main__":
    main()
