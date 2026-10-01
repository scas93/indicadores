"""Seed inicial, fuera de la interfaz. Corre una vez por ambiente (es idempotente).

    SEED_SUPER_ADMIN_USUARIO=... SEED_SUPER_ADMIN_PASSWORD=... python seed.py
    python seed.py --usuario root --password '...' [--nombre 'Nombre']

1. super_admin (usuario/contraseña por env o parámetros; nunca en el repo; contraseña con argon2).
2. Plantillas globales.
3. Subdominios reservados.
"""
import argparse
import csv
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import new_session
from app.models import (GeografiaEstado, GeografiaLocalidad, GeografiaMunicipio, PlantillaAlgoritmo,
                        PlantillaClasificacionProgramatica, PlantillaConac, PlantillaDimension,
                        PlantillaFrecuencia, PlantillaGrupoEdad, PlantillaNivelSocioeconomico,
                        SubdominioReservado, SuperAdmin)
from app.security import hash_admin_password

DATA = Path(__file__).parent / "seed_data"

RESERVADOS = ["admin", "www", "api", "app", "mail", "smtp", "ftp", "staging", "static", "assets",
              "media", "cdn", "status", "soporte", "ayuda", "docs"]

ESTADOS = [
    ("01", "Aguascalientes"), ("02", "Baja California"), ("03", "Baja California Sur"),
    ("04", "Campeche"), ("05", "Coahuila de Zaragoza"), ("06", "Colima"), ("07", "Chiapas"),
    ("08", "Chihuahua"), ("09", "Ciudad de México"), ("10", "Durango"), ("11", "Guanajuato"),
    ("12", "Guerrero"), ("13", "Hidalgo"), ("14", "Jalisco"), ("15", "México"),
    ("16", "Michoacán de Ocampo"), ("17", "Morelos"), ("18", "Nayarit"), ("19", "Nuevo León"),
    ("20", "Oaxaca"), ("21", "Puebla"), ("22", "Querétaro"), ("23", "Quintana Roo"),
    ("24", "San Luis Potosí"), ("25", "Sinaloa"), ("26", "Sonora"), ("27", "Tabasco"),
    ("28", "Tamaulipas"), ("29", "Tlaxcala"), ("30", "Veracruz de Ignacio de la Llave"),
    ("31", "Yucatán"), ("32", "Zacatecas"),
]
FRECUENCIAS = [("mensual", "Mensual"), ("bimestral", "Bimestral"), ("trimestral", "Trimestral"),
               ("cuatrimestral", "Cuatrimestral"), ("semestral", "Semestral"), ("anual", "Anual")]
DIMENSIONES = [("eficacia", "Eficacia"), ("eficiencia", "Eficiencia"), ("calidad", "Calidad"),
               ("economia", "Economía")]
ALGORITMOS = [("a_sobre_b_pct", "(A / B) * 100"), ("a_sobre_b_menos1_pct", "((A / B) - 1) * 100"),
              ("a_sobre_b", "A / B"), ("a", "A")]
CLASIFICACION = [("especificos", "Específicos"), ("proyectos_inversion", "Proyectos de Inversión"),
                 ("servicios_publicos", "Prestación de Servicios Públicos")]
# Ejemplos: reemplazar con los valores reales (CSV) cuando se definan para el padrón.
GRUPOS_EDAD = [("0-11", "Niñez", 0, 11), ("12-17", "Adolescencia", 12, 17),
               ("18-29", "Juventud", 18, 29), ("30-59", "Adultez", 30, 59),
               ("60+", "Adultos mayores", 60, None)]
NIVELES = [("muy_bajo", "Muy bajo"), ("bajo", "Bajo"), ("medio", "Medio"), ("alto", "Alto")]
CONAC_MUESTRA = [
    ("capitulo", "1000", "Servicios personales", None), ("capitulo", "2000", "Materiales y suministros", None),
    ("capitulo", "3000", "Servicios generales", None),
    ("capitulo", "4000", "Transferencias, asignaciones, subsidios y otras ayudas", None),
    ("capitulo", "5000", "Bienes muebles, inmuebles e intangibles", None),
    ("capitulo", "6000", "Inversión pública", None), ("capitulo", "7000", "Inversiones financieras y otras provisiones", None),
    ("capitulo", "8000", "Participaciones y aportaciones", None), ("capitulo", "9000", "Deuda pública", None),
    ("partida", "221", "Productos alimenticios y bebidas para personas", "2000"),
    ("partida", "223", "Utensilios para el servicio de alimentación", "2000"),
    ("partida_especifica", "2213", "Productos alimenticios para personas derivado de actividades extraordinarias", "221"),
    ("partida_especifica", "2231", "Utensilios para el servicio de alimentación", "223"),
]


