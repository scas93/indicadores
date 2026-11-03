"""Carga la geografía INEGI (api/seed_data/geografia_*.csv) a las plantillas globales.

    python cargar_geografia.py                 # todos los estados que traigan los CSV
    python cargar_geografia.py --estado 11     # solo Guanajuato (las demás filas se ignoran)

Es idempotente y tolerante: una localidad sin municipio/estado se omite y se reporta."""
import argparse
import csv
import sys
from pathlib import Path

from app.db import new_session
from app.services.geografia import cargar_geografia

DATA = Path(__file__).parent / "seed_data"


def leer_csv(nombre: str):
    """Generador: lee el CSV fila por fila, sin cargarlo completo en memoria."""
    p = DATA / nombre
    if not p.exists():
        print(f"AVISO: no existe {p}", file=sys.stderr)
        return
    with p.open(encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--estado", help="clave INEGI de un solo estado (p. ej. 11)")
    a = ap.parse_args(argv)
    with new_session() as db:
        try:
            rep = cargar_geografia(db, leer_csv("geografia_municipio.csv"),
                                   leer_csv("geografia_localidad.csv"), solo_estado=a.estado)
        except ValueError as e:
            print(e, file=sys.stderr)
            return 2
    print(rep.resumen())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
