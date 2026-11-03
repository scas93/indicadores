"""Copia la geografía de las plantillas a municipios ya existentes (los nuevos la reciben al
crearse). Solo agrega lo que falta del estado del municipio; no duplica ni pisa lo editado.

    python copiar_geografia.py --subdominio demo
    python copiar_geografia.py --todos
    python copiar_geografia.py --subdominio demo --dry-run   # cuenta sin escribir"""
import argparse
import sys

from sqlalchemy import select

from app.db import new_session
from app.models import Municipio
from app.services.geografia import copiar_geografia_a_municipio


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--subdominio", help="subdominio del municipio (p. ej. demo)")
    g.add_argument("--todos", action="store_true", help="todos los municipios")
    ap.add_argument("--dry-run", action="store_true", help="no escribe: revierte al final")
    a = ap.parse_args(argv)
    with new_session() as db:
        q = select(Municipio).order_by(Municipio.subdominio)
        if a.subdominio:
            q = q.where(Municipio.subdominio == a.subdominio)
        municipios = db.scalars(q).all()
        if not municipios:
            print("No se encontró ningún municipio", file=sys.stderr)
            return 2
        for m in municipios:
            rep = copiar_geografia_a_municipio(db, m)
            if a.dry_run:
                db.rollback()
            else:
                db.commit()
            print(("[dry-run] " if a.dry_run else "") + rep.resumen())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
