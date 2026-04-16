import requests
import json
import pandas as pd

def obtener_datos_ckan(url_dataset):
    """
    Extrae metadatos y enlaces de descarga de un dataset del portal gub.uy
    usando la API de CKAN.
    """
    # 1. Extraer el 'slug' (nombre único) del dataset desde la URL
    # Ejemplo: 'velocidad-promedio-vehicular-en-las-principales-avenidas-de-montevideo'
    dataset_slug = url_dataset.strip("/").split("/")[-1]
    
    # 2. Construir la URL de la API de CKAN
    base_url = "https://catalogodatos.gub.uy/api/3/action/package_show"
    params = {'id': dataset_slug}
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()  # Verifica si hay errores en la petición
        data = response.json()
        
        if data['success']:
            result = data['result']
            
            # --- METADATOS GENERALES ---
            info_general = {
                "Título": result.get("title"),
                "Autor": result.get("author"),
                "Mantenedor": result.get("maintainer"),
                "Última actualización": result.get("metadata_modified"),
                "Descripción": result.get("notes")
            }
            
            print(f"--- ANALIZANDO: {info_general['Título']} ---\n")
            print(f"Descripción: {info_general['Descripción'][:200]}...\n")
            
            # --- RECURSOS (LOS DATASETS REALES) ---
            recursos = result.get("resources", [])
            lista_recursos = []
            
            for res in recursos:
                lista_recursos.append({
                    "Nombre": res.get("name"),
                    "Formato": res.get("format"),
                    "URL_Descarga": res.get("url"),
                    "Fecha_Creacion": res.get("created"),
                    "ID_Recurso": res.get("id")
                })
            
            # Convertimos a DataFrame para visualizar mejor
            df_recursos = pd.DataFrame(lista_recursos)
            return info_general, df_recursos
            
        else:
            print("No se pudo obtener información del dataset.")
            return None, None
            
    except Exception as e:
        print(f"Ocurrió un error: {e}")
        return None, None

# --- EJECUCIÓN ---
# url = "https://catalogodatos.gub.uy/dataset/velocidad-promedio-vehicular-en-las-principales-avenidas-de-montevideo"
url = "https://catalogodatos.gub.uy/dataset/multas-de-transito"
metadatos, datasets = obtener_datos_ckan(url)

if datasets is not None:
    print("Datasets encontrados:")
    print(datasets)
    print("Metadatos:")
    print(metadatos)
    
    # Opcional: Guardar a CSV la lista de enlaces para tu proceso de BI
    # datasets.to_csv("lista_descargas.csv", index=False)
