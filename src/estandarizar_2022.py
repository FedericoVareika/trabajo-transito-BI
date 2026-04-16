import os
import polars as pl
from pyproj import Transformer

# EPSG:32721 = UTM Zone 21S (WGS84) - Uruguay
utm_transformer = Transformer.from_crs("EPSG:32721", "EPSG:4326", always_xy=True)

def utm_to_latlon(x, y):
    if x is None or y is None:
        return None, None
    try:
        lon, lat = utm_transformer.transform(float(x), float(y))
        return lat, lon
    except:
        return None, None

DATA_DIR = "data"
OUTPUT_DIR = os.path.join(DATA_DIR, "estandarizado")

os.makedirs(OUTPUT_DIR, exist_ok=True)

EXPECTED_VELOCIDAD_COLS = 10
EXPECTED_CONTEO_COLS = 11
EXPECTED_SINIESTROS_COLS = 19

def filter_2022(files):
    return [f for f in files if '2022' in f.lower() and not f.endswith('.etag')]

def is_valid_csv(path):
    try:
        with open(path, 'rb') as f:
            return f.read(2) != b'PK'
    except:
        return False

def standardize_columns(columns):
    return [str(c).replace('\ufeff', '').strip().lower().replace(' ', '_').replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ú','u').replace('ñ','n') for c in columns]

def load_dataset_lazy(directory, files, expected_cols, col_mapping, filter_2022_fn=None):
    dfs = []
    for f in files:
        path = os.path.join(directory, f)
        if not os.path.isfile(path) or not is_valid_csv(path):
            print(f"    Saltando {f}")
            continue
        
        try:
            schema = pl.scan_csv(path, has_header=True, ignore_errors=True, null_values=["SIN DATOS", "N/A", ""]).collect_schema()
            if len(schema.names()) != expected_cols:
                print(f"    Saltando {f}: columnas {len(schema.names())} != {expected_cols}")
                continue
            
            df = pl.scan_csv(path, has_header=True, ignore_errors=True, null_values=["SIN DATOS", "N/A", ""])
            cols = df.collect_schema().names()
            new_cols = standardize_columns(cols)
            rename_map = {old: new for old, new in zip(cols, new_cols) if old != new}
            for src, tgt in col_mapping.items():
                if src in rename_map:
                    rename_map[rename_map[src]] = tgt
                elif src in cols:
                    rename_map[src] = tgt
            
            df = df.rename(rename_map)
            df = df.with_columns(pl.lit(f).alias('_source'))
            dfs.append(df)
        except Exception as e:
            print(f"    Error {f}: {e}")
    
    if not dfs:
        return None
    
    combined = pl.concat(dfs)
    
    if filter_2022_fn:
        combined = filter_2022_fn(combined)
    
    return combined

def parse_fecha(df):
    return df.with_columns([
        pl.col('fecha').str.to_date(format='%Y-%m-%d', strict=False).alias('fecha_dt'),
        pl.col('fecha').str.to_date(format='%d/%m/%Y', strict=False).alias('fecha_dt2'),
    ]).with_columns(
        pl.coalesce(['fecha_dt', 'fecha_dt2']).alias('fecha_dt')
    ).drop('fecha_dt2')

def extract_hour(df):
    return df.with_columns(
        pl.when(pl.col('hora').cast(pl.Utf8).str.contains(':'))
          .then(pl.col('hora').cast(pl.Utf8).str.split(':').list.first().cast(pl.Int32))
          .otherwise(pl.col('hora').cast(pl.Int32, strict=False).fill_null(0))
          .alias('hora_int')
    )

print("Creando dimensiones y hechos para 2022...\n")

print("1. Cargando velocidad_promedio 2022...")
vp_dir = os.path.join(DATA_DIR, "velocidad_promedio")
vp_files = filter_2022(os.listdir(vp_dir))
vp_df = load_dataset_lazy(
    vp_dir, vp_files, EXPECTED_VELOCIDAD_COLS,
    {'velocidad_promedio': 'velocidad'},
    lambda df: df.filter(pl.col('fecha').str.contains('2022'))
)
print(f"   Dataset loaded (lazy)")

print("\n2. Cargando conteo_vehicular 2022...")
cv_dir = os.path.join(DATA_DIR, "conteo_vehicular")
cv_files = filter_2022(os.listdir(cv_dir))
cv_df = load_dataset_lazy(
    cv_dir, cv_files, EXPECTED_CONTEO_COLS,
    {},
    lambda df: df.filter(pl.col('fecha').str.contains('2022'))
)
print(f"   Dataset loaded (lazy)")

print("\n3. Cargando lesionados_en_siniestros...")
sin_dir = os.path.join(DATA_DIR, "lesionados_en_siniestros")
sin_files = [f for f in os.listdir(sin_dir) if f.endswith('.csv')]
sin_df = load_dataset_lazy(
    sin_dir, sin_files, EXPECTED_SINIESTROS_COLS,
    {},
    lambda df: df.pipe(parse_fecha).filter(pl.col('fecha_dt').dt.year() == 2022)
)
print(f"   Dataset loaded (lazy)")

print("\n" + "="*50)
print("STAGE 1: Creando dimensiones (bajo uso de memoria)...")
print("="*50)

print("\n4. Creando dim_fecha...")
fecha_parts = []
if vp_df is not None:
    f = (vp_df.pipe(parse_fecha).pipe(extract_hour)
         .select(['fecha_dt', 'hora_int']).unique()
         .with_columns([
             pl.col('fecha_dt').dt.year().alias('anio'),
             pl.col('fecha_dt').dt.month().alias('mes'),
             pl.col('fecha_dt').dt.day().alias('dia'),
             pl.col('fecha_dt').dt.weekday().map_elements(lambda x: ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'][x-1], return_dtype=pl.Utf8).alias('dia_semana')
         ]))
    fecha_parts.append(f)
if cv_df is not None:
    f = (cv_df.pipe(parse_fecha).pipe(extract_hour)
         .select(['fecha_dt', 'hora_int']).unique()
         .with_columns([
             pl.col('fecha_dt').dt.year().alias('anio'),
             pl.col('fecha_dt').dt.month().alias('mes'),
             pl.col('fecha_dt').dt.day().alias('dia'),
             pl.col('fecha_dt').dt.weekday().map_elements(lambda x: ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'][x-1], return_dtype=pl.Utf8).alias('dia_semana')
         ]))
    fecha_parts.append(f)
if sin_df is not None:
    f = (sin_df.select(['fecha', 'hora']).pipe(parse_fecha).pipe(extract_hour)
         .select(['fecha_dt', 'hora_int']).unique()
         .with_columns([
             pl.col('fecha_dt').dt.year().alias('anio'),
             pl.col('fecha_dt').dt.month().alias('mes'),
             pl.col('fecha_dt').dt.day().alias('dia'),
             pl.col('fecha_dt').dt.weekday().map_elements(lambda x: ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'][x-1], return_dtype=pl.Utf8).alias('dia_semana')
         ]))
    fecha_parts.append(f)

if fecha_parts:
    dim_fecha = (pl.concat(fecha_parts)
                 .unique()
                 .sort(['fecha_dt', 'hora_int'])
                 .with_row_index(name='fecha_key', offset=1)
                 .with_columns(pl.col('fecha_key').cast(pl.Int32))
                 .rename({'fecha_dt': 'fecha', 'hora_int': 'hora'})
                 .select(['fecha_key', 'fecha', 'hora', 'anio', 'mes', 'dia', 'dia_semana']))
    dim_fecha.sink_csv(os.path.join(OUTPUT_DIR, 'dim_fecha.csv'))
    print(f"   dim_fecha.csv exportado")

print("\n5. Creando dim_ubicacion...")
ubicacion_parts = []
if vp_df is not None:
    ub = (vp_df.select(['dsc_avenida', 'latitud', 'longitud']).unique()
          .with_columns([
              pl.col('latitud').cast(pl.Float64),
              pl.col('longitud').cast(pl.Float64),
              pl.lit('avenida').alias('tipo')
          ])
          .rename({'dsc_avenida': 'descripcion'}))
    ubicacion_parts.append(ub)
if cv_df is not None:
    ub = (cv_df.select(['dsc_avenida', 'latitud', 'longitud']).unique()
          .with_columns([
              pl.col('latitud').cast(pl.Float64),
              pl.col('longitud').cast(pl.Float64),
              pl.lit('avenida').alias('tipo')
          ])
          .rename({'dsc_avenida': 'descripcion'}))
    ubicacion_parts.append(ub)
if sin_df is not None:
    sin_unique = sin_df.select(['calle', 'x', 'y']).unique().collect()
    if not sin_unique.is_empty():
        latlon_list = [utm_to_latlon(row['x'], row['y']) for row in sin_unique.iter_rows(named=True)]
        lat_col = [ll[0] for ll in latlon_list]
        lon_col = [ll[1] for ll in latlon_list]
        sin_ub = pl.DataFrame({
            'descripcion': sin_unique['calle'].to_list(),
            'latitud': lat_col,
            'longitud': lon_col,
            'tipo': ['calle_siniestro'] * len(sin_unique)
        })
        ubicacion_parts.append(sin_ub.lazy())

if ubicacion_parts:
    dim_ubicacion = (pl.concat(ubicacion_parts)
                     .unique()
                     .sort('descripcion')
                     .with_row_index(name='ubicacion_id', offset=1)
                     .select(['ubicacion_id', 'descripcion', 'latitud', 'longitud', 'tipo']))
    dim_ubicacion.sink_csv(os.path.join(OUTPUT_DIR, 'dim_ubicacion.csv'))
    print(f"   dim_ubicacion.csv exportado")

print("\n6. Creando dim_detector...")
detector_parts = []
if vp_df is not None:
    det = (vp_df.select(['cod_detector', 'dsc_avenida', 'dsc_int_anterior', 'dsc_int_siguiente', 'latitud', 'longitud'])
           .unique(subset='cod_detector')
           .with_columns([
               pl.col('latitud').cast(pl.Float64),
               pl.col('longitud').cast(pl.Float64),
           ])
           .rename({'dsc_avenida': 'avenida', 'dsc_int_anterior': 'int_anterior', 'dsc_int_siguiente': 'int_siguiente'}))
    detector_parts.append(det)
if cv_df is not None:
    det = (cv_df.select(['cod_detector', 'dsc_avenida', 'dsc_int_anterior', 'dsc_int_siguiente', 'latitud', 'longitud'])
           .unique(subset='cod_detector')
           .with_columns([
               pl.col('latitud').cast(pl.Float64),
               pl.col('longitud').cast(pl.Float64),
           ])
           .rename({'dsc_avenida': 'avenida', 'dsc_int_anterior': 'int_anterior', 'dsc_int_siguiente': 'int_siguiente'}))
    detector_parts.append(det)

if detector_parts:
    dim_detector = (pl.concat(detector_parts)
                    .unique(subset='cod_detector')
                    .sort('cod_detector')
                    .with_row_index(name='detector_id', offset=1)
                    .select(['detector_id', 'cod_detector', 'avenida', 'int_anterior', 'int_siguiente', 'latitud', 'longitud']))
    dim_detector.sink_csv(os.path.join(OUTPUT_DIR, 'dim_detector.csv'))
    print(f"   dim_detector.csv exportado")

del vp_df, cv_df, sin_df
del fecha_parts, ubicacion_parts, detector_parts
del dim_fecha, dim_ubicacion, dim_detector

import gc
gc.collect()

print("\n" + "="*50)
print("STAGE 2: Creando hechos (re-cargando datos reducidos)...")
print("="*50)

print("\n7. Creando hecho_velocidad_2022...")
vp_dir = os.path.join(DATA_DIR, "velocidad_promedio")
vp_files = filter_2022(os.listdir(vp_dir))

vp_dfs = []
for f in vp_files:
    path = os.path.join(vp_dir, f)
    if not os.path.isfile(path) or not is_valid_csv(path):
        continue
    try:
        df = (pl.scan_csv(path, has_header=True, ignore_errors=True, null_values=["SIN DATOS", "N/A", ""])
              .filter(pl.col('fecha').str.contains('2022'))
              .pipe(parse_fecha)
              .pipe(extract_hour)
              .with_columns([
                  pl.col('latitud').cast(pl.Float64),
                  pl.col('longitud').cast(pl.Float64),
              ])
              .select(['fecha_dt', 'hora_int', 'cod_detector', 'id_carril', 'velocidad', 'dsc_avenida', 'latitud', 'longitud'])
              .rename({'fecha_dt': 'fecha', 'hora_int': 'hora', 'dsc_avenida': 'avenida'}))
        vp_dfs.append(df)
    except:
        continue

if vp_dfs:
    fact_vp = pl.concat(vp_dfs)
    fact_vp.sink_csv(os.path.join(OUTPUT_DIR, 'fact_velocidad_2022.csv'))
    print(f"   fact_velocidad_2022.csv exportado ({fact_vp.collect().height:,} registros)")
    del fact_vp
    gc.collect()

print("\n8. Creando hecho_conteo_2022...")
cv_dir = os.path.join(DATA_DIR, "conteo_vehicular")
cv_files = filter_2022(os.listdir(cv_dir))

cv_dfs = []
for f in cv_files:
    path = os.path.join(cv_dir, f)
    if not os.path.isfile(path) or not is_valid_csv(path):
        continue
    try:
        df = (pl.scan_csv(path, has_header=True, ignore_errors=True, null_values=["SIN DATOS", "N/A", ""])
              .filter(pl.col('fecha').str.contains('2022'))
              .pipe(parse_fecha)
              .pipe(extract_hour)
              .with_columns([
                  pl.col('latitud').cast(pl.Float64),
                  pl.col('longitud').cast(pl.Float64),
              ])
              .select(['fecha_dt', 'hora_int', 'cod_detector', 'id_carril', 'volume', 'volumen_hora', 'dsc_avenida', 'latitud', 'longitud'])
              .rename({'fecha_dt': 'fecha', 'hora_int': 'hora', 'dsc_avenida': 'avenida'}))
        cv_dfs.append(df)
    except:
        continue

if cv_dfs:
    fact_cv = pl.concat(cv_dfs)
    fact_cv.sink_csv(os.path.join(OUTPUT_DIR, 'fact_conteo_2022.csv'))
    print(f"   fact_conteo_2022.csv exportado ({fact_cv.collect().height:,} registros)")
    del fact_cv
    gc.collect()

print("\n9. Creando hecho_siniestros_2022...")
sin_dir = os.path.join(DATA_DIR, "lesionados_en_siniestros")
sin_files = [f for f in os.listdir(sin_dir) if f.endswith('.csv') and not f.endswith('.etag')]

def standardize_siniestros(df):
    cols = df.collect_schema().names()
    new_cols = standardize_columns(cols)
    rename_map = {old: new for old, new in zip(cols, new_cols) if old != new}
    return df.rename(rename_map)

sin_dfs = []
for f in sin_files:
    path = os.path.join(sin_dir, f)
    if not os.path.isfile(path) or not is_valid_csv(path):
        continue
    try:
        df = (pl.scan_csv(path, has_header=True, ignore_errors=True, null_values=["SIN DATOS", "N/A", ""])
              .pipe(standardize_siniestros)
              .pipe(parse_fecha)
              .filter(pl.col('fecha_dt').dt.year() == 2022)
              .pipe(extract_hour)
              .select(['fecha_dt', 'hora_int', 'tipo_de_siniestro', 'edad', 'sexo', 'calle', 'x', 'y'])
              .rename({'fecha_dt': 'fecha', 'hora_int': 'hora'})
              .unique()
              .collect())
        if not df.is_empty():
            latlon = [utm_to_latlon(row['x'], row['y']) for row in df.iter_rows(named=True)]
            df = df.with_columns([
                pl.Series([ll[0] for ll in latlon]).alias('latitud'),
                pl.Series([ll[1] for ll in latlon]).alias('longitud'),
            ]).drop('x', 'y')
            sin_dfs.append(df.lazy())
    except Exception as e:
        print(f"    Error: {e}")
        continue

if sin_dfs:
    fact_sin = pl.concat(sin_dfs).unique()
    fact_sin.sink_csv(os.path.join(OUTPUT_DIR, 'fact_siniestros_2022.csv'))
    print(f"   fact_siniestros_2022.csv exportado ({fact_sin.collect().height:,} registros)")
    del fact_sin
    gc.collect()

print(f"\n{'='*50}")
print(f"Archivos exportados a: {OUTPUT_DIR}")
print("="*50)
