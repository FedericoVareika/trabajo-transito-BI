import os
import json
import re
import polars as pl
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pyproj import Transformer
import gc

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'datasets.json')
DATA_DIR = "data"
OUTPUT_DIR = os.path.join(DATA_DIR, "estandarizado")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# UTM Zone 21S to WGS84
utm_transformer = Transformer.from_crs("EPSG:32721", "EPSG:4326", always_xy=True)

def utm_to_latlon(x, y):
    if x is None or y is None:
        return None, None
    try:
        lon, lat = utm_transformer.transform(float(x), float(y))
        return lat, lon
    except:
        return None, None

def standardize_columns(columns):
    return [str(c).replace('\ufeff', '').strip().lower().replace(' ', '_').replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ú','u').replace('ñ','n') for c in columns]

def parse_date_window(date_str):
    if len(date_str) == 7:
        return datetime.strptime(date_str, "%Y-%m")
    elif len(date_str) == 4:
        return datetime.strptime(date_str, "%Y")
    return None

def filename_matches_window(filename, start, end):
    filename_lower = filename.lower()
    
    months_es = {
        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
        'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
        'setiembre': 9, 'septiembre': 9, 'octubre': 10,
        'noviembre': 11, 'diciembre': 12
    }
    
    for month_name, month_num in months_es.items():
        if month_name in filename_lower:
            years = re.findall(r'(\d{4})', filename)
            if years:
                year = int(years[-1])
                file_date = datetime(year, month_num, 1)
                if start <= file_date <= end:
                    return True
            return False
    
    years = re.findall(r'(\d{4})', filename)
    if years:
        year = int(years[-1])
        file_date = datetime(year, 1, 1)
        if start <= file_date <= end:
            return True
    
    return False

def is_valid_csv(path):
    try:
        with open(path, 'rb') as f:
            return f.read(2) != b'PK'
    except:
        return False

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

def main():
    try:
        with open(CONFIG_FILE) as f:
            datasets = json.load(f)
    except Exception as e:
        print(f"Error al leer {CONFIG_FILE}: {e}")
        return

    all_fecha_parts = []
    all_ubicacion_parts = []
    all_detector_parts = []
    dataset_outputs = []
    
    for dataset in datasets:
        title = dataset['title']
        data_dir = os.path.join(DATA_DIR, title)
        
        date_window = dataset.get('date_window', {})
        start_str = date_window.get('start', '1900-01')
        end_str = date_window.get('end', '2100-12')
        
        start_date = parse_date_window(start_str)
        end_date = parse_date_window(end_str)
        if end_date and len(end_str) == 7:
            end_date = end_date + relativedelta(months=1) - relativedelta(days=1)
        
        output_name = f"{title}_{start_str.replace('-', '_')}_{end_str.replace('-', '_')}"
        
        print(f"\n{'='*50}")
        print(f"Procesando: {title}")
        print(f"Date window: {start_str} to {end_str}")
        print(f"{'='*50}")
        
        if not os.path.exists(data_dir):
            print(f"  Directorio no encontrado: {data_dir}")
            continue
        
        all_files = [f for f in os.listdir(data_dir) if f.endswith('.csv') and not f.endswith('.etag')]
        
        matching_files = []
        for f in all_files:
            if filename_matches_window(f, start_date, end_date):
                matching_files.append(f)
        
        if not matching_files:
            print(f"  No hay archivos para procesar en este rango.")
            continue
        
        print(f"  Archivos a procesar: {len(matching_files)}")
        
        dfs = []
        for f in matching_files:
            path = os.path.join(data_dir, f)
            if not is_valid_csv(path):
                continue
            try:
                schema = pl.scan_csv(path, has_header=True, ignore_errors=True, null_values=["SIN DATOS", "N/A", ""]).collect_schema()
                df = pl.scan_csv(path, has_header=True, ignore_errors=True, null_values=["SIN DATOS", "N/A", ""])
                cols = df.collect_schema().names()
                new_cols = standardize_columns(cols)
                rename_map = {old: new for old, new in zip(cols, new_cols) if old != new}
                df = df.rename(rename_map)
                df = df.with_columns(pl.lit(f).alias('_source'))
                dfs.append(df)
            except Exception as e:
                print(f"    Error leyendo {f}: {e}")
                continue
        
        if not dfs:
            print(f"  No se pudieron cargar archivos.")
            continue
        
        combined = pl.concat(dfs)
        
        # Get schema to know dataset type
        schema_cols = combined.collect_schema().names()
        
        # Fecha parts
        try:
            fecha_df = (combined.pipe(parse_fecha).pipe(extract_hour)
                       .select(['fecha_dt', 'hora_int']).unique()
                       .with_columns([
                           pl.col('fecha_dt').dt.year().alias('anio'),
                           pl.col('fecha_dt').dt.month().alias('mes'),
                           pl.col('fecha_dt').dt.day().alias('dia'),
                           pl.col('fecha_dt').dt.weekday().map_elements(
                               lambda x: ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'][x-1], 
                               return_dtype=pl.Utf8
                           ).alias('dia_semana')
                       ]))
            all_fecha_parts.append(fecha_df)
        except:
            pass
        
        # Ubicacion parts
        if 'dsc_avenida' in schema_cols:
            ub = (combined.select(['dsc_avenida', 'latitud', 'longitud']).unique()
                  .with_columns([
                      pl.col('latitud').cast(pl.Float64),
                      pl.col('longitud').cast(pl.Float64),
                      pl.lit('avenida').alias('tipo')
                  ])
                  .rename({'dsc_avenida': 'descripcion'}))
            all_ubicacion_parts.append(ub)
        elif 'calle' in schema_cols:
            cal_unique = combined.select(['calle', 'x', 'y']).unique().collect()
            if not cal_unique.is_empty():
                latlon_list = [utm_to_latlon(row['x'], row['y']) for row in cal_unique.iter_rows(named=True)]
                sin_ub = pl.DataFrame({
                    'descripcion': cal_unique['calle'].to_list(),
                    'latitud': [ll[0] for ll in latlon_list],
                    'longitud': [ll[1] for ll in latlon_list],
                    'tipo': ['calle_siniestro'] * len(cal_unique)
                })
                all_ubicacion_parts.append(sin_ub.lazy())
        
        # Detector parts
        if 'cod_detector' in schema_cols and 'dsc_avenida' in schema_cols:
            det = (combined.select(['cod_detector', 'dsc_avenida', 'dsc_int_anterior', 'dsc_int_siguiente', 'latitud', 'longitud'])
                   .unique(subset='cod_detector')
                   .with_columns([
                       pl.col('latitud').cast(pl.Float64),
                       pl.col('longitud').cast(pl.Float64),
                   ])
                   .rename({'dsc_avenida': 'avenida', 'dsc_int_anterior': 'int_anterior', 'dsc_int_siguiente': 'int_siguiente'}))
            all_detector_parts.append(det)
        
        # Prepare output columns based on dataset type
        output_cols = []
        select_cols = []
        
        # Common date/time columns
        select_cols.extend(['fecha_dt', 'hora_int'])
        
        if 'cod_detector' in schema_cols:
            select_cols.append('cod_detector')
        if 'id_carril' in schema_cols:
            select_cols.append('id_carril')
        if 'velocidad' in schema_cols:
            select_cols.append('velocidad')
        if 'velocidad_promedio' in schema_cols:
            select_cols.append('velocidad_promedio')
        if 'volume' in schema_cols:
            select_cols.append('volume')
        if 'volumen_hora' in schema_cols:
            select_cols.append('volumen_hora')
        if 'dsc_avenida' in schema_cols:
            select_cols.append('dsc_avenida')
        if 'latitud' in schema_cols:
            select_cols.append('latitud')
        if 'longitud' in schema_cols:
            select_cols.append('longitud')
        
        # Siniestros specific
        if 'tipo_de_siniestro' in schema_cols:
            select_cols.append('tipo_de_siniestro')
        if 'edad' in schema_cols:
            select_cols.append('edad')
        if 'sexo' in schema_cols:
            select_cols.append('sexo')
        if 'calle' in schema_cols:
            select_cols.append('calle')
        
        select_cols = [c for c in select_cols if c in schema_cols]
        
        output_df = (combined
                    .pipe(parse_fecha)
                    .pipe(extract_hour)
                    .select(select_cols)
                    .rename({'fecha_dt': 'fecha', 'hora_int': 'hora'}))
        
        # Add lat/long for siniestros
        if 'calle' in schema_cols and 'x' in schema_cols and 'y' in schema_cols:
            out_collected = output_df.unique().collect()
            if not out_collected.is_empty():
                latlon = [utm_to_latlon(row['x'], row['y']) for row in out_collected.iter_rows(named=True)]
                out_collected = out_collected.with_columns([
                    pl.Series([ll[0] for ll in latlon]).alias('latitud'),
                    pl.Series([ll[1] for ll in latlon]).alias('longitud'),
                ]).drop('x', 'y')
                dataset_outputs.append((output_name, out_collected.lazy()))
        else:
            if 'latitud' in schema_cols:
                output_df = output_df.with_columns(pl.col('latitud').cast(pl.Float64))
            if 'longitud' in schema_cols:
                output_df = output_df.with_columns(pl.col('longitud').cast(pl.Float64))
            dataset_outputs.append((output_name, output_df.unique()))
        
        print(f"  Registros unicos: {output_df.unique().collect().height:,}")
        
        del combined, dfs
        gc.collect()

    # Create dimension tables
    print(f"\n{'='*50}")
    print("Creando tablas de dimensiones...")
    print(f"{'='*50}")
    
    if all_fecha_parts:
        dim_fecha = (pl.concat(all_fecha_parts)
                     .unique()
                     .sort(['fecha_dt', 'hora_int'])
                     .with_row_index(name='fecha_key', offset=1)
                     .with_columns(pl.col('fecha_key').cast(pl.Int32))
                     .rename({'fecha_dt': 'fecha', 'hora_int': 'hora'})
                     .select(['fecha_key', 'fecha', 'hora', 'anio', 'mes', 'dia', 'dia_semana']))
        dim_fecha.sink_csv(os.path.join(OUTPUT_DIR, 'dim_fecha.csv'))
        print(f"  dim_fecha.csv: {dim_fecha.collect().height:,} registros")
        del dim_fecha
    
    if all_ubicacion_parts:
        dim_ubicacion = (pl.concat(all_ubicacion_parts)
                         .unique()
                         .sort('descripcion')
                         .with_row_index(name='ubicacion_id', offset=1)
                         .select(['ubicacion_id', 'descripcion', 'latitud', 'longitud', 'tipo']))
        dim_ubicacion.sink_csv(os.path.join(OUTPUT_DIR, 'dim_ubicacion.csv'))
        print(f"  dim_ubicacion.csv: {dim_ubicacion.collect().height:,} registros")
        del dim_ubicacion
    
    if all_detector_parts:
        dim_detector = (pl.concat(all_detector_parts)
                        .unique(subset='cod_detector')
                        .sort('cod_detector')
                        .with_row_index(name='detector_id', offset=1)
                        .select(['detector_id', 'cod_detector', 'avenida', 'int_anterior', 'int_siguiente', 'latitud', 'longitud']))
        dim_detector.sink_csv(os.path.join(OUTPUT_DIR, 'dim_detector.csv'))
        print(f"  dim_detector.csv: {dim_detector.collect().height:,} registros")
        del dim_detector
    
    del all_fecha_parts, all_ubicacion_parts, all_detector_parts
    gc.collect()
    
    # Write dataset outputs
    print(f"\n{'='*50}")
    print("Guardando archivos de datos...")
    print(f"{'='*50}")
    
    for name, df in dataset_outputs:
        output_path = os.path.join(OUTPUT_DIR, f'{name}.csv')
        df.sink_csv(output_path)
        print(f"  {name}.csv: {df.collect().height:,} registros")
    
    print(f"\n{'='*50}")
    print(f"Archivos exportados a: {OUTPUT_DIR}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
