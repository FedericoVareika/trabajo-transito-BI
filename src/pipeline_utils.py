import os
import polars as pl
from pyproj import Transformer

DATA_DIR = "data"
OUTPUT_DIR = os.path.join(DATA_DIR, "estandarizado")

SIN_MAPPING = {
    'tipo_de_resultado': 'tipo_resultado',
    'tipo_de_siniestro': 'tipo_siniestro',
    'dia_de_la_semana': 'dia_semana',
    'tipo_de_vehiculo': 'tipo_vehiculo',
    'dida_de_la_semana': 'dia_semana',
    'usa_cinturin': 'usa_cinturon',
}

_utm_transformer = Transformer.from_crs("EPSG:32721", "EPSG:4326", always_xy=True)

def standardize_columns(cols):
    return [str(c).replace('\ufeff', '').replace('\ufffd', '').strip()
            .lower().replace(' ', '_')
            .replace('á', 'a').replace('é', 'e').replace('í', 'i')
            .replace('ó', 'o').replace('ú', 'u').replace('ñ', 'n')
            for c in cols]

def load_and_standardize(path, extra_rename=None):
    df = pl.scan_csv(path, has_header=True, ignore_errors=True,
                     null_values=["SIN DATOS", "N/A", "",
                                  " SIN DATOS", " N/A",
                                  "SIN DATOS ", " SIN DATOS ",
                                  "NO", " NO"])
    cols = df.collect_schema().names()
    new_cols = standardize_columns(cols)
    rename_map = {old: new for old, new in zip(cols, new_cols) if old != new}
    df = df.rename(rename_map)
    if extra_rename:
        existing = {k: v for k, v in extra_rename.items()
                    if k in df.collect_schema().names()}
        if existing:
            df = df.rename(existing)
    return df

def is_valid_csv(path):
    try:
        with open(path, 'rb') as f:
            return f.read(2) != b'PK'
    except:
        return False

def parse_fecha(df):
    return df.with_columns([
        pl.col('fecha').str.to_date('%Y-%m-%d', strict=False).alias('fd1'),
        pl.col('fecha').str.to_date('%d/%m/%Y', strict=False).alias('fd2'),
    ]).with_columns(pl.coalesce(['fd1', 'fd2']).alias('fecha_dt')).drop('fd1', 'fd2')

def extract_hour(df):
    return df.with_columns(
        pl.when(pl.col('hora').cast(pl.Utf8).str.contains(':'))
        .then(pl.col('hora').cast(pl.Utf8).str.split(':').list.first().cast(pl.Int32))
        .otherwise(pl.col('hora').cast(pl.Int32, strict=False).fill_null(0))
        .alias('hora_int'))

def extract_minuto(df):
    return df.with_columns(
        pl.when(pl.col('hora').cast(pl.Utf8).str.contains(':'))
        .then(pl.col('hora').cast(pl.Utf8).str.split(':').list.get(1).cast(pl.Int32))
        .otherwise(pl.lit(0))
        .alias('minuto'))

def utm_to_latlon(x, y):
    if x is None or y is None:
        return None, None
    try:
        lon, lat = _utm_transformer.transform(float(x), float(y))
        return lat, lon
    except:
        return None, None

def list_csv_files(dir_path):
    return sorted([
        f for f in os.listdir(dir_path)
        if f.endswith('.csv') and not f.endswith('.etag')
    ])
