import os
import requests

def descargar_ckan(dataset_id, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    base_url = f"https://catalogodatos.gub.uy/api/3/action/package_show?id={dataset_id}"
    print(f"Consultando: {dataset_id}")
    try:
        response = requests.get(base_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        recursos = data['result']['resources']
        for r in recursos:
            url = r['url']
            nombre = r['name'].lower().replace(' ', '_').replace('/', '_')
            if not nombre.endswith('.csv'):
                nombre += '.csv' # Forzamos la extension para simplificar
            
            ruta_archivo = os.path.join(out_dir, nombre)
            if os.path.exists(ruta_archivo):
                print(f"  El archivo {nombre} ya existe. Omitiendo descarga.")
                continue
                
            print(f"  Descargando {nombre}...")
            r_file = requests.get(url, stream=True)
            with open(ruta_archivo, 'wb') as f:
                for chunk in r_file.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"  Descargado: {ruta_archivo}")
    except Exception as e:
        print(f"Error descargando {dataset_id}: {e}")

if __name__ == "__main__":
    print("Descargando Multas Históricas...")
    descargar_ckan("multas-de-transito", "data/multas_de_transito")
    
    print("\nDescargando Vías de Montevideo (Diccionario de calles)...")
    descargar_ckan("vias-de-montevideo-con-cabezales-de-numeracion-significado-tipo-y-titulo", "data/listado_calles")
