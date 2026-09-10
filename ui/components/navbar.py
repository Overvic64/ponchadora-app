import customtkinter as ctk

from config.settings import ACCENT_COLOR, BG_COLOR, MUTED_TEXT_COLOR, PRIMARY_COLOR, SURFACE_COLOR, TEXT_COLOR


class NavigationBar(ctk.CTkFrame):
	def __init__(self, master, on_navigate, **kwargs):
		super().__init__(master, width=220, corner_radius=0, fg_color=SURFACE_COLOR, border_width=1, border_color="#D9E5DC", **kwargs)
		self.grid_propagate(False)
		ctk.CTkLabel(self, text="PONCHADORA", font=ctk.CTkFont(size=20, weight="bold"), text_color=PRIMARY_COLOR).pack(anchor="w", padx=24, pady=(34, 4))
		ctk.CTkLabel(self, text="CONTROL DE ASISTENCIA", font=ctk.CTkFont(size=10, weight="bold"), text_color=MUTED_TEXT_COLOR).pack(anchor="w", padx=24, pady=(0, 34))
		for label, view in (("Resumen", "home"), ("Resumen semanal", "weekly"), ("Procesar archivo", "attendance"), ("Historial", "reports")):
			ctk.CTkButton(self, text=label, anchor="w", fg_color="transparent", text_color=TEXT_COLOR, hover_color="#E2F1E6", command=lambda value=view: on_navigate(value)).pack(fill="x", padx=12, pady=3)
		ctk.CTkLabel(self, text="SQLite activo", text_color=ACCENT_COLOR, font=ctk.CTkFont(size=11)).pack(side="bottom", anchor="w", padx=24, pady=24)
