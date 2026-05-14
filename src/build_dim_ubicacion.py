import os
import polars as pl
from pipeline_utils import (
    DATA_DIR, OUTPUT_DIR, load_and_standardize,
    list_csv_files, is_valid_csv, SIN_MAPPING, utm_to_latlon,
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
                  .select(['dsc_avenida', 'latitud', 'longitud']).unique()
                  .with_columns([
                      pl.col('latitud').cast(pl.Float64),
                      pl.col('longitud').cast(pl.Float64),
                      pl.lit('avenida').alias('tipo'),
                  ])
                  .rename({'dsc_avenida': 'descripcion'}))
            parts.append(df)

    for f in list_csv_files(SIN_DIR):
        p = os.path.join(SIN_DIR, f)
        if not is_valid_csv(p):
            continue
        c = (load_and_standardize(p, SIN_MAPPING)
             .select(['calle', 'x', 'y']).unique().collect())
        if c.is_empty():
            continue
        ll = [utm_to_latlon(r['x'], r['y']) for r in c.iter_rows(named=True)]
        sin_ub = pl.DataFrame({
            'descripcion': c['calle'].to_list(),
            'latitud': [x[0] for x in ll],
            'longitud': [x[1] for x in ll],
            'tipo': ['calle_siniestro'] * len(c),
        }).lazy()
        parts.append(sin_ub)

    if not parts:
        print("No hay datos para dim_ubicacion")
        return

    dim = (pl.concat(parts)
           .unique()
           .group_by(['latitud', 'longitud'])
           .agg([
               pl.col('descripcion').str.join(' / ').alias('descripcion'),
               pl.col('tipo').first().alias('tipo'),
           ])
           .sort('descripcion')
           .with_row_index(name='id', offset=1)
           .select(['id', 'descripcion', 'latitud', 'longitud', 'tipo'])
           .collect())

    out_path = os.path.join(OUTPUT_DIR, 'dim_ubicacion.csv')
    dim.write_csv(out_path)
    print(f"dim_ubicacion.csv: {dim.height:,} filas")


if __name__ == "__main__":
    main()
