from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
import pandas as pd

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
from core.attendance_engine import WEEKDAY_COLUMNS, procesar_semana


class AttendanceView(ctk.CTkFrame):
    """Matriz semanal dinamica de horas, retardos e incidencias."""

    def __init__(self, master, database, week_start: date | None = None, **kwargs):
        super().__init__(master, fg_color=BG_COLOR, **kwargs)
        self.database = database
        self.week_start = self._monday(week_start or date.today())
        self.search_value = ctk.StringVar()
        self.area_value = ctk.StringVar(value="Todos")
        self.week_value = ctk.StringVar(value=self.week_start.isoformat())
        self.summary = pd.DataFrame()
        self.search_value.trace_add("write", lambda *_: self.refresh())
        self._build()
        self.refresh()

    @staticmethod
    def _monday(value: date) -> date:
        return value - timedelta(days=value.weekday())

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(self, text="Resumen semanal", text_color=TEXT_COLOR, font=ctk.CTkFont(size=28, weight="bold")).grid(row=0, column=0, sticky="w", padx=36, pady=(28, 2))
        ctk.CTkLabel(self, text="Horas trabajadas, retardos e incidencias por profesor", text_color=MUTED_TEXT_COLOR).grid(row=0, column=0, sticky="w", padx=38, pady=(68, 0))

        controls = ctk.CTkFrame(self, fg_color=SURFACE_COLOR, border_width=1, border_color="#D9E5DC", corner_radius=8)
        controls.grid(row=1, column=0, sticky="ew", padx=36, pady=14)
        ctk.CTkLabel(controls, text="Semana", text_color=MUTED_TEXT_COLOR).grid(row=0, column=0, padx=(16, 6), pady=12)
        ctk.CTkEntry(controls, textvariable=self.week_value, width=120).grid(row=0, column=1, padx=6, pady=12)
        ctk.CTkButton(controls, text="Actualizar", command=self.refresh, width=100, fg_color=PRIMARY_COLOR, hover_color=PRIMARY_HOVER_COLOR).grid(row=0, column=2, padx=6, pady=12)
        ctk.CTkLabel(controls, text="Area", text_color=MUTED_TEXT_COLOR).grid(row=0, column=3, padx=(18, 6), pady=12)
        self.area_menu = ctk.CTkOptionMenu(controls, variable=self.area_value, values=["Todos"], command=lambda _value: self.refresh(), fg_color=PRIMARY_COLOR, button_color=PRIMARY_HOVER_COLOR)
        self.area_menu.grid(row=0, column=4, padx=6, pady=12)
        ctk.CTkEntry(controls, textvariable=self.search_value, placeholder_text="Buscar nombre o codigo", width=210).grid(row=0, column=5, padx=12, pady=12)
        ctk.CTkButton(controls, text="Exportar Resumen a Excel", command=self.export_summary, fg_color=PRIMARY_COLOR, hover_color=PRIMARY_HOVER_COLOR).grid(row=0, column=6, padx=(0, 16), pady=12)

        self.cards = ctk.CTkFrame(self, fg_color="transparent")
        self.cards.grid(row=2, column=0, sticky="ew", padx=36, pady=4)
        self.cards.grid_columnconfigure((0, 1, 2), weight=1)
        self.card_values = []
        for index, title in enumerate(("PROFESORES REGISTRADOS", "HORAS TOTALES", "RETARDOS (MIN)")):
            card = ctk.CTkFrame(self.cards, fg_color=SURFACE_COLOR, border_width=1, border_color="#D9E5DC", corner_radius=8)
            card.grid(row=0, column=index, sticky="ew", padx=4)
            ctk.CTkLabel(card, text=title, text_color=MUTED_TEXT_COLOR, font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w", padx=16, pady=(12, 2))
            value = ctk.CTkLabel(card, text="0", text_color=ACCENT_COLOR, font=ctk.CTkFont(size=21, weight="bold"))
            value.pack(anchor="w", padx=16, pady=(0, 12))
            self.card_values.append(value)

        self.table = ctk.CTkScrollableFrame(self, fg_color=SURFACE_COLOR, border_width=1, border_color="#D9E5DC", corner_radius=8)
        self.table.grid(row=3, column=0, sticky="nsew", padx=36, pady=(8, 18))
        self.detail = ctk.CTkLabel(self, text="La tabla muestra la semana seleccionada.", text_color=MUTED_TEXT_COLOR, anchor="w")
        self.detail.grid(row=4, column=0, sticky="ew", padx=40, pady=(0, 16))

    def _parse_week(self) -> date:
        try:
            return self._monday(datetime.strptime(self.week_value.get().strip(), "%Y-%m-%d").date())
        except ValueError as error:
            raise ValueError("La semana debe tener formato AAAA-MM-DD") from error

    def refresh(self):
        try:
            self.week_start = self._parse_week()
            self.week_value.set(self.week_start.isoformat())
            week_end = self.week_start + timedelta(days=4)
            rows = self.database.attendance_between(self.week_start.isoformat(), week_end.isoformat())
            records = pd.DataFrame([dict(row) for row in rows])
            if records.empty:
                records = pd.DataFrame(columns=["codigo", "nombre", "area", "punched_at", "fecha_hora_dt"])
            else:
                records["fecha_hora_dt"] = pd.to_datetime(records["punched_at"], errors="coerce")
            professors = pd.DataFrame([dict(row) for row in self.database.professors()])
            areas = ["Todos"] + sorted(professors["area"].dropna().unique().tolist()) if not professors.empty else ["Todos"]
            self.area_menu.configure(values=areas)
            if self.area_value.get() not in areas:
                self.area_value.set("Todos")
            if self.area_value.get() != "Todos":
                professors = professors[professors["area"].eq(self.area_value.get())]
                records = records[records["area"].eq(self.area_value.get())]
            summary = procesar_semana(self.week_start, week_end, records, professors)
            query = self.search_value.get().strip().casefold()
            if query:
                mask = summary["nombre"].astype(str).str.casefold().str.contains(query, na=False) | summary["codigo"].astype(str).str.casefold().str.contains(query, na=False)
                summary = summary[mask]
            self.summary = summary.reset_index(drop=True)
            self._render_table()
            self.card_values[0].configure(text=str(len(self.summary)))
            self.card_values[1].configure(text=f"{self.summary['TOTAL HRS'].sum():.2f} hrs" if not self.summary.empty else "0 hrs")
            self.card_values[2].configure(text=str(int(self.summary["RETARDOS (MIN)"].sum())) if not self.summary.empty else "0")
            self.detail.configure(text=f"Semana: {self.week_start:%d/%m/%Y} - {(self.week_start + timedelta(days=4)):%d/%m/%Y}", text_color=MUTED_TEXT_COLOR)
        except ValueError as error:
            self.detail.configure(text=str(error), text_color=ERROR_COLOR)

    def _render_table(self):
        for child in self.table.winfo_children():
            child.destroy()
        headers = ("CODIGO", "NOMBRE", "AREA", *WEEKDAY_COLUMNS, "TOTAL HRS", "RETARDOS (MIN)")
        for column, header in enumerate(headers):
            ctk.CTkLabel(self.table, text=header, text_color=PRIMARY_COLOR, font=ctk.CTkFont(size=10, weight="bold"), anchor="w").grid(row=0, column=column, sticky="ew", padx=8, pady=11)
        for row_index, (_, row) in enumerate(self.summary.iterrows(), start=1):
            values = [row["codigo"], row["nombre"], row["area"], *(row[day] for day in WEEKDAY_COLUMNS), f"{row['TOTAL HRS']:.2f} hrs", str(int(row["RETARDOS (MIN)"]))]
            for column, value in enumerate(values):
                color = ERROR_COLOR if any(marker in str(value) for marker in ("FIE", "FIS", "Falta", "Retardo")) else TEXT_COLOR
                ctk.CTkLabel(self.table, text=str(value), text_color=color, anchor="w").grid(row=row_index, column=column, sticky="ew", padx=8, pady=8)

    def export_summary(self):
        if self.summary.empty:
            self.detail.configure(text="No hay datos para exportar.", text_color=ERROR_COLOR)
            return
        path = filedialog.asksaveasfilename(title="Exportar Resumen a Excel", initialfile=f"Resumen_Semanal_{self.week_start}.xlsx", defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if path:
            self.summary.to_excel(Path(path), index=False)
            self.detail.configure(text=f"Resumen guardado en: {path}", text_color=ACCENT_COLOR)
