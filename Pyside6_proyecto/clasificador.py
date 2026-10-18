"""Clasificacion automatica del personal a partir de sus ponchadas y su edificio.

Solo se llena lo que esta en blanco: nunca se pisa un tipo, turno o area que alguien
ya capturo. Antes de aplicar cambios se guarda un respaldo en `respaldos/` (se puede
deshacer con `restaurar`).

Reglas
  Tipo de personal
    * Jornada de 5.5 h o mas entre su primera y ultima ponchada -> tiempo completo.
      Jornada de menos de 4.5 h -> asignatura.
    * Sin dato claro (una sola ponchada al dia, o entre 4.5 y 5.5 h): si poncha en la mitad
      o mas de los dias habiles entre su primera y su ultima ponchada es tiempo completo; si no, asignatura.
    * Tiempo completo se divide en PTC (edificio "Docencia ...") y Administrativo (cualquier otro).
  Turno (solo si no tiene): hora de entrada tipica antes del punto medio entre las
    entradas de los dos turnos -> matutino, despues -> vespertino.
  Area/Carrera (solo si esta vacia y es Administrativo o PTC): su edificio. Las carreras
    de los profesores de asignatura no se pueden deducir de las ponchadas.
"""
from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from store import Maestro, store

TIPO_ADMIN = "Administrativo"
TIPO_PTC = "Profesor de Tiempo Completo"
TIPO_ASIGNATURA = "Profesor de Asignatura"

HORAS_JORNADA_COMPLETA = 5.5
HORAS_JORNADA_CORTA = 4.5
RATIO_TIEMPO_COMPLETO = 0.5
UMBRAL_DIA_LABORABLE = 0.25  # igual que report_data: dia con menos del 25% de la gente tipica no cuenta
RESPALDOS = Path(__file__).resolve().parent / "respaldos"


@dataclass
class Propuesta:
    maestro: Maestro
    cambios: dict = field(default_factory=dict)  # campo de Maestro -> valor nuevo
    motivo: str = ""


def _segundos(hora: str | None) -> int | None:
    return int(hora[:2]) * 3600 + int(hora[3:5]) * 60 + int(hora[6:8] or 0) if hora else None


def _corte_turno() -> float:
    """Hora (decimal) que separa matutino de vespertino: punto medio entre sus entradas."""
    try:
        horas = [int(store.turnos[t]["hora_entrada"][:2]) + int(store.turnos[t]["hora_entrada"][3:5]) / 60
                 for t in ("matutino", "vespertino")]
        return sum(horas) / 2
    except (KeyError, ValueError):
        return 12.0


def _perfiles(filas: list[dict]) -> dict[str, dict]:
    """Por persona: dias que poncho, proporcion de dias habiles, jornada tipica y entrada tipica."""
    por_dia = Counter(f["fecha"] for f in filas)
    if not por_dia:
        return {}
    minimo = statistics.median(por_dia.values()) * UMBRAL_DIA_LABORABLE
    laborables = sorted(dia for dia, n in por_dia.items() if n >= minimo)
    es_laborable = set(laborables)

    por_persona: dict[str, list[dict]] = defaultdict(list)
    for fila in filas:
        por_persona[fila["maestro_id"]].append(fila)

    perfiles = {}
    for maestro_id, registros in por_persona.items():
        dias = sorted({r["fecha"] for r in registros if r["fecha"] in es_laborable})
        if not dias:
            continue
        habiles_en_su_rango = sum(1 for d in laborables if dias[0] <= d <= dias[-1])
        horas = [
            (_segundos(r["salida"]) - _segundos(r["entrada"])) / 3600
            for r in registros
            if r["entrada"] and r["salida"] and r["salida"] > r["entrada"]
        ]
        entradas = [_segundos(r["entrada"]) / 3600 for r in registros if r["entrada"]]
        perfiles[maestro_id] = {
            "dias": len(dias),
            "ratio": len(dias) / max(habiles_en_su_rango, 1),
            "horas": statistics.median(horas) if horas else None,
            "entrada": statistics.median(entradas) if entradas else None,
        }
    return perfiles


