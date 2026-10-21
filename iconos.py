"""Iconos de la aplicacion (Phosphor, trazo fino) a traves de qtawesome.

Las pantallas piden un nombre logico ("importar", "buscar"...) y aqui se decide que icono
es; asi cambiar uno es tocar solo este archivo.
"""
from __future__ import annotations

import qtawesome as qta
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QLabel, QPushButton

from theme import COLORS

NOMBRES = {
    # Navegacion
    "inicio": "house",
    "importar": "upload-simple",
    "limpieza": "eraser",
    "asistencias": "calendar-check",
    "incidencias": "warning-circle",
    "reportes": "chart-bar",
    "profesores": "chalkboard-teacher",
    "administrativos": "identification-badge",
    "configuracion": "gear-six",
    # Marca y usuario
    "logo": "graduation-cap",
    "usuario": "user",
    # Acciones
    "buscar": "magnifying-glass",
    "guardar": "floppy-disk",
    "agregar": "plus",
    "eliminar": "trash-simple",
    "exportar": "download-simple",
    "subir": "upload-simple",
    "nube": "cloud-arrow-up",
    "clasificar": "magic-wand",
    "editar": "pencil-simple",
    "siguiente": "caret-right",
    "anterior": "caret-left",
    # Contenido
    "calendario": "calendar-blank",
    "reloj": "clock",
    "personas": "users",
    "persona": "user",
    "edificios": "buildings",
    "archivo": "file-text",
    "archivos": "files",
    "grafica": "chart-line-up",
    "turno": "arrows-left-right",
    "lista": "list-bullets",
    # Estados
    "ok": "check-circle",
    "falta": "x-circle",
    "aviso": "warning",
    "hecho": "check",
    "retardo": "timer",
    "permiso": "file-text",
    "pendiente": "hourglass",
    "sube": "arrow-up-right",
    "baja": "arrow-down-right",
}


def icono(nombre: str, color: str | None = None, color_activo: str | None = None) -> QIcon:
    """QIcon de linea. `color` por omision es el gris de texto secundario."""
    base = color or COLORS["text_secondary"]
    return qta.icon(f"ph.{NOMBRES.get(nombre, nombre)}", color=base, color_active=color_activo or base)


def etiqueta_icono(nombre: str, tamano: int = 18, color: str | None = None) -> QLabel:
    """QLabel que solo muestra un icono (para titulos de tarjeta, insignias, etc.)."""
    label = QLabel()
    label.setPixmap(icono(nombre, color).pixmap(tamano, tamano))
    label.setFixedSize(tamano, tamano)
    label.setAlignment(Qt.AlignCenter)
    label.setStyleSheet("background: transparent; border: none;")
    return label


def con_icono(boton: QPushButton, nombre: str, color: str | None = None, tamano: int = 16) -> QPushButton:
    """Pone icono (y su tamaño) a un boton y lo regresa."""
    boton.setIcon(icono(nombre, color))
    boton.setIconSize(QSize(tamano, tamano))
    return boton
