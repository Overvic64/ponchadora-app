from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import pandas as pd

from config.settings import (
	DEDUPLICATION_WINDOW_SECONDS,
	ENTRY_TOLERANCE_MINUTES,
	SCHEDULED_ENTRY_TIME,
)


@dataclass(frozen=True)
class CleaningResult:
	cleaned: pd.DataFrame
	daily_summary: pd.DataFrame
	input_count: int
	duplicate_count: int
	window_discard_count: int
	invalid_date_count: int


WEEKDAY_COLUMNS = ("LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES")
WEEKDAY_INDEX = {index: name for index, name in enumerate(WEEKDAY_COLUMNS)}


def _daily_status(day_records: pd.DataFrame, scheduled_time: time) -> tuple[str, float, int, str]:
	if day_records.empty:
		return "Ausente", 0.0, 0, "Falta"

	punches = day_records["fecha_hora_dt"].sort_values()
	entry = punches.iloc[0]
	exit_time = punches.iloc[-1]
	if len(punches) == 1:
		if entry.time() <= (datetime.combine(entry.date(), scheduled_time) + timedelta(hours=4)).time():
			return "FIS", 0.0, _late_minutes(entry, scheduled_time), "FIS"
		return "FIE", 0.0, 0, "FIE"

	hours = round((exit_time - entry).total_seconds() / 3600, 2)
	late = _late_minutes(entry, scheduled_time)
	return (f"{late}m Retardo" if late else f"{hours:.2f} hrs"), hours, late, ("Retardo" if late else "A tiempo")


