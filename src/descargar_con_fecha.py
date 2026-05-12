import os
import json
import requests
import re
from datetime import datetime
from tqdm import tqdm
from dateutil.relativedelta import relativedelta

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'datasets.json')
BASE_API_URL = "https://catalogodatos.gub.uy/api/3/action/package_show?id={}"

def sanitize_filename(name, ext):
    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', name.lower())
    return safe_name + ext

def get_extension(recurso):
    if recurso.get('format'):
        fmt = recurso['format'].lower().strip('.').split()[-1]
        return '.' + fmt if fmt else ''
    if recurso.get('url'):
        from urllib.parse import urlparse
        parsed = urlparse(recurso['url'])
        path = parsed.path
        if '.' in path:
            ext = path.rsplit('.', 1)[-1].lower()
            return '.' + ext
    return ''

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

def main():
    try:
        with open(CONFIG_FILE) as f:
            datasets = json.load(f)
    except Exception as e:
        print(f"Error al leer {CONFIG_FILE}: {e}")
        return

    for dataset in datasets:
        title = dataset['title']
        dataset_id = dataset['dataset_id']
        download_dir = os.path.join("data", title)
        os.makedirs(download_dir, exist_ok=True)
        
        date_window = dataset.get('date_window', {})
        start_str = date_window.get('start', '1900-01')
        end_str = date_window.get('end', '2100-12')
        
        start_date = parse_date_window(start_str)
        end_date = parse_date_window(end_str)
        if end_date and len(end_str) == 7:
            end_date = end_date + relativedelta(months=1) - relativedelta(days=1)
        
        print(f"\n{'='*50}")
        print(f"Dataset: {title}")
        print(f"Date window: {start_str} to {end_str}")
        print(f"{'='*50}")
        
        print(f"Consultando la API de CKAN: {dataset_id}...")
        try:
            response = requests.get(BASE_API_URL.format(dataset_id), timeout=10)
            response.raise_for_status()
            dataset_info = response.json()
        except KeyboardInterrupt:
            print("\n\nDescarga interrumpida por el usuario.")
            return
        except requests.exceptions.ConnectionError:
            print("Error de conexion. Verifica tu conexion a internet.")
            continue
        except requests.exceptions.Timeout:
            print("Tiempo de espera agotado al consultar la API.")
            continue
        except Exception as e:
            print(f"Error al consultar la API: {e}")
            continue

        recursos = dataset_info['result']['resources']

        recursos_info = []
        skipped_outside_window = 0
        for r in recursos:
            ext = get_extension(r)
            nombre_archivo = sanitize_filename(r['name'], ext)
            
            if not filename_matches_window(nombre_archivo, start_date, end_date):
                skipped_outside_window += 1
                continue
            
            ruta_archivo = os.path.join(download_dir, nombre_archivo)
            recursos_info.append((nombre_archivo, ruta_archivo, r['url']))

        print(f"Se encontraron {len(recursos_info)} recursos dentro del rango ({skipped_outside_window} fuera del rango).\n")

        if not recursos_info:
            print("No hay archivos para descargar en este rango de fechas.")
            continue

        print(f"Descargando {len(recursos_info)} archivos...")
        pbar = tqdm(recursos_info, desc="Archivos", unit="archivo")
        for nombre_archivo, ruta_archivo, url_descarga in pbar:
            print(f"\nDescargando: {nombre_archivo}", flush=True)
            if os.path.exists(ruta_archivo):
                try:
                    headers_check = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    }
                    r_head = requests.head(url_descarga, headers=headers_check, timeout=15)
                    remote_size = r_head.headers.get('content-length')
                    remote_etag = r_head.headers.get('etag')
                    local_size = os.path.getsize(ruta_archivo)
                    local_etag = None
                    etag_file = ruta_archivo + '.etag'
                    if os.path.exists(etag_file):
                        local_etag = open(etag_file).read().strip()
                    if remote_size and int(remote_size) not in (0, local_size):
                        print(f"  Tamaño diferente (local: {local_size} bytes, remoto: {remote_size}), re-descargando.")
                    elif remote_etag and local_etag and remote_etag != local_etag:
                        print(f"  ETag diferente, re-descargando.")
                    else:
                        print(f"  Ya existe y parece intacto, omitiendo.")
                        continue
                except KeyboardInterrupt:
                    pbar.close()
                    print("\n\nDescarga interrumpida por el usuario.")
                    return
                except requests.exceptions.ConnectionError:
                    print(f"  Error de conexion al verificar {nombre_archivo}, omitiendo.")
                    continue
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                }
                
                r = requests.get(url_descarga, headers=headers, stream=True, timeout=15)
                r.raise_for_status()
                
                total_size_str = r.headers.get('content-length')
                total_size = int(total_size_str) if total_size_str else None
                
                file_pbar = tqdm(
                    desc=nombre_archivo,
                    total=total_size,
                    unit='B', 
                    unit_scale=True,
                    unit_divisor=1024,
                    leave=False,
                )
                with open(ruta_archivo, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192): 
                        if chunk:
                            f.write(chunk)
                            file_pbar.update(len(chunk))
                file_pbar.close()
                            
                etag = r.headers.get('etag')
                if etag:
                    with open(ruta_archivo + '.etag', 'w') as ef:
                        ef.write(etag)
                
            except KeyboardInterrupt:
                pbar.close()
                print("\n\nDescarga interrumpida por el usuario.")
                return
            except requests.exceptions.ConnectionError:
                print(f"  Error de conexion descargando {nombre_archivo}, omitiendo.")
            except requests.exceptions.Timeout:
                print(f"  Tiempo de espera agotado para {nombre_archivo}.")
            except Exception as e:
                print(f"  Error descargando {nombre_archivo}: {e}")
        pbar.close()

if __name__ == "__main__":
    main()
