import os
import json
import pandas as pd

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'datasets.json')

def main():
    with open(CONFIG_FILE) as f:
        datasets = json.load(f)
    
    for dataset in datasets:
        title = dataset['title']
        download_dir = os.path.join("data", title)
        
        print(f"\n{'='*50}")
        print(f"Dataset: {title}")
        print(f"{'='*50}")
        
        if not os.path.exists(download_dir):
            print(f"Directorio no encontrado: {download_dir}\n")
            continue
        
        archivos = [os.path.join(download_dir, f) for f in os.listdir(download_dir) if f.endswith('.csv')]
        
        if not archivos:
            print(f"No se encontraron archivos CSV en {download_dir}\n")
            continue
        
        print(f"Analizando {len(archivos)} archivos CSV...\n")
        
        esquemas = {}
        
        for archivo in archivos:
            try:
                df = pd.read_csv(archivo, nrows=0, sep=None, engine='python', encoding='utf-8') 
                columnas = tuple(df.columns.str.strip().str.lower().tolist())
                
                if columnas not in esquemas:
                    esquemas[columnas] = []
                esquemas[columnas].append(archivo)
                
            except UnicodeDecodeError:
                try:
                    df = pd.read_csv(archivo, nrows=0, sep=None, engine='python', encoding='latin1')
                    columnas = tuple(df.columns.str.strip().str.lower().tolist())
                    if columnas not in esquemas:
                        esquemas[columnas] = []
                    esquemas[columnas].append(archivo)
                except Exception as e2:
                    print(f"  [ERROR] de lectura en {archivo}: {e2}")
            except Exception as e:
                print(f"  [ERROR] general leyendo {archivo}: {e}")
        
        print("--- REPORTE DE COMPATIBILIDAD ---")
        if len(esquemas) == 1:
            print("Todos los archivos tienen exactamente las mismas columnas.")
            print("Son 100% compatibles para hacer un merge directo usando pd.concat().")
            print(f"Columnas detectadas: {list(esquemas.keys())[0]}")
        elif len(esquemas) > 1:
            print(f"Se encontraron {len(esquemas)} estructuras de columnas diferentes.")
            for i, (columnas, archivos) in enumerate(esquemas.items(), 1):
                print(f"\nESTRUCTURA {i} ({len(archivos)} archivos):")
                print(f"   Columnas: {columnas}")
                print(f"   Ejemplos:")
                for ej in archivos[:3]: 
                    print(f"     - {os.path.basename(ej)}")

if __name__ == "__main__":
    main()
