import subprocess
import sys
import os

SCRIPTS = [
    "build_dim_fecha.py",
    "build_dim_ubicacion.py",
    "build_dim_calle.py",
    "build_dim_detector.py",
    "build_fact_medicion.py",
    "build_fact_siniestros.py",
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    for script in SCRIPTS:
        path = os.path.join(BASE_DIR, script)
        print(f"\n{'=' * 60}")
        print(f"Ejecutando: {script}")
        print(f"{'=' * 60}")
        result = subprocess.run([sys.executable, path], capture_output=False)
        if result.returncode != 0:
            print(f"ERROR: {script} falló (código {result.returncode})")
            sys.exit(result.returncode)

    print(f"\n{'=' * 60}")
    print("Pipeline completo.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