def _csv(nombre: str):
    p = DATA / nombre
    if not p.exists():
        return []
    with p.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _plano(db: Session, modelo, filas, extras=()):
    existentes = {c for c in db.scalars(select(modelo.clave))}
    for fila in filas:
        if fila[0] in existentes:
            continue
        kw = dict(clave=fila[0], nombre=fila[1])
        for i, e in enumerate(extras):
            kw[e] = fila[2 + i]
        db.add(modelo(**kw))


def seed_super_admin(db: Session, usuario: str, password: str, nombre: str) -> str:
    a = db.scalar(select(SuperAdmin).where(SuperAdmin.usuario == usuario))
    if a:
        return "ya existía"
    db.add(SuperAdmin(usuario=usuario, password_hash=hash_admin_password(password), nombre=nombre))
    return "creado"


def seed_plantillas(db: Session) -> None:
    for clave, nombre in ESTADOS:
        if not db.scalar(select(GeografiaEstado).where(GeografiaEstado.clave == clave)):
            db.add(GeografiaEstado(clave=clave, nombre=nombre))
    db.flush()
    _plano(db, PlantillaFrecuencia, FRECUENCIAS)
    _plano(db, PlantillaDimension, DIMENSIONES)
    _plano(db, PlantillaAlgoritmo, ALGORITMOS)
    _plano(db, PlantillaClasificacionProgramatica, CLASIFICACION)
    _plano(db, PlantillaGrupoEdad, [(r["clave"], r["nombre"], int(r["edad_min"]) if r["edad_min"] else None,
                                     int(r["edad_max"]) if r["edad_max"] else None)
                                    for r in _csv("grupo_edad.csv")] or GRUPOS_EDAD,
           ("edad_min", "edad_max"))
    _plano(db, PlantillaNivelSocioeconomico,
           [(r["clave"], r["nombre"]) for r in _csv("nivel_socioeconomico.csv")] or NIVELES)
    db.flush()

    # CONAC (CSV completo si existe; si no, muestra)
    filas = [(r["nivel"], r["clave"], r["nombre"], r["padre_clave"] or None)
             for r in _csv("conac.csv")] or CONAC_MUESTRA
    por_clave = {(c.nivel, c.clave): c for c in db.scalars(select(PlantillaConac))}
    padres = {"partida": "capitulo", "partida_especifica": "partida", "articulo": "partida_especifica"}
    for nivel, clave, nombre, padre in filas:
        if (nivel, clave) in por_clave:
            continue
        p = por_clave.get((padres.get(nivel), padre)) if padre else None
        c = PlantillaConac(nivel=nivel, clave=clave, nombre=nombre, padre_id=p.id if p else None)
        db.add(c)
        db.flush()
        por_clave[(nivel, clave)] = c

    # Geografía INEGI desde CSV (no se embebe: ~300 mil localidades)
    estados = {e.clave: e for e in db.scalars(select(GeografiaEstado))}
    munis = {(m.estado_id, m.clave): m for m in db.scalars(select(GeografiaMunicipio))}
    for r in _csv("geografia_municipio.csv"):
        e = estados[r["estado_clave"]]
        if (e.id, r["clave"]) not in munis:
            m = GeografiaMunicipio(estado_id=e.id, clave=r["clave"], nombre=r["nombre"])
            db.add(m)
            db.flush()
            munis[(e.id, r["clave"])] = m
    locs = {(l.municipio_geo_id, l.clave) for l in db.scalars(select(GeografiaLocalidad))}
    for r in _csv("geografia_localidad.csv"):
        m = munis[(estados[r["estado_clave"]].id, r["municipio_clave"])]
        if (m.id, r["clave"]) not in locs:
            db.add(GeografiaLocalidad(municipio_geo_id=m.id, clave=r["clave"], nombre=r["nombre"]))


def seed_reservados(db: Session) -> None:
    ya = set(db.scalars(select(SubdominioReservado.subdominio)))
    for s in RESERVADOS:
        if s not in ya:
            db.add(SubdominioReservado(subdominio=s))


def main(argv=None) -> int:
    s = get_settings()
    ap = argparse.ArgumentParser()
    ap.add_argument("--usuario", default=s.seed_super_admin_usuario)
    ap.add_argument("--password", default=s.seed_super_admin_password)
    ap.add_argument("--nombre", default=s.seed_super_admin_nombre)
    a = ap.parse_args(argv)
    if not a.usuario or not a.password:
        print("Falta usuario/contraseña del super admin (SEED_SUPER_ADMIN_* o --usuario/--password)",
              file=sys.stderr)
        return 2
    with new_session() as db:
        r = seed_super_admin(db, a.usuario, a.password, a.nombre)
        seed_plantillas(db)
        seed_reservados(db)
        db.commit()
    print(f"super admin {r}; plantillas y subdominios reservados cargados")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
