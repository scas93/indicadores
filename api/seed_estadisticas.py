"""Datos de prueba de Fase 3 (Estadísticas) en un municipio YA CREADO. Idempotente: se puede correr
las veces que haga falta; cada corrida deja exactamente los mismos datos (no duplica nada).

    DATABASE_URL=... PASSWORD_ENCRYPTION_KEY=... python seed_estadisticas.py \\
        --municipio <subdominio> --password '<contraseña del usuario de prueba>' [--usuario informes1]

Carga, con el alcance del municipio dado:
  * centro gestor ECONÓMICO; eje EJE2 «ECONÓMICO» (general, sin centro gestor), un subtema y una estrategia
    de muestra, y el programa 1014
    "Fortalecimiento del empleo y la gestión empresarial" (ejercicio 2025);
  * su MIR: Fin, Propósito, 5 Componentes y 12 Actividades (cada una bajo su componente), con sus 19 indicadores, la meta anual 2025 y
    las capturas A/B mensuales reales (seed_data/economico_2025.py, del export de Cuenta Pública), con su ID
    real (410, 411, 512…), texto de la meta, descripciones de las variables, unidad de medida, año base (2024) con su
    meta programada, y los medios de verificación (fuente de información);
  * un usuario tipo Informes asignado al programa 1014.
Con 2025 deben verse (Dependencias y Ejes): obtenido 7/1/10/1 y (C.O/C.E)×100 14/0/4/1 (total 19).

Re-correr corrige a los valores del seed lo que se haya editado a mano en esos mismos registros (el
indicador se identifica por elemento + nombre); no borra nada que el seed no cree.
"""
import argparse
import os
import sys
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import new_session
from app.models import (Algoritmo, AvanceMensual, CentroGestor, ClasificacionProgramatica, DimensionIndicador,
                        Eje, ElementoMatriz, Estrategia, Frecuencia, Indicador, MetaAnual, Municipio,
                        NivelMatriz, Programa, Subtema, TipoIndicador, TipoUsuario, Usuario, UsuarioPrograma)
from app.security import encrypt_password
from app.tenancy import scope_session
from seed_data import economico_2025 as datos

NIVELES = {"fin": NivelMatriz.fin, "proposito": NivelMatriz.proposito, "componente": NivelMatriz.componente,
           "actividad": NivelMatriz.actividad}


def _uno(db: Session, modelo, llaves: dict, valores: dict | None = None):
    """Busca por `llaves` (dentro del municipio, la Session ya está aislada); si no existe lo crea;
    en ambos casos deja `valores` aplicados. Devuelve el objeto."""
    obj = db.scalar(select(modelo).filter_by(**llaves))
    if obj is None:
        obj = modelo(**llaves)
        db.add(obj)
    for k, v in (valores or {}).items():
        setattr(obj, k, v)
    db.flush()
    return obj


def _d(x) -> Decimal | None:
    return None if x is None else Decimal(str(x))


def _elemento(db: Session, programa: Programa, nivel: str, resumen: str, *, numero: str, orden: int,
              padre: ElementoMatriz | None, medios: str = "", supuestos: str = "") -> ElementoMatriz:
    llaves = {"programa_id": programa.id, "nivel": NIVELES[nivel]}
    if nivel in ("componente", "actividad"):
        llaves["resumen_narrativo"] = resumen  # varios por programa: se distinguen por su texto
    return _uno(db, ElementoMatriz, llaves, {"resumen_narrativo": resumen, "numero": numero, "orden": orden,
                                             "padre_id": padre.id if padre else None, "medios_verificacion": medios,
                                             "supuestos": supuestos})


