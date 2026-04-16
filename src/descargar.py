import os
import json
import requests
import re
from tqdm import tqdm

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

def main():
    try:
        with open(CONFIG_FILE) as f:
            datasets = json.load(f)
    except Exception as e:
        print(f"Error al leer {CONFIG_FILE}: {e}")
        return
    
    interrupted = False
    
    for dataset in datasets:
        title = dataset['title']
        dataset_id = dataset['dataset_id']
        download_dir = os.path.join("data", title)
        os.makedirs(download_dir, exist_ok=True)
        
        print(f"\n{'='*50}")
        print(f"Dataset: {title}")
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

        print(f"Se encontraron {len(recursos)} recursos en la metadata.\n")

        recursos_info = []
        for r in recursos:
            ext = get_extension(r)
            nombre_archivo = sanitize_filename(r['name'], ext)
            ruta_archivo = os.path.join(download_dir, nombre_archivo)
            recursos_info.append((nombre_archivo, ruta_archivo, r['url']))

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
