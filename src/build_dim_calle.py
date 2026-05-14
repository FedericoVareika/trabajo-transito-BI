import os
import polars as pl
from pipeline_utils import OUTPUT_DIR


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    ub_path = os.path.join(OUTPUT_DIR, 'dim_ubicacion.csv')
    if not os.path.exists(ub_path):
        print("dim_ubicacion.csv no encontrado. Ejecuta build_dim_ubicacion.py primero.")
        return

    ub = pl.read_csv(ub_path)

    streets = (ub.select(['id', 'descripcion'])
               .with_columns(pl.col('descripcion').str.split(' / ').alias('parts'))
               .explode('parts')
               .with_columns(
                   pl.when(pl.col('parts').str.to_lowercase().str.contains(' esq. '))
                   .then(pl.col('parts').str.to_lowercase().str.replace(' esq. ', '|'))
                   .otherwise(pl.col('parts').str.to_lowercase()).alias('m'))
               .with_columns(pl.col('m').str.split('|').alias('sub'))
               .explode('sub')
               .with_columns(
                   pl.col('sub').str.strip_chars().str.to_uppercase().alias('nombre'))
               .filter(pl.col('nombre') != '')
               .filter(~pl.col('nombre').str.contains(r'^-?\d+\.?\d*$'))
               .unique(['id', 'nombre'])
               .sort(['id', 'nombre']))

    dim = (streets
           .with_row_index(name='calle_id', offset=1)
           .select(['calle_id', 'id', 'nombre'])
           .rename({'calle_id': 'id', 'id': 'ubicacion'}))

    out_path = os.path.join(OUTPUT_DIR, 'dim_calle.csv')
    dim.write_csv(out_path)
    print(f"dim_calle.csv: {dim.height:,} filas")


if __name__ == "__main__":
    main()