def sembrar(db: Session, municipio: str, usuario: str, password: str) -> dict:
    """Siembra y hace commit. Lanza ValueError si el municipio no existe."""
    m = db.scalar(select(Municipio).where(Municipio.subdominio == municipio))
    if m is None:
        raise ValueError(f"No existe el municipio «{municipio}» (se crea desde el super admin; este seed no lo crea)")
    scope_session(db, m.id)
    anio = datos.ANIO

    # --- catálogos y programa
    cg = _uno(db, CentroGestor, {"clave": "ECONOMICO"}, {"nombre": "ECONÓMICO", "activo": True})
    # el eje es general (no cuelga de ningún centro gestor); en la referencia es clave EJE2, nombre ECONÓMICO
    eje = _uno(db, Eje, {"clave": "EJE2"}, {"nombre": "ECONÓMICO", "activo": True})
    sub = _uno(db, Subtema, {"eje_id": eje.id, "clave": "DESARROLLO"}, {"nombre": "Desarrollo económico", "activo": True})
    est = _uno(db, Estrategia, {"subtema_id": sub.id, "clave": "EMPLEO"}, {"nombre": "Fortalecimiento del empleo", "activo": True})
    frec = _uno(db, Frecuencia, {"clave": "mensual"}, {"nombre": "Mensual", "activo": True})
    clasif = _uno(db, ClasificacionProgramatica, {"clave": "especificos"}, {"nombre": "Específicos", "activo": True})
    prog = _uno(db, Programa, {"ejercicio_fiscal": anio, "clave": datos.PROGRAMA_CLAVE},
                {"nombre": datos.PROGRAMA_NOMBRE, "centro_gestor_id": cg.id, "subtema_id": sub.id,
                 "estrategia_id": est.id, "clasificacion_programatica_id": clasif.id, "activo": True})

    # --- MIR: la jerarquía de las actividades (`padre_id` del dataset) se dedujo de la Transparencia de referencia
    # los medios de verificación (= "Fuente de información" de Transparencia) son del elemento; aquí uno por indicador
    d_fin = next(i for i in datos.INDICADORES if i["nivel"] == "fin")
    d_prop = next(i for i in datos.INDICADORES if i["nivel"] == "proposito")
    fin = _elemento(db, prog, "fin", d_fin["resumen"], numero="", orden=0, padre=None, medios=d_fin["medios_verificacion"], supuestos=d_fin["supuestos"])
    prop = _elemento(db, prog, "proposito", d_prop["resumen"], numero="", orden=0, padre=None, medios=d_prop["medios_verificacion"], supuestos=d_prop["supuestos"])
    elementos: dict[str, ElementoMatriz] = {}
    comp_por_id: dict[int, ElementoMatriz] = {}
    for ind in datos.INDICADORES:
        if ind["nivel"] == "fin":
            elementos[ind["ref"]] = fin
        elif ind["nivel"] == "proposito":
            elementos[ind["ref"]] = prop
        elif ind["nivel"] == "componente":
            c = _elemento(db, prog, "componente", ind["resumen"], numero=str(len(comp_por_id) + 1),
                          orden=len(comp_por_id) + 1, padre=None, medios=ind["medios_verificacion"], supuestos=ind["supuestos"])
            comp_por_id[ind["id"]] = c
            elementos[ind["ref"]] = c
    hijas: dict[int, int] = {}
    for ind in datos.INDICADORES:
        if ind["nivel"] == "actividad":
            padre = comp_por_id[ind["padre_id"]]
            hijas[ind["padre_id"]] = hijas.get(ind["padre_id"], 0) + 1
            elementos[ind["ref"]] = _elemento(db, prog, "actividad", ind["resumen"], numero=f"{padre.numero}.{hijas[ind['padre_id']]}",
                                              orden=hijas[ind["padre_id"]], padre=padre, medios=ind["medios_verificacion"],
                                              supuestos=ind["supuestos"])

    # --- indicadores, meta anual y capturas mensuales
    n_avances = 0
    objetos: dict[str, Indicador] = {}
    for k, ind in enumerate(datos.INDICADORES):
        r = datos.rangos_de(ind)
        rangos = {f"rango_{c}_{k}": _d(r.get(c, {}).get(k)) for c in ("verde", "amarillo", "rojo") for k in ("desde", "hasta")}
        solo_a = ind["algoritmo"] == "a"
        i = _uno(db, Indicador, {"elemento_matriz_id": elementos[ind["ref"]].id, "nombre": ind["nombre"]}, {
            "tipo": TipoIndicador.estrategico if ind["nivel"] in ("fin", "proposito") else TipoIndicador.gestion,
            "prioritario": False, "interpretacion": "", "dimension": DimensionIndicador.eficacia,
            "frecuencia_id": frec.id, "unidad_medida": ind["unidad_medida"], "anio_base": ind["anio_base"],
            "algoritmo": Algoritmo(ind["algoritmo"]),
            "unidad_a": ind["unidad_a"], "unidad_b": None if solo_a else ind["unidad_b"],
            "descripcion_a": ind["descripcion_a"], "descripcion_b": None if solo_a else ind["descripcion_b"],
            "meta_administracion": ind["meta_texto"],
            "id_numerico": -(k + 1),  # provisional: el ID real se fija abajo sin chocar con la unicidad
            **rangos})
        objetos[ind["ref"]] = i
        # año base: su resultado programado es el "Valor línea base" de Transparencia (de ahí meta_2024_a/b)
        _uno(db, MetaAnual, {"indicador_id": i.id, "anio": ind["anio_base"]},
             {"valor_a_programado": _d(ind["meta_2024_a"]), "valor_b_programado": None if solo_a else _d(ind["meta_2024_b"]),
              "es_ejercicio_fiscal": False})
        _uno(db, MetaAnual, {"indicador_id": i.id, "anio": anio},
             {"valor_a_programado": _d(ind["meta_a"]), "valor_b_programado": None if solo_a else _d(ind["meta_b"]),
              "es_ejercicio_fiscal": True})
        for mes in range(1, 13):
            a, b = ind["A"][mes - 1], (None if solo_a else ind["B"][mes - 1])
            if a is None and b is None:
                continue  # mes sin captura: no se crea fila
            _uno(db, AvanceMensual, {"indicador_id": i.id, "anio": anio, "mes": mes}, {"valor_a": _d(a), "valor_b": _d(b)})
            n_avances += 1

    # --- ID real del indicador (el de la referencia: 410, 411, 512…); el consecutivo automático sigue desde el máximo
    reales = {ind["id"] for ind in datos.INDICADORES}
    ajeno = db.scalar(select(Indicador.id_numerico).where(
        Indicador.id_numerico.in_(reales), Indicador.id.notin_([o.id for o in objetos.values()])))
    if ajeno is not None:
        raise ValueError(f"El ID {ajeno} ya lo usa otro indicador del municipio; no se puede fijar el ID real de la referencia")
    for ind in datos.INDICADORES:
        objetos[ind["ref"]].id_numerico = ind["id"]
    db.flush()

    # --- usuario Informes asignado al programa (la contraseña se fija en cada corrida)
    u = db.scalar(select(Usuario).where(Usuario.usuario == usuario))
    if u is None:
        u = Usuario(usuario=usuario, tipo=TipoUsuario.informes, nombre="Informes (datos de prueba Fase 3)", activo=True,
                    password_encrypted=encrypt_password(password), debe_cambiar_password=True)
        db.add(u)
    else:
        u.password_encrypted = encrypt_password(password)
        u.activo = True
        if u.tipo != TipoUsuario.informes:
            raise ValueError(f"El usuario «{usuario}» ya existe con otro tipo ({u.tipo.value}); elige otro nombre con --usuario")
    db.flush()
    _uno(db, UsuarioPrograma, {"usuario_id": u.id, "programa_id": prog.id})
    db.commit()
    return {"municipio": municipio, "programa": f"{prog.clave} — {prog.nombre}", "indicadores": len(datos.INDICADORES),
            "avances": n_avances, "usuario": usuario, "anio": anio}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--municipio", required=True, help="subdominio del municipio ya creado")
    ap.add_argument("--usuario", default="informes1", help="usuario tipo Informes (default informes1)")
    ap.add_argument("--password", default=os.environ.get("SEED_DEMO_PASSWORD"),
                    help="contraseña del usuario (o env SEED_DEMO_PASSWORD)")
    a = ap.parse_args(argv)
    if not a.password:
        print("Falta la contraseña del usuario (--password o SEED_DEMO_PASSWORD)", file=sys.stderr)
        return 2
    with new_session() as db:
        try:
            r = sembrar(db, a.municipio, a.usuario, a.password)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    print("Listo: {municipio} · programa {programa} · {indicadores} indicadores, {avances} capturas mensuales {anio} · "
          "usuario {usuario}".format(**r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