def _decidir_tipo(maestro: Maestro, perfil: dict) -> tuple[str, str]:
    horas, ratio = perfil["horas"], perfil["ratio"]
    if horas is not None and horas >= HORAS_JORNADA_COMPLETA:
        completo, razon = True, f"jornada de {horas:.1f} h"
    elif horas is not None and 0 < horas < HORAS_JORNADA_CORTA:
        completo, razon = False, f"jornada de {horas:.1f} h"
    else:
        completo = ratio >= RATIO_TIEMPO_COMPLETO
        razon = f"poncha {ratio:.0%} de los días hábiles"
    if not completo:
        return TIPO_ASIGNATURA, f"{razon} → asignatura"
    if (maestro.edificio or "").lower().startswith("docencia"):
        return TIPO_PTC, f"{razon}, edificio {maestro.edificio} → PTC"
    return TIPO_ADMIN, f"{razon}, edificio {maestro.edificio or 'sin edificio'} → administrativo"


def proponer(maestros: list[Maestro], filas: list[dict] | None = None) -> list[Propuesta]:
    """Propuesta por cada persona de `maestros` a la que le falte tipo, turno o area."""
    perfiles = _perfiles(filas if filas is not None else store.historial_ponchadas())
    corte = _corte_turno()
    propuestas = []
    for maestro in maestros:
        perfil = perfiles.get(maestro.id)
        propuesta = Propuesta(maestro)
        motivos = []
        tipo = maestro.tipo_personal
        if perfil is None:
            propuesta.motivo = "sin ponchadas todavía: no hay con qué clasificar"
            propuestas.append(propuesta)
            continue
        if not tipo:
            tipo, motivo = _decidir_tipo(maestro, perfil)
            propuesta.cambios["tipo_personal"] = tipo
            motivos.append(motivo)
        if not maestro.turno and perfil["entrada"] is not None:
            turno = "matutino" if perfil["entrada"] < corte else "vespertino"
            propuesta.cambios["turno"] = turno
            motivos.append(f"entra hacia las {int(perfil['entrada']):02d}:{int(perfil['entrada'] % 1 * 60):02d} → {turno}")
        if not maestro.area_carrera and tipo in (TIPO_ADMIN, TIPO_PTC) and maestro.edificio:
            propuesta.cambios["area_carrera"] = maestro.edificio
            motivos.append(f"área = edificio ({maestro.edificio})")
        propuesta.motivo = "; ".join(motivos)
        propuestas.append(propuesta)
    return propuestas


def aplicar(propuestas: list[Propuesta]) -> Path | None:
    """Guarda los cambios (con respaldo previo). Regresa la ruta del respaldo o None si no habia nada."""
    pendientes = [p for p in propuestas if p.cambios]
    if not pendientes:
        return None
    RESPALDOS.mkdir(exist_ok=True)
    ruta = RESPALDOS / f"clasificacion_antes_{datetime.now():%Y%m%d_%H%M%S}.json"
    respaldo = [
        {
            "id": p.maestro.id,
            "nombre": p.maestro.nombre,
            "tipo_personal": p.maestro.tipo_personal,
            "turno_id": p.maestro.turno,
            "area_carrera": p.maestro.area_carrera,
        }
        for p in pendientes
    ]
    ruta.write_text(json.dumps(respaldo, ensure_ascii=False, indent=2), encoding="utf-8")
    for propuesta in pendientes:
        store.update_maestro(propuesta.maestro.id, **propuesta.cambios)
    return ruta


def restaurar(ruta: str | Path) -> int:
    """Regresa a cada persona del respaldo a como estaba antes de clasificar."""
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    for fila in datos:
        store.update_maestro(
            fila["id"], tipo_personal=fila["tipo_personal"], turno=fila["turno_id"], area_carrera=fila["area_carrera"]
        )
    return len(datos)


def clasificar_pendientes(maestros: list[Maestro] | None = None) -> tuple[list[Propuesta], Path | None]:
    """Propone y aplica de una vez. Sin argumentos revisa a todo el personal al que le falte algo."""
    objetivo = maestros if maestros is not None else [
        m for m in store.maestros if not m.tipo_personal or not m.turno or not m.area_carrera
    ]
    propuestas = proponer(objetivo)
    return propuestas, aplicar(propuestas)


def resumen(propuestas: list[Propuesta]) -> str:
    """Texto corto con cuantas personas quedaron en cada tipo."""
    tipos = Counter(p.cambios["tipo_personal"] for p in propuestas if "tipo_personal" in p.cambios)
    partes = [f"{n} {tipo}" for tipo, n in tipos.most_common()]
    sin_datos = sum(1 for p in propuestas if not p.cambios and "sin ponchadas" in p.motivo)
    if sin_datos:
        partes.append(f"{sin_datos} sin ponchadas (se clasifican cuando tengan)")
    return ", ".join(partes) or "nada que clasificar"
