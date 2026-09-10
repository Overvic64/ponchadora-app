from pathlib import Path

import pandas as pd

from config.settings import REQUIRED_COLUMNS


class InputFileError(ValueError):
	"""Raised when the input file cannot be converted to attendance records."""


def read_attendance_file(file_path: str | Path) -> pd.DataFrame:
	path = Path(file_path)
	if not path.exists():
		raise InputFileError(f"No existe el archivo: {path}")

	suffix = path.suffix.lower()
	if suffix == ".csv":
		try:
			frame = pd.read_csv(path, sep=";", encoding="utf-8")
		except UnicodeDecodeError:
			frame = pd.read_csv(path, sep=";", encoding="latin-1")
	elif suffix in {".xlsx", ".xls"}:
		frame = pd.read_excel(path)
	else:
		raise InputFileError("El archivo debe tener extension .csv, .xlsx o .xls")

	missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
	if missing:
		raise InputFileError("Faltan columnas requeridas: " + ", ".join(missing))

	records = frame[list(REQUIRED_COLUMNS)].copy()
	records.columns = ["fecha_hora", "codigo", "nombre"]
	area_column = next(
		(column for column in ("Área", "Area", "Departamento", "Carrera") if column in frame.columns),
		None,
	)
	records["area"] = frame[area_column].astype("string").fillna("General").str.strip() if area_column else "General"
	records["codigo"] = records["codigo"].astype("string").fillna("").str.strip()
	records["nombre"] = records["nombre"].astype("string").fillna("").str.strip()
	records["fecha_hora"] = records["fecha_hora"].astype("string").fillna("").str.strip()
	records["fecha_hora_dt"] = pd.to_datetime(
		records["fecha_hora"], format="%d/%m/%Y %H:%M:%S", errors="coerce"
	)
	invalid_dates = int(records["fecha_hora_dt"].isna().sum())
	records = records[records["fecha_hora_dt"].notna() & records["codigo"].ne("")].copy()
	if records.empty:
		raise InputFileError("No se encontraron registros validos en el archivo")
	records.attrs["invalid_dates"] = invalid_dates
	return records
