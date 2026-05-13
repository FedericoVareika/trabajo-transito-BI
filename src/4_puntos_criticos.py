import os
import polars as pl
from sklearn.cluster import KMeans

DATA_DIR = "data/analitica"
OUTPUT_DIR = "data/analitica"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def main():
    print("Iniciando Identificación Automática de Puntos Críticos (Clustering)...")
    
    in_path = os.path.join(DATA_DIR, "tramos_analitica_2022.csv")
    if not os.path.exists(in_path):
        print(f"Error: No se encontró {in_path}.")
        print("Debes correr primero src/1_analitica_espacial.py para generar los tramos base.")
        return

    tramos = pl.read_csv(in_path)
    
    # Extraemos las variables numéricas que nos interesan para el clustering
    # Usaremos el Índice de Riesgo (qué tantos choques hay por volumen) 
    # y el Índice de Eficiencia (qué tan bien fluye el tránsito).
    print("\n1. Preparando datos para Machine Learning...")
    X = tramos.select(["indice_riesgo", "indice_eficiencia"]).to_numpy()
    
    # Manejar nulos por si acaso
    import numpy as np
    X = np.nan_to_num(X, nan=0.0)
    
    # 2. Aplicar K-Means
    print("2. Entrenando modelo K-Means con 3 clusters (Alto, Medio, Bajo riesgo)...")
    kmeans = KMeans(n_clusters=3, random_state=42, n_init="auto")
    kmeans.fit(X)
    
    # 3. Clasificar los resultados
    # K-Means devuelve etiquetas (0, 1, 2) pero no sabemos cuál es el "peor".
    # Vamos a analizar los centroides para ordenarlos.
    # El cluster con mayor Riesgo promedio y menor Eficiencia promedio será el Peor.
    
    centroides = kmeans.cluster_centers_
    # Creamos un "score de peligrosidad" para ordenar los clusters
    # score = Riesgo - Eficiencia (Queremos alto riesgo y baja eficiencia)
    scores = centroides[:, 0] - centroides[:, 1]
    
    # Ordenamos de menor a mayor peligrosidad
    ordenados = np.argsort(scores)
    # ordenados[0] = Indice del cluster menos peligroso (Bajo)
    # ordenados[1] = Indice del cluster intermedio (Medio)
    # ordenados[2] = Indice del cluster más peligroso (Crítico)
    
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
    
    # Aplicar nombres al dataset
    etiquetas_raw = kmeans.labels_
    etiquetas_nombres = [mapa_nombres[l] for l in etiquetas_raw]
    etiquetas_colores = [mapa_colores[l] for l in etiquetas_raw]
    
    tramos = tramos.with_columns([
        pl.Series("categoria_peligrosidad", etiquetas_nombres),
        pl.Series("color_sugerido_powerbi", etiquetas_colores)
    ])
    
    # 4. Exportar
    out_path = os.path.join(OUTPUT_DIR, "puntos_criticos_2022.csv")
    tramos.write_csv(out_path)
    
    print(f"\n¡Clasificación exitosa! Archivo guardado en {out_path}")
    print("\nResumen de Puntos Críticos encontrados:")
    print(tramos.group_by("categoria_peligrosidad").agg(pl.count().alias("cantidad_detectores")))

if __name__ == "__main__":
    main()

"""
=============================================================================
SALIDA PARA POWER BI (puntos_criticos_2022.csv)
=============================================================================
Este script enriquece la base geográfica con etiquetas de Machine Learning.
TODAS LAS COLUMNAS GENERADAS:
- detector_id: ID interno del sensor.
- cod_detector: Código del radar/sensor.
- avenida: Nombre exacto de la calle/avenida.
- latitud: Coordenada Y para el Mapa.
- longitud: Coordenada X para el Mapa.
- velocidad_media: Promedio anual de velocidad.
- volumen_total: Suma de autos anual.
- cantidad_siniestros: Total de accidentes geográficamente cercanos.
- indice_eficiencia (0-100): Indicador base de fluidez.
- indice_riesgo (0-100): Indicador base de peligrosidad.
- categoria_peligrosidad: Etiqueta de la IA ("Punto Crítico", "Precaución", "Seguro / Fluido").
- color_sugerido_powerbi: Color hexadecimal o palabra (Rojo, Amarillo, Verde) para el mapa.

VISUALIZACIONES RECOMENDADAS:
1. Mapa:
   - Ubicación: latitud y longitud. Leyenda: categoria_peligrosidad. (Pinta todo Montevideo según la clasificación automática de la IA).
2. Gráfico de Anillo (Donut Chart):
   - Leyenda: categoria_peligrosidad. Valores: Recuento de latitud. (Para ver el porcentaje de sensores que cayeron en estado Crítico).
3. Segmentador de Datos (Slicer):
   - Campo: categoria_peligrosidad. (Filtro maestro para que al hacer clic en "Punto Crítico", el resto del Dashboard muestre solo esos datos).
=============================================================================
"""
