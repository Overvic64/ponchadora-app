from pathlib import Path
from datetime import date
import customtkinter as ctk

from config.settings import APP_NAME, BG_COLOR, DATABASE_PATH, ERROR_COLOR, MUTED_TEXT_COLOR, OUTPUT_DIR, PRIMARY_COLOR, PRIMARY_HOVER_COLOR, SURFACE_COLOR, TEXT_COLOR, ensure_directories
from core.attendance_engine import CleaningResult, clean_attendance
from core.database import Database
from core.excel_parser import InputFileError, read_attendance_file
from core.report_generator import export_reports
from ui.components.file_uploader import FileUploader
from ui.components.navbar import NavigationBar
from ui.views.attendance_view import AttendanceView
from ui.views.home_view import HomeView


class PonchadoraApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ensure_directories()
        self.database = Database(DATABASE_PATH)
        self.current_file: Path | None = None
        self.last_result: CleaningResult | None = None
        self.title(APP_NAME)
        self.geometry("1100x700")
        self.minsize(900, 600)
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("green")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        NavigationBar(self, self.show_view).grid(row=0, column=0, sticky="nsew")
        self.content = ctk.CTkFrame(self, fg_color=BG_COLOR, corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(1, weight=1)
        self.selected_week: date | None = None
        self.show_view("home")

    def clear_content(self):
        for child in self.content.winfo_children():
            child.destroy()

    def show_view(self, view: str):
        self.clear_content()
        if view == "attendance":
            self.build_attendance_view()
        elif view == "weekly":
            self.build_weekly_view()
        elif view == "reports":
            self.build_reports_view()
        else:
            self.build_home_view()

    def page_title(self, title: str, subtitle: str):
        ctk.CTkLabel(self.content, text=title, font=ctk.CTkFont(size=30, weight="bold"), text_color=TEXT_COLOR).grid(row=0, column=0, sticky="w", padx=44, pady=(38, 4))
        ctk.CTkLabel(self.content, text=subtitle, text_color=MUTED_TEXT_COLOR).grid(row=0, column=0, sticky="w", padx=46, pady=(84, 0))

    def build_home_view(self):
        HomeView(self.content, self.database, self.on_import_completed).grid(row=1, column=0, sticky="nsew")

    def build_attendance_view(self):
        self.build_home_view()

    def build_weekly_view(self):
        AttendanceView(self.content, self.database, week_start=self.selected_week).grid(row=1, column=0, sticky="nsew")

    def on_import_completed(self, week_start):
        self.selected_week = week_start
        self.show_view("weekly")

    def on_file_selected(self, path: Path):
        self.current_file = path
        self.status_label.configure(text=f"Archivo seleccionado: {path.name}", text_color="#65d6c3")
        self.process_button.configure(state="normal")

    def process_file(self):
        if not self.current_file:
            return
        try:
            records = read_attendance_file(self.current_file)
            self.last_result = clean_attendance(records)
            self.database.save_import(self.current_file.name, self.last_result)
            cleaned, summary = export_reports(self.last_result, OUTPUT_DIR, self.current_file.stem)
            self.status_label.configure(text=f"Completado: {cleaned.name} y {summary.name}", text_color="#65d6c3")
            self.process_button.configure(state="disabled")
        except (InputFileError, OSError, ValueError) as error:
            self.status_label.configure(text=str(error), text_color="#ff8d8d")

    def build_reports_view(self):
        self.page_title("Historial", "Importaciones realizadas y cantidad de registros conservados.")
        table = ctk.CTkScrollableFrame(self.content, fg_color=SURFACE_COLOR, border_width=1, border_color="#D9E5DC")
        table.grid(row=1, column=0, sticky="nsew", padx=44, pady=44)
        headers = ("Archivo", "Fecha", "Originales", "Conservados", "Descartados")
        for column, header in enumerate(headers):
            ctk.CTkLabel(table, text=header, text_color=PRIMARY_COLOR, font=ctk.CTkFont(weight="bold")).grid(row=0, column=column, sticky="w", padx=14, pady=12)
        for row_index, record in enumerate(self.database.recent_imports(), start=1):
            values = (record["source_name"], record["imported_at"], record["input_count"], record["cleaned_count"], record["discarded_count"])
            for column, value in enumerate(values):
                ctk.CTkLabel(table, text=str(value), text_color=TEXT_COLOR).grid(row=row_index, column=column, sticky="w", padx=14, pady=10)


if __name__ == "__main__":
    PonchadoraApp().mainloop()