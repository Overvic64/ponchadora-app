"""Generador de datos de ejemplo para la vista previa de reportes.

Combina maestros + incidencias capturadas en el store para simular lo que,
una vez conectada Supabase, vendria de cruzar `reporte_asistencias` con
`incidencias`. La regla de resolucion (incidencia manual > FI > FIE/FIS >
retardo) es la misma que se definio para la vista final combinada.
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from store import TURNOS, store


def business_days(anio: int, mes: int, mitad: str) -> list[date]:
    """mitad: 'primera' (dias 1-15) o 'segunda' (16 al fin de mes)."""
    if mitad == "primera":
        start, end = 1, 15
    else:
        start = 16
        end = (date(anio, mes % 12 + 1, 1) - timedelta(days=1)).day if mes != 12 else 31
    dias = [date(anio, mes, d) for d in range(start, end + 1)]
    return [d for d in dias if d.weekday() < 5]


def _incidencia_para(maestro_id: str, dia: date) -> str | None:
    for incidencia in store.incidencias:
        if incidencia.maestro_id == maestro_id and incidencia.fecha_inicio <= dia <= incidencia.fecha_fin:
            return incidencia.tipo
    return None


def generar_quincena(maestros, anio: int, mes: int, mitad: str, seed: int = 42):
    """Regresa (dias, {maestro_id: [celda_por_dia]})."""
    rnd = random.Random(seed)
    dias = business_days(anio, mes, mitad)
    resultado = {}
    for maestro in maestros:
        turno_ref = TURNOS[maestro.turno]
        base_h, base_m = (int(p) for p in turno_ref["hora_entrada"].split(":"))
        salida_h, salida_m = (int(p) for p in turno_ref["hora_salida"].split(":"))
        tolerancia = turno_ref["tolerancia_minutos"]

        celdas = []
        for dia in dias:
            clave_manual = _incidencia_para(maestro.id, dia)
            if clave_manual:
                celdas.append({"dia": dia, "tipo": "incidencia", "clave": clave_manual})
                continue

            roll = rnd.random()
            if roll < 0.04:
                celdas.append({"dia": dia, "tipo": "FI"})
                continue
            if roll < 0.06:
                celdas.append({"dia": dia, "tipo": "FIE"})
                continue
            if roll < 0.08:
                celdas.append({"dia": dia, "tipo": "FIS"})
                continue

            retardo_bruto = rnd.choice([0, 0, 0, 4, 8, 12, 18, 24]) if roll < 0.30 else 0
            entrada_total_min = base_h * 60 + base_m + retardo_bruto
            entrada = f"{entrada_total_min // 60:02d}:{entrada_total_min % 60:02d}"
            salida = f"{salida_h:02d}:{salida_m:02d}"
            retardo_neto = max(0, retardo_bruto - tolerancia)
            celdas.append(
                {
                    "dia": dia,
                    "tipo": "completo",
                    "entrada": entrada,
                    "salida": salida,
                    "retardo_min": retardo_neto,
                }
            )
        resultado[maestro.id] = celdas
    return dias, resultado


def resumen_concentrado(celdas: list[dict]) -> dict:
    """Cuenta dias de falta y minutos de retardo para el reporte F05."""
    dias_falta = sum(1 for c in celdas if c["tipo"] in ("FI", "FIE", "FIS"))
    minutos_incidencia_dias = sum(
        1 for c in celdas if c["tipo"] == "incidencia" and c["clave"] in ("I", "AM")
    )
    total_minutos_retardo = sum(c.get("retardo_min", 0) for c in celdas if c["tipo"] == "completo")
    return {
        "dias": dias_falta + minutos_incidencia_dias,
        "horas": total_minutos_retardo // 60,
        "minutos": total_minutos_retardo % 60,
    }
