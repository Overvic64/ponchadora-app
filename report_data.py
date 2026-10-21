"""Datos reales para 'Asistencias'/'Reportes': cruza la vista
`reporte_asistencias` de Supabase (ya calcula edificio, turno y retardo)
con las `incidencias` capturadas a mano para resolver cada dia de la
quincena.

Solo se consideran los dias habiles del calendario escolar (calendario_escolar.py).
Regla de resolucion por dia: incidencia manual capturada > lo que diga
reporte_asistencias (completo / ponchada incompleta) > falta (no hay
ni ponchada ni incidencia ese dia, pero SI hay datos importados de otros
empleados ese mismo dia) > sin datos (nadie tiene ponchada ese dia -- no se
ha importado ese periodo todavia, asi que no se cuenta como falta de nadie).
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

import calendario_escolar
from store import store

# Respaldo del calendario: un dia habil en que poncho menos de este porcentaje
# del dia tipico (lector apagado, dato que no vino en el Excel, o fecha fuera
# del calendario cargado) no se cuenta como falta de nadie.
UMBRAL_DIA_LABORABLE = 0.25

MESES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _ultimo_dia_mes(anio: int, mes: int) -> int:
    if mes == 12:
        return 31
    return (date(anio, mes + 1, 1) - timedelta(days=1)).day


def etiqueta_quincena(anio: int, mes: int, mitad: str) -> str:
    rango = "1-15" if mitad == "primera" else f"16-{_ultimo_dia_mes(anio, mes)}"
    return f"{rango} de {MESES[mes]} {anio}"


def quincenas_disponibles() -> list[tuple[int, int, str]]:
    """Solo las quincenas (anio, mes, mitad) que realmente tienen al menos
    una ponchada importada -- no todo el rango entre la primera y la
    ultima fecha, que puede incluir periodos vacios."""
    return store.quincenas_disponibles()


def resumen_global(maestros, anio: int, mes: int, mitad: str) -> dict:
    """Totales (asistencias/retardos/permisos/faltas) de toda la quincena,
    para las tarjetas y la grafica de Inicio."""
    dias, celdas_por_maestro = generar_quincena(maestros, anio, mes, mitad)
    asistencias = retardos = permisos = faltas = 0
    dias_con_algun_dato = set()
    for celdas in celdas_por_maestro.values():
        for celda in celdas:
            if celda["tipo"] == "completo":
                asistencias += 1
                dias_con_algun_dato.add(celda["dia"])
                if celda["retardo_min"] > 0:
                    retardos += 1
            elif celda["tipo"] == "incidencia":
                permisos += 1
                dias_con_algun_dato.add(celda["dia"])
            elif celda["tipo"] == "falta":
                faltas += 1
                dias_con_algun_dato.add(celda["dia"])
            elif celda["tipo"] == "incompleto":
                # Ese dia si se importo (hay ponchada, aunque incompleta) --
                # no debe contarse como "sin datos" en el aviso de cobertura.
                dias_con_algun_dato.add(celda["dia"])
    return {
        "asistencias": asistencias,
        "retardos": retardos,
        "permisos": permisos,
        "faltas": faltas,
        "dias_totales": len(dias),
        "dias_con_datos": len(dias_con_algun_dato),
    }


def business_days(anio: int, mes: int, mitad: str) -> list[date]:
    """Dias habiles de la quincena (mitad: 'primera' = 1-15, 'segunda' = 16 al
    fin de mes): lunes a viernes, sin los dias inhabiles ni vacaciones del
    calendario escolar."""
    start, end = (1, 15) if mitad == "primera" else (16, _ultimo_dia_mes(anio, mes))
    return [
        dia
        for dia in (date(anio, mes, d) for d in range(start, end + 1))
        if dia.weekday() < 5 and not (calendario_escolar.cubre(dia) and calendario_escolar.motivo_no_laborable(dia))
    ]


def generar_quincena(maestros, anio: int, mes: int, mitad: str):
    """Regresa (dias, {maestro_id: [celda_por_dia]}) usando datos reales."""
    dias = business_days(anio, mes, mitad)
    if not dias:
        return dias, {}

    filas = store.reporte_asistencias(dias[0], dias[-1])
    asistencia_por_clave = {(fila["maestro_id"], fila["fecha"]): fila for fila in filas}
    dias_con_datos = {fila["fecha"] for fila in filas}

    # Un dia en que poncho una fraccion minima del personal (vacaciones,
    # festivos: ej. 2 de enero, 1 de 77) no fue un dia laboral: nadie "falto".
    # Se compara contra el dia tipico de todo lo importado, no de la quincena,
    # porque en una quincena de vacaciones todos los dias vienen casi vacios.
    personas_por_dia = Counter(fila["fecha"] for fila in filas)
    minimo = store.mediana_personas_por_dia() * UMBRAL_DIA_LABORABLE
    dias_laborables = {fecha for fecha, n in personas_por_dia.items() if n >= minimo}

    incidencias_por_maestro: dict[str, list] = {}
    for incidencia in store.incidencias:
        incidencias_por_maestro.setdefault(incidencia.maestro_id, []).append(incidencia)

    resultado = {}
    for maestro in maestros:
        celdas = []
        for dia in dias:
            incidencia = next(
                (
                    i
                    for i in incidencias_por_maestro.get(maestro.id, [])
                    if i.fecha_inicio <= dia <= i.fecha_fin
                ),
                None,
            )
            fecha = dia.isoformat()
            fila = asistencia_por_clave.get((maestro.id, fecha))
            if incidencia:
                celdas.append(
                    {
                        "dia": dia,
                        "tipo": "incidencia",
                        "clave": incidencia.tipo,
                        # Las claves EA/SA solo cubren una marca: la otra se sigue mostrando.
                        "entrada": ((fila or {}).get("entrada") or "")[:5],
                        "salida": ((fila or {}).get("salida") or "")[:5],
                    }
                )
                continue

            if fila is None:
                primera = store.primera_ponchada(maestro.id)
                if fecha not in dias_con_datos:
                    # Nadie tiene ponchada ese dia: no es que todos hayan
                    # faltado, es que ese dia no se ha importado todavia.
                    celdas.append({"dia": dia, "tipo": "sin_datos", "clave": "—"})
                elif (
                    fecha not in dias_laborables
                    or not maestro.activo
                    or primera is None
                    or fecha < primera
                    or maestro.tipo_personal == "Profesor de Asignatura"
                ):
                    # Dia inhabil, empleado dado de baja, todavia no trabajaba
                    # ahi, o profesor de asignatura: solo va los dias que tiene
                    # clase y no hay horario cargado para saber cuales son.
                    celdas.append({"dia": dia, "tipo": "no_aplica", "clave": "—"})
                else:
                    celdas.append({"dia": dia, "tipo": "falta", "clave": "FI"})
            elif fila.get("estado") == "completo":
                celdas.append(
                    {
                        "dia": dia,
                        "tipo": "completo",
                        "entrada": (fila.get("entrada") or "")[:5],
                        "salida": (fila.get("salida") or "")[:5],
                        "retardo_min": fila.get("retardo_minutos_referencia") or 0,
                    }
                )
            else:
                # ponchada incompleta (sin_entrada / sin_salida / etc. segun
                # la vista) -- se muestra el estado tal cual para revisarlo,
                # no se inventa un retardo ni se cuenta como falta.
                estado = (fila.get("estado") or "incompleto").replace("_", " ").upper()
                celdas.append(
                    {
                        "dia": dia,
                        "tipo": "incompleto",
                        "clave": estado,
                        "estado": fila.get("estado"),
                        "entrada": (fila.get("entrada") or "")[:5],
                        "salida": (fila.get("salida") or "")[:5],
                    }
                )
        resultado[maestro.id] = celdas
    return dias, resultado


def resumen_concentrado(celdas: list[dict]) -> dict:
    """Cuenta dias de falta y minutos de retardo para el reporte F05."""
    dias_falta = sum(1 for c in celdas if c["tipo"] == "falta")
    dias_incidencia = sum(
        1 for c in celdas if c["tipo"] == "incidencia" and c["clave"] in ("I", "AM")
    )
    total_minutos_retardo = sum(c.get("retardo_min", 0) for c in celdas if c["tipo"] == "completo")
    return {
        "dias": dias_falta + dias_incidencia,
        "horas": total_minutos_retardo // 60,
        "minutos": total_minutos_retardo % 60,
    }
