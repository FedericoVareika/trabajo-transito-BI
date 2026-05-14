import os
import polars as pl
from pipeline_utils import (
    DATA_DIR, OUTPUT_DIR, load_and_standardize,
    parse_fecha, extract_hour, extract_minuto,
    list_csv_files, is_valid_csv,
)

VP_DIR = os.path.join(DATA_DIR, "velocidad_promedio")
CV_DIR = os.path.join(DATA_DIR, "conteo_vehicular")

MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
          'julio', 'agosto', 'setiembre', 'septiembre', 'octubre',
          'noviembre', 'diciembre']


def _get_month(filename):
    name = filename.lower()
    for m in MONTHS:
        if m in name:
            return m
    return None


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    dim_fecha_path = os.path.join(OUTPUT_DIR, 'dim_fecha.csv')
    dim_detector_path = os.path.join(OUTPUT_DIR, 'dim_detector.csv')

    if not os.path.exists(dim_fecha_path):
        print("dim_fecha.csv no encontrado. Ejecuta build_dim_fecha.py primero.")
        return
    if not os.path.exists(dim_detector_path):
        print("dim_detector.csv no encontrado. Ejecuta build_dim_detector.py primero.")
        return

    dim_fecha = pl.read_csv(dim_fecha_path, try_parse_dates=True)
    dim_detector = pl.read_csv(dim_detector_path)

    vp_files = {_get_month(f): f for f in list_csv_files(VP_DIR) if _get_month(f)}
    cv_files = {_get_month(f): f for f in list_csv_files(CV_DIR) if _get_month(f)}
    common_months = sorted(set(vp_files) & set(cv_files))

    if not common_months:
        print("No hay meses en común entre VP y CV")
        return

    temp_files = []
    for month in common_months:
        vp = (load_and_standardize(os.path.join(VP_DIR, vp_files[month]))
              .pipe(parse_fecha).pipe(extract_hour).pipe(extract_minuto)
              .select(['fecha_dt', 'hora_int', 'minuto',
                       'cod_detector', 'id_carril', 'velocidad'])
              .rename({'fecha_dt': 'fecha', 'hora_int': 'hora'})
              .unique(subset=['fecha', 'hora', 'minuto', 'cod_detector', 'id_carril']))

        cv = (load_and_standardize(os.path.join(CV_DIR, cv_files[month]))
              .pipe(parse_fecha).pipe(extract_hour).pipe(extract_minuto)
              .select(['fecha_dt', 'hora_int', 'minuto',
                       'cod_detector', 'id_carril', 'volume', 'volumen_hora'])
              .rename({'fecha_dt': 'fecha', 'hora_int': 'hora'})
              .unique(subset=['fecha', 'hora', 'minuto', 'cod_detector', 'id_carril']))

        joined = vp.join(cv, on=['fecha', 'hora', 'minuto', 'cod_detector', 'id_carril'],
                         how='left')

        temp_path = os.path.join(OUTPUT_DIR, f'_fact_medicion_{month}.csv')
        (joined
         .join(dim_fecha.lazy(), on='fecha', how='left')
         .join(dim_detector.lazy(), left_on='cod_detector', right_on='codigo', how='left')
         .with_columns(
             pl.format("{}:{}:00",
                       pl.col('hora').cast(pl.Utf8),
                       pl.col('minuto').cast(pl.Utf8))
             .str.to_time('%H:%M:%S').alias('hora_t')
         )
         .select([
             pl.col('id').alias('fecha_id'),
             pl.col('id_right').alias('detector_id'),
             'hora_t', 'id_carril', 'velocidad', 'volume', 'volumen_hora',
         ])
         .rename({'hora_t': 'hora'})
         .sink_csv(temp_path, engine='streaming'))
        temp_files.append(temp_path)
        print(f"  {month}: {os.path.getsize(temp_path) / 1024 / 1024:.0f} MB")

    out_path = os.path.join(OUTPUT_DIR, 'fact_medicion.csv')
    with open(out_path, 'w') as out:
        for i, tf in enumerate(temp_files):
            with open(tf, 'r') as f:
                if i == 0:
                    out.write(f.read())
                else:
                    next(f)
                    out.write(f.read())
            os.remove(tf)

    print(f"fact_medicion.csv exportado ({os.path.getsize(out_path) / 1024 / 1024:.0f} MB)")


if __name__ == "__main__":
    main()
