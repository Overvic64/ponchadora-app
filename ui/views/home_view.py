from pathlib import Path
from tkinter import filedialog
from datetime import timedelta

import customtkinter as ctk

from config.settings import (
	ACCENT_COLOR,
	BG_COLOR,
	ERROR_COLOR,
	MUTED_TEXT_COLOR,
	PRIMARY_COLOR,
	PRIMARY_HOVER_COLOR,
	SURFACE_COLOR,
	TEXT_COLOR,
)
from core.attendance_engine import clean_attendance
from core.excel_parser import InputFileError, read_attendance_file
from ui.components.file_uploader import FileUploader


class HomeView(ctk.CTkFrame):
	"""Importa, depura, persiste y entrega el control al resumen semanal."""

	def __init__(self, master, database, on_import_completed, **kwargs):
		super().__init__(master, fg_color=BG_COLOR, **kwargs)
		self.database = database
		self.on_import_completed = on_import_completed
		self.current_file: Path | None = None
		self._build()

	def _build(self):
		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(1, weight=1)
		ctk.CTkLabel(self, text="Depurador y control de asistencia", text_color=TEXT_COLOR, font=ctk.CTkFont(size=30, weight="bold")).grid(row=0, column=0, sticky="w", padx=48, pady=(42, 4))
		ctk.CTkLabel(self, text="Importa tus accesos y revisa el resumen semanal en segundos.", text_color=MUTED_TEXT_COLOR).grid(row=0, column=0, sticky="w", padx=50, pady=(92, 0))
		panel = ctk.CTkFrame(self, fg_color=SURFACE_COLOR, border_width=1, border_color="#D9E5DC", corner_radius=10)
		panel.grid(row=1, column=0, sticky="new", padx=48, pady=48)
		panel.grid_columnconfigure(0, weight=1)
		ctk.CTkLabel(panel, text="Carga el archivo de la ponchadora", text_color=TEXT_COLOR, font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, sticky="w", padx=28, pady=(28, 8))
		ctk.CTkLabel(panel, text="Se aceptan archivos CSV, XLSX y XLS. Los duplicados y lecturas dentro de cinco minutos se descartan.", text_color=MUTED_TEXT_COLOR).grid(row=1, column=0, sticky="w", padx=28, pady=(0, 20))
		FileUploader(panel, self._select_file).grid(row=2, column=0, sticky="ew", padx=28, pady=(0, 20))
		self.status = ctk.CTkLabel(panel, text="Listo para comenzar", text_color=MUTED_TEXT_COLOR, anchor="w")
		self.status.grid(row=3, column=0, sticky="ew", padx=28, pady=8)
		self.process_button = ctk.CTkButton(panel, text="Procesar archivo", command=self.process_file, state="disabled", fg_color=PRIMARY_COLOR, hover_color=PRIMARY_HOVER_COLOR, height=42)
		self.process_button.grid(row=4, column=0, sticky="w", padx=28, pady=(8, 28))

	def _select_file(self, path: Path):
		self.current_file = path
		self.status.configure(text=f"Seleccionado: {path.name}", text_color=ACCENT_COLOR)
		self.process_button.configure(state="normal")

	def process_file(self):
		if not self.current_file:
			return
		try:
			records = read_attendance_file(self.current_file)
			result = clean_attendance(records)
			self.database.save_import(self.current_file.name, result)
			self.status.configure(text="Procesamiento completado. Selecciona dónde guardar el Excel limpio.", text_color=ACCENT_COLOR)
			self._save_clean_copy(result)
			first_day = result.cleaned["fecha_hora_dt"].min().date()
			week_start = first_day - timedelta(days=first_day.weekday())
			self.on_import_completed(week_start)
		except (InputFileError, OSError, ValueError) as error:
			self.status.configure(text=str(error), text_color=ERROR_COLOR)

	def _save_clean_copy(self, result):
		path = filedialog.asksaveasfilename(
			title="Guardar copia limpia",
			initialfile=f"{self.current_file.stem}_Ponchadas_Depuradas.xlsx",
			defaultextension=".xlsx",
			filetypes=[("Excel", "*.xlsx")],
		)
		if path:
			output_path = Path(path)
			result.cleaned[["codigo", "nombre", "fecha_hora"]].to_excel(output_path, index=False)
