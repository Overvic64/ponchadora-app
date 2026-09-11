"""Pantalla 'Asistencias': explorador de registros con filtros.

Los datos que se muestran aqui son de ejemplo (generados localmente a partir
de los maestros del store). Cuando se conecte Supabase, esta pantalla debe
leer directo de la vista `reporte_asistencias`, que ya calcula edificio,
turno y retardo reales -- por eso esa logica no se duplica aqui.
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from store import EDIFICIOS, TIPOS_PERSONAL, TURNOS, store
from theme import COLORS
from widgets import size_table_to_contents


def _sample_rows():
    random.seed(7)
    rows = []
    today = date.today()
    for maestro in store.maestros:
        turno_ref = TURNOS[maestro.turno]
        base_hour, base_minute = (int(part) for part in turno_ref["hora_entrada"].split(":"))
        for offset in range(5):
            dia = today - timedelta(days=offset)
            retardo = random.choice([0, 0, 0, 4, 12, 18])
            entrada_minute = base_minute + retardo
            entrada_hour = base_hour + entrada_minute // 60
            entrada_minute = entrada_minute % 60
            entrada = f"{entrada_hour:02d}:{entrada_minute:02d}"
            salida_hour, salida_minute = (int(part) for part in turno_ref["hora_salida"].split(":"))
            salida = f"{salida_hour:02d}:{salida_minute:02d}"
            tolerancia = turno_ref["tolerancia_minutos"]
            retardo_final = max(0, retardo - tolerancia)
            rows.append(
                {
                    "fecha": dia.strftime("%Y-%m-%d"),
                    "nombre": maestro.nombre,
                    "edificio": maestro.edificio,
                    "tipo_personal": maestro.tipo_personal,
                    "turno": maestro.turno.capitalize(),
                    "entrada": entrada,
                    "salida": salida,
                    "retardo": retardo_final,
                }
            )
    rows.sort(key=lambda r: (r["fecha"], r["nombre"]), reverse=True)
    return rows


class AsistenciasView(QWidget):
    HEADERS = ["Fecha", "Empleado", "Edificio", "Tipo", "Turno", "Entrada", "Salida", "Retardo (min)"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = _sample_rows()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Asistencias")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 18px; font-weight: 700;")
        subtitle = QLabel(
            "Datos de ejemplo — al conectar Supabase, esta pantalla lee directo de la vista reporte_asistencias."
        )
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; font-style: italic;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        card = QFrame()
        card.setObjectName("statCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(10)

        filters_row = QHBoxLayout()
        filters_row.setSpacing(10)

        self.edificio_combo = QComboBox()
        self.edificio_combo.addItem("Todos los edificios")
        self.edificio_combo.addItems(EDIFICIOS)
        self.edificio_combo.currentIndexChanged.connect(self._apply_filters)

        self.tipo_combo = QComboBox()
        self.tipo_combo.addItem("Todos los tipos")
        self.tipo_combo.addItems(TIPOS_PERSONAL)
        self.tipo_combo.currentIndexChanged.connect(self._apply_filters)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍  Buscar empleado...")
        self.search_box.setObjectName("searchBoxLight")
        self.search_box.textChanged.connect(self._apply_filters)

        filters_row.addWidget(self.edificio_combo)
        filters_row.addWidget(self.tipo_combo)
        filters_row.addWidget(self.search_box, 1)
        card_layout.addLayout(filters_row)

        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(34)
        card_layout.addWidget(self.table)

        layout.addWidget(card)
        layout.addStretch()

        self._apply_filters()

    def refresh(self):
        self._rows = _sample_rows()
        self._apply_filters()

    def _apply_filters(self):
        edificio = self.edificio_combo.currentText()
        tipo = self.tipo_combo.currentText()
        search = self.search_box.text().strip().lower()

        filtered = [
            row
            for row in self._rows
            if (edificio == "Todos los edificios" or row["edificio"] == edificio)
            and (tipo == "Todos los tipos" or row["tipo_personal"] == tipo)
            and (search in row["nombre"].lower())
        ]

        self.table.setRowCount(len(filtered))
        for row_index, row in enumerate(filtered):
            values = [
                row["fecha"],
                row["nombre"],
                row["edificio"],
                row["tipo_personal"],
                row["turno"],
                row["entrada"],
                row["salida"],
                str(row["retardo"]) if row["retardo"] else "-",
            ]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col_index == 7 and row["retardo"]:
                    item.setForeground(QColor(COLORS["orange"]))
                    font = QFont()
                    font.setBold(True)
                    item.setFont(font)
                self.table.setItem(row_index, col_index, item)
        size_table_to_contents(self.table)
