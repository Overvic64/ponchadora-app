"""Paleta de colores compartida por toda la aplicacion.

Estilo claro y aireado: fondos casi blancos, un solo azul de marca y grises azulados.
El color de datos solo aparece donde significa algo (retardo = ambar, falta = rojo) y en etiquetas suaves.
"""

COLORS = {
    # Estructura
    "page_bg": "#f5f7fb",
    "card_bg": "#ffffff",
    "border": "#e5eaf2",
    "border_strong": "#cfd8e6",
    "hover": "#eef2f8",
    "text_primary": "#111827",
    "text_secondary": "#5b6577",
    "text_muted": "#6b7688",
    # Marca y acciones
    "primary": "#1f6feb",
    "primary_hover": "#1858c4",
    "accent": "#1f6feb",
    "accent_soft": "#e3eefe",
    # Barra lateral y superior
    "sidebar_bg": "#f0f4fa",
    "sidebar_bg_hover": "#e6edf7",
    "sidebar_active": "#dbe7fa",
    "sidebar_text": "#374151",
    "sidebar_text_active": "#1f6feb",
    "topbar_bg": "#ffffff",
    # Datos (cada uno con su fondo suave)
    "blue": "#1f6feb",
    "blue_bg": "#e3eefe",
    "orange": "#c77c0a",
    "orange_bg": "#fdf1d8",
    "red": "#d64545",
    "red_bg": "#fde8e8",
    "green": "#1e8e57",
    "green_bg": "#dff5e8",
    "purple": "#6b4fc4",
    "purple_bg": "#ece7fa",
}

# Tono -> (color del icono/valor, fondo suave)
TONOS = {
    "neutral": (COLORS["text_secondary"], COLORS["hover"]),
    "blue": (COLORS["blue"], COLORS["blue_bg"]),
    "orange": (COLORS["orange"], COLORS["orange_bg"]),
    "red": (COLORS["red"], COLORS["red_bg"]),
    "green": (COLORS["green"], COLORS["green_bg"]),
    "purple": (COLORS["purple"], COLORS["purple_bg"]),
}
