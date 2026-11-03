"""Datos de EJEMPLO del Padrón para un municipio (demo): 12 beneficiarios ficticios y algunas capturas.

    python seed_padron_ejemplo.py --subdominio demo --usuario padron2

Todo es inventado y está marcado: la CURP empieza con EJEMPLO, el nombre termina en "(EJEMPLO)" y las filas llevan
`es_ejemplo`. Es idempotente (no repite beneficiarios ni capturas). Requiere la geografía copiada al municipio
(copiar_geografia.py) y al menos un programa activo; si el programa no tiene apoyos, crea dos de ejemplo."""
import argparse
import sys
from datetime import timedelta

from sqlalchemy import select

from app import validators_padron as vpd
from app.db import new_session
from app.models import (Apoyo, Beneficiario, CapturaApoyo, CatalogoMunicipio, DescripcionApoyo, Municipio, Programa,
                        Usuario, UsuarioPrograma)
from app.services.padron_beneficiarios import hoy

# (nombre, género, edad en años, apoyo # (0|1), días atrás de la captura, nivel #)
PERSONAS = [
    ("Ramírez Torres Lucía", "F", 4, 0, 0, 0), ("Hernández Gómez Mateo", "M", 8, 1, 0, 1),
    ("García Luna Valentina", "F", 13, 0, 0, 2), ("Martínez Ruiz Diego", "M", 16, 1, 1, 0),
    ("López Vega Sofía", "F", 22, 0, 1, 1), ("Sánchez Mora Carlos", "M", 35, 1, 2, 2),
    ("Flores Díaz Fernanda", "F", 41, 0, 2, 0), ("Torres Ortiz Jorge", "M", 58, 1, 3, 1),
    ("Cruz Reyes Marta", "F", 63, 0, 3, 2), ("Morales Silva Ernesto", "M", 71, 1, 4, 0),
    ("Jiménez Castro Rosa", "F", 79, 0, 5, 1), ("Vargas Núñez Pedro", "M", 27, 1, 6, 2),
]
APOYOS = [("EJ-APO1", "Despensa (EJEMPLO)", [("EJ-D1", "Despensa básica (EJEMPLO)"), ("EJ-D2", "Despensa ampliada (EJEMPLO)")]),
          ("EJ-APO2", "Apoyo escolar (EJEMPLO)", [("EJ-D3", "Paquete de útiles (EJEMPLO)")])]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--subdominio", required=True)
    ap.add_argument("--usuario", help="usuario cuyo programa asignado se usa (p. ej. padron2)")
    a = ap.parse_args(argv)
    with new_session() as db:
        mun = db.scalar(select(Municipio).where(Municipio.subdominio == a.subdominio))
        if mun is None:
            print("No existe el municipio", file=sys.stderr)
            return 2
        mid, dia = mun.id, hoy()
        q = select(Programa).where(Programa.municipio_id == mid, Programa.activo.is_(True))
        if a.usuario:
            u = db.scalar(select(Usuario).where(Usuario.municipio_id == mid, Usuario.usuario == a.usuario))
            if u is None:
                print("No existe el usuario", file=sys.stderr)
                return 2
            q = q.where(Programa.id.in_(select(UsuarioPrograma.programa_id).where(UsuarioPrograma.usuario_id == u.id)))
        programa = db.scalars(q.order_by(Programa.ejercicio_fiscal.desc(), Programa.clave)).first()
        if programa is None:
            print("No hay un programa activo (asignado al usuario, si se pidió)", file=sys.stderr)
            return 2

        apoyos = list(db.scalars(select(Apoyo).where(Apoyo.programa_id == programa.id).order_by(Apoyo.clave)))
        if not apoyos:
            for clave, nombre, descs in APOYOS:
                x = Apoyo(municipio_id=mid, clave=clave, nombre=nombre, programa_id=programa.id)
                db.add(x)
                db.flush()
                apoyos.append(x)
                for dc, dn in descs:
                    db.add(DescripcionApoyo(municipio_id=mid, clave=dc, nombre=dn, apoyo_id=x.id))
            db.flush()
        cat = lambda tipo: list(db.scalars(select(CatalogoMunicipio).where(
            CatalogoMunicipio.municipio_id == mid, CatalogoMunicipio.tipo == tipo).order_by(CatalogoMunicipio.clave)))
        niveles, grupos = cat("nivel_socioeconomico"), cat("grupo_edad")
        rangos = [(g.id, g.datos["edad_min"], g.datos.get("edad_max")) for g in grupos if (g.datos or {}).get("edad_min") is not None]
        munis = cat("geo_municipio")
        locs = [(m, l) for m in munis for l in db.scalars(select(CatalogoMunicipio).where(
            CatalogoMunicipio.padre_id == m.id, CatalogoMunicipio.tipo == "geo_localidad").order_by(CatalogoMunicipio.clave).limit(40))]
        if not locs:
            print("El municipio no tiene geografía: corre copiar_geografia.py primero", file=sys.stderr)
            return 2

        nuevos = capturas = 0
        for i, (nombre, genero, edad, n_apoyo, atras, n_nivel) in enumerate(PERSONAS):
            curp = f"EJEMPLO{i + 1:04d}"
            b = db.scalar(select(Beneficiario).where(Beneficiario.municipio_id == mid, Beneficiario.curp == curp))
            if b is None:
                m, l = locs[(i * 7) % len(locs)]
                nac = dia.replace(year=dia.year - edad, month=3, day=15) if edad else dia
                b = Beneficiario(municipio_id=mid, curp=curp, nombre=f"{nombre} (EJEMPLO)", fecha_nacimiento=nac, genero=genero,
                                 cp="36000", estado_id=mun.estado_republica_id, municipio_geo_id=m.id, localidad_id=l.id,
                                 calle="Calle de Ejemplo", numero=str(10 + i), colonia="Colonia Ejemplo",
                                 telefono=f"4770000{i:04d}", correo=f"ejemplo{i + 1}@example.com", es_ejemplo=True)
                db.add(b)
                db.flush()
                nuevos += 1
            if db.scalar(select(CapturaApoyo.id).where(CapturaApoyo.beneficiario_id == b.id).limit(1)) is None:
                apoyo = apoyos[n_apoyo % len(apoyos)]
                desc = db.scalars(select(DescripcionApoyo).where(DescripcionApoyo.apoyo_id == apoyo.id).order_by(DescripcionApoyo.clave)).first()
                entrega = dia - timedelta(days=atras)
                e = vpd.calcular_edad(b.fecha_nacimiento, entrega)
                db.add(CapturaApoyo(
                    municipio_id=mid, beneficiario_id=b.id, programa_id=programa.id, apoyo_id=apoyo.id,
                    descripcion_apoyo_id=desc.id if desc else None,
                    nivel_socioeconomico_id=niveles[n_nivel % len(niveles)].id if niveles else None,
                    grupo_edad_id=vpd.grupo_de_edad(e, rangos), edad=e, cantidad=1 + i % 3, fecha_entrega=entrega,
                    fecha_registro=entrega, observaciones="Captura de ejemplo", es_ejemplo=True))
                capturas += 1
        db.commit()
    print(f"{a.subdominio}: {nuevos} beneficiarios y {capturas} capturas de ejemplo agregados (programa {programa.clave})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
