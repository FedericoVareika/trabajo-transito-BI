import os
import polars as pl
from sklearn.cluster import KMeans

DATA_DIR = "data/analitica"
OUTPUT_DIR = "data/analitica"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def main():
    in_path = os.path.join(DATA_DIR, "tramos_analitica_2022.csv")
    if not os.path.exists(in_path):
        print(f"Error: No se encontró {in_path}.")
        print("Debes correr primero src/1_analitica_espacial.py para generar los tramos base.")
        return

    tramos = pl.read_csv(in_path)
    
    X = tramos.select(["indice_riesgo", "indice_eficiencia"]).to_numpy()
    
    import numpy as np
    X = np.nan_to_num(X, nan=0.0)
    
    kmeans = KMeans(n_clusters=3, random_state=42, n_init="auto")
    kmeans.fit(X)
    
    centroides = kmeans.cluster_centers_
    scores = centroides[:, 0] - centroides[:, 1]
    
    ordenados = np.argsort(scores)
    
    mapa_nombres = {
        ordenados[0]: "Seguro / Fluido",
        ordenados[1]: "Precaución",
        ordenados[2]: "Punto Crítico"
    }
    mapa_colores = {
        ordenados[0]: "Verde",
        ordenados[1]: "Amarillo",
        ordenados[2]: "Rojo"
    }
    
    etiquetas_raw = kmeans.labels_
    etiquetas_nombres = [mapa_nombres[l] for l in etiquetas_raw]
    etiquetas_colores = [mapa_colores[l] for l in etiquetas_raw]
    
    tramos = tramos.with_columns([
        pl.Series("categoria_peligrosidad", etiquetas_nombres),
        pl.Series("color_sugerido_powerbi", etiquetas_colores)
    ])
    
    out_path = os.path.join(OUTPUT_DIR, "puntos_criticos_2022.csv")
    tramos.write_csv(out_path)

if __name__ == "__main__":
    main()