def _late_minutes(entry: pd.Timestamp, scheduled_time: time) -> int:
	scheduled = datetime.combine(entry.date(), scheduled_time)
	actual = entry.to_pydatetime()
	if actual <= scheduled + timedelta(minutes=ENTRY_TOLERANCE_MINUTES):
		return 0
	return max(0, int((actual - scheduled).total_seconds() // 60))


def procesar_semana(
	fecha_inicio: date | str,
	fecha_fin: date | str,
	records: pd.DataFrame | None = None,
	profesores: pd.DataFrame | list | None = None,
	hora_programada: str = SCHEDULED_ENTRY_TIME,
) -> pd.DataFrame:
	"""Construye el resumen laboral con horas, retardos e incidencias.

	Una fila diaria con una sola ponchada se clasifica como FIS si ocurrió
	por la mañana y como FIE si ocurrió después; sin ponchadas es Falta.
	"""
	start = pd.Timestamp(fecha_inicio).normalize()
	end = pd.Timestamp(fecha_fin).normalize()
	if end < start:
		raise ValueError("fecha_fin debe ser posterior o igual a fecha_inicio")
	scheduled = datetime.strptime(hora_programada, "%H:%M").time()
	columns = ["codigo", "nombre", "area", *WEEKDAY_COLUMNS, "TOTAL HRS", "RETARDOS (MIN)"]

	if records is None:
		records = pd.DataFrame(columns=["codigo", "nombre", "area", "fecha_hora_dt"])
	frame = records.copy()
	if not frame.empty and "fecha_hora_dt" not in frame:
		frame["fecha_hora_dt"] = pd.to_datetime(frame["punched_at"], errors="coerce")
	if not frame.empty:
		frame["fecha_hora_dt"] = pd.to_datetime(frame["fecha_hora_dt"], errors="coerce")
		frame = frame.dropna(subset=["fecha_hora_dt"])
		frame = frame[(frame["fecha_hora_dt"] >= start) & (frame["fecha_hora_dt"] < end + pd.Timedelta(days=1))]
	for column, default in (("codigo", ""), ("nombre", ""), ("area", "General")):
		if column not in frame:
			frame[column] = default

	if profesores is None:
		professor_frame = frame[["codigo", "nombre", "area"]].drop_duplicates() if not frame.empty else pd.DataFrame(columns=["codigo", "nombre", "area"])
	elif isinstance(profesores, pd.DataFrame):
		professor_frame = profesores.copy()
	else:
		professor_frame = pd.DataFrame([dict(row) for row in profesores])
	for column, default in (("codigo", ""), ("nombre", ""), ("area", "General")):
		if column not in professor_frame:
			professor_frame[column] = default
	professor_frame = professor_frame[["codigo", "nombre", "area"]].drop_duplicates("codigo")

	result_rows = []
	for professor in professor_frame.itertuples(index=False):
		values = {"codigo": professor.codigo, "nombre": professor.nombre, "area": professor.area}
		total_hours = 0.0
		total_late = 0
		for offset, weekday in enumerate(WEEKDAY_COLUMNS):
			day = start + pd.Timedelta(days=offset)
			day_records = frame[(frame["codigo"] == professor.codigo) & (frame["fecha_hora_dt"].dt.date == day.date())]
			status, hours, late, _incidence = _daily_status(day_records, scheduled)
			values[weekday] = status
			total_hours += hours
			total_late += late
		values["TOTAL HRS"] = round(total_hours, 2)
		values["RETARDOS (MIN)"] = total_late
		result_rows.append(values)
	return pd.DataFrame(result_rows, columns=columns).sort_values("nombre").reset_index(drop=True) if result_rows else pd.DataFrame(columns=columns)


def generar_resumen_semanal(
	records: pd.DataFrame,
	fecha_inicio: date | str,
	fecha_fin: date | str,
) -> pd.DataFrame:
	"""Genera horas por trabajador y jornada laboral de lunes a viernes.

	Records debe contener codigo, nombre y fecha_hora_dt; cada jornada usa
	la primera y ultima ponchada del trabajador. Una jornada con una sola
	ponchada aporta cero horas porque no existe una salida verificable.
	"""
	start = pd.Timestamp(fecha_inicio).normalize()
	end = pd.Timestamp(fecha_fin).normalize()
	if end < start:
		raise ValueError("fecha_fin debe ser posterior o igual a fecha_inicio")

	columns = ["codigo", "nombre", *WEEKDAY_COLUMNS, "TOTAL HRS"]
	if records.empty:
		return pd.DataFrame(columns=columns)

	frame = records.copy()
	if "fecha_hora_dt" not in frame:
		frame["fecha_hora_dt"] = pd.to_datetime(frame["punched_at"], errors="coerce")
	frame = frame.dropna(subset=["fecha_hora_dt"])
	frame = frame[
		(frame["fecha_hora_dt"] >= start)
		& (frame["fecha_hora_dt"] < end + pd.Timedelta(days=1))
		& (frame["fecha_hora_dt"].dt.weekday < 5)
	].copy()
	if frame.empty:
		return pd.DataFrame(columns=columns)

	frame["day_name"] = frame["fecha_hora_dt"].dt.dayofweek.map(
		{index: name for index, name in enumerate(WEEKDAY_COLUMNS)}
	)
	daily = (
		frame.groupby(["codigo", "nombre", frame["fecha_hora_dt"].dt.date, "day_name"])
		["fecha_hora_dt"]
		.agg(["min", "max", "count"])
		.reset_index()
	)
	daily["hours"] = ((daily["max"] - daily["min"]).dt.total_seconds() / 3600).where(
		daily["count"] > 1, 0.0
	)
	pivot = daily.pivot_table(
		index=["codigo", "nombre"], columns="day_name", values="hours", aggfunc="sum", fill_value=0
	).reset_index()
	for weekday in WEEKDAY_COLUMNS:
		if weekday not in pivot:
			pivot[weekday] = 0.0
	pivot["TOTAL HRS"] = pivot[list(WEEKDAY_COLUMNS)].sum(axis=1)
	return pivot[columns].sort_values("nombre").reset_index(drop=True)


def calcular_horas_diarias(records: pd.DataFrame) -> pd.DataFrame:
	"""Devuelve una fila por trabajador y fecha con entrada, salida y horas."""
	if records.empty:
		return pd.DataFrame(columns=["codigo", "nombre", "fecha", "entrada", "salida", "horas"])
	frame = records.copy()
	frame["fecha_hora_dt"] = pd.to_datetime(frame["fecha_hora_dt"], errors="coerce")
	frame = frame.dropna(subset=["fecha_hora_dt"])
	daily = frame.groupby(["codigo", "nombre", frame["fecha_hora_dt"].dt.date])["fecha_hora_dt"].agg(["min", "max", "count"]).reset_index()
	daily["entrada"] = daily["min"].dt.strftime("%H:%M:%S")
	daily["salida"] = daily["max"].dt.strftime("%H:%M:%S")
	daily["horas"] = ((daily["max"] - daily["min"]).dt.total_seconds() / 3600).where(daily["count"] > 1, 0.0)
	return daily.rename(columns={"fecha_hora_dt": "fecha"})[["codigo", "nombre", "fecha", "entrada", "salida", "horas"]]


def clean_attendance(
	records: pd.DataFrame,
	window_seconds: int = DEDUPLICATION_WINDOW_SECONDS,
) -> CleaningResult:
	frame = records.copy()
	input_count = len(frame)
	frame = frame.sort_values(["codigo", "fecha_hora_dt"]).reset_index(drop=True)
	before_duplicates = len(frame)
	frame = frame.drop_duplicates(subset=["codigo", "fecha_hora_dt"]).copy()
	duplicate_count = before_duplicates - len(frame)
	frame["difference_seconds"] = (
		frame.groupby("codigo")["fecha_hora_dt"].diff().dt.total_seconds()
	)
	keep = frame["difference_seconds"].isna() | (
		frame["difference_seconds"] > window_seconds
	)
	cleaned = frame[keep].copy()
	window_discard_count = len(frame) - len(cleaned)
	cleaned["fecha"] = cleaned["fecha_hora_dt"].dt.strftime("%Y-%m-%d")
	cleaned["hora"] = cleaned["fecha_hora_dt"].dt.strftime("%H:%M:%S")
	daily_summary = (
		cleaned.groupby(["fecha", "codigo", "nombre"], as_index=False)
		.agg(entrada=("hora", "min"), salida=("hora", "max"))
		.sort_values(["fecha", "codigo"])
	)
	return CleaningResult(
		cleaned=cleaned,
		daily_summary=daily_summary,
		input_count=input_count,
		duplicate_count=duplicate_count,
		window_discard_count=window_discard_count,
		invalid_date_count=int(records.attrs.get("invalid_dates", 0)),
	)
