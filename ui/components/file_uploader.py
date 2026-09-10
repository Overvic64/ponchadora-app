from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from config.settings import MUTED_TEXT_COLOR, PRIMARY_COLOR, PRIMARY_HOVER_COLOR, TEXT_COLOR


class FileUploader(ctk.CTkFrame):
	def __init__(self, master, on_file_selected, **kwargs):
		super().__init__(master, fg_color="transparent", **kwargs)
		self.on_file_selected = on_file_selected
		self.selected_path: Path | None = None
		self.path_label = ctk.CTkLabel(self, text="Ningun archivo seleccionado", text_color=MUTED_TEXT_COLOR)
		self.path_label.pack(side="left", padx=(0, 12))
		ctk.CTkButton(self, text="Seleccionar archivo", command=self.select_file, width=160, fg_color=PRIMARY_COLOR, hover_color=PRIMARY_HOVER_COLOR, text_color=TEXT_COLOR).pack(side="right")

	def select_file(self):
		selected = filedialog.askopenfilename(
			title="Selecciona el archivo de la ponchadora",
			filetypes=[("Excel y CSV", "*.csv *.xlsx *.xls"), ("Todos los archivos", "*.*")],
		)
		if selected:
			self.selected_path = Path(selected)
			self.path_label.configure(text=self.selected_path.name, text_color=TEXT_COLOR)
			self.on_file_selected(self.selected_path)
