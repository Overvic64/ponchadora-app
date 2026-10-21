"""Calendario escolar oficial de la UTN. Define que dias NO son laborables: dias
inhabiles y periodos de descanso. Un dia sin ponchada en estas fechas no se cuenta
como falta.

Fuentes: Calendario-1.pdf (Calendario Escolar 2025, pagina 2, "Dias Feriados" y
"Periodos de Descanso") y Calendario-2 (Calendario Escolar 2026, enero a agosto).
Septiembre a diciembre de 2026 todavia no se publica: se usan las mismas fechas
que en 2025. Cuando salga, corregirlas aqui.
Para un nuevo ciclo, agregar sus fechas aqui.
"""
from __future__ import annotations

from datetime import date, timedelta

DIAS_INHABILES = {
    date(2025, 2, 3): "Día de la Constitución Mexicana",
    date(2025, 2, 24): "Día de la Bandera",
    date(2025, 3, 17): "Natalicio de Benito Juárez",
    date(2025, 5, 1): "Día del Trabajo",
    date(2025, 5, 5): "Batalla de Puebla",
    date(2025, 5, 9): "Día de las Madres",
    date(2025, 5, 15): "Día del Maestro",
    date(2025, 7, 28): "Día del Servidor Público",
    date(2025, 9, 15): "Día de la Independencia",
    date(2025, 9, 16): "Día de la Independencia",
    date(2025, 10, 13): "Descubrimiento de América",
    date(2025, 11, 3): "Día de Muertos",
    date(2025, 11, 17): "Día de la Revolución Mexicana",
    date(2026, 1, 5): "Sustitución por el 25 de diciembre",
    date(2026, 1, 6): "Sustitución por el 1 de enero",
    # 2026 (Calendario Escolar 2026)
    date(2026, 2, 2): "Día de la Constitución Mexicana",
    date(2026, 2, 24): "Día de la Bandera",
    date(2026, 3, 16): "Natalicio de Benito Juárez",
    date(2026, 5, 1): "Día del Trabajo",
    date(2026, 5, 5): "Batalla de Puebla",
    date(2026, 5, 11): "Día de las Madres",
    date(2026, 5, 15): "Día del Maestro",
    date(2026, 7, 27): "Día del Servidor Público",
    # septiembre a diciembre de 2026: mismas fechas que 2025 (pendiente el calendario oficial)
    date(2026, 9, 15): "Día de la Independencia",
    date(2026, 9, 16): "Día de la Independencia",
    date(2026, 10, 13): "Descubrimiento de América",
    date(2026, 11, 3): "Día de Muertos",
    date(2026, 11, 17): "Día de la Revolución Mexicana",
}

PERIODOS_DESCANSO = [
    # Cierre de las vacaciones de invierno 2024 (el cuatrimestre inicia el 6 de enero).
    (date(2025, 1, 1), date(2025, 1, 3), "Vacaciones de invierno"),
    (date(2025, 4, 14), date(2025, 4, 25), "Vacaciones de Semana Santa"),
    (date(2025, 7, 14), date(2025, 7, 25), "Vacaciones de verano"),
    (date(2025, 12, 22), date(2026, 1, 2), "Vacaciones de invierno"),
    (date(2026, 3, 30), date(2026, 4, 10), "Vacaciones de Semana Santa"),
    (date(2026, 7, 13), date(2026, 7, 24), "Vacaciones de verano"),
    (date(2026, 12, 22), date(2027, 1, 2), "Vacaciones de invierno"),  # igual que 2025 (pendiente el oficial)
]

# Rango que cubre el calendario. Fuera de el no se sabe que dias son
# inhabiles y se usa la regla de respaldo (dias casi sin ponchadas).
COBERTURA = (date(2025, 1, 1), date(2026, 12, 31))


def cubre(dia: date) -> bool:
    return COBERTURA[0] <= dia <= COBERTURA[1]


def motivo_no_laborable(dia: date) -> str | None:
    """Por que ese dia no se trabaja, o None si es dia laboral."""
    if dia.weekday() >= 5:
        return "Fin de semana"
    if dia in DIAS_INHABILES:
        return DIAS_INHABILES[dia]
    for inicio, fin, motivo in PERIODOS_DESCANSO:
        if inicio <= dia <= fin:
            return motivo
    return None


def dias_laborables(inicio: date, fin: date) -> list[date]:
    dias, dia = [], inicio
    while dia <= fin:
        if motivo_no_laborable(dia) is None:
            dias.append(dia)
        dia += timedelta(days=1)
    return dias
