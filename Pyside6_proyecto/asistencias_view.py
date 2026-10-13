"""Pantalla 'Asistencias': explorador de registros con filtros.

Lee directo de la vista `reporte_asistencias` en Supabase, que ya calcula
edificio, turno y retardo reales -- por eso esa logica no se duplica aqui.
tipo_personal no vive en la vista, asi que se completa cruzando con
store.maestros por maestro_id.
"""
from __future__ import annotations

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

from report_data import business_days, etiqueta_quincena, quincenas_disponibles
from store import EDIFICIOS, TIPOS_PERSONAL, store
from theme import COLORS
from widgets import size_table_to_contents

ESTADO_LABELS = {
    "completo": "Completo",
    "sin_entrada": "Sin entrada",
    "sin_salida": "Sin salida",
    "horas_iguales_por_revisar": "Ponchada única",
    "orden_por_revisar": "Orden por revisar",
}


def _load_rows(fecha_inicio=None, fecha_fin=None):
    maestros_by_id = {m.id: m for m in store.maestros}
    rows = []
    for r in store.reporte_asistencias(fecha_inicio, fecha_fin):
        maestro = maestros_by_id.get(r.get("maestro_id"))
        turno = r.get("turno_reporte") or r.get("turno_observado") or ""
        estado = r.get("estado") or "completo"
        rows.append(
            {
                "fecha": r.get("fecha") or "",
                "nombre": r.get("nombre") or "",
                "edificio": r.get("edificio_reporte") or "",
                "tipo_personal": maestro.tipo_personal if maestro else None,
                "turno": turno.capitalize() if turno else "-",
                "entrada": (r.get("entrada") or "-")[:5],
                "salida": (r.get("salida") or "-")[:5],
                "retardo": r.get("retardo_minutos_referencia") or 0,
                "estado": estado,
            }
        )
    rows.sort(key=lambda r: (r["fecha"], r["nombre"]), reverse=True)
    return rows


class AsistenciasView(QWidget):
    HEADERS = ["Fecha", "Empleado", "Edificio", "Tipo", "Turno", "Entrada", "Salida", "Retardo (min)", "Estado"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._quincena: tuple[int, int, str] | None = None
        self._rows: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Asistencias")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 18px; font-weight: 700;")
        subtitle = QLabel("Datos en vivo desde Supabase (vista reporte_asistencias).")
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; font-style: italic;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.quincena_label = QLabel("")
        self.quincena_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; font-weight: 600;")
        layout.addWidget(self.quincena_label)

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
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(34)
        card_layout.addWidget(self.table)

        layout.addWidget(card)
        layout.addStretch()

        self._reload_rows()

    def set_quincena(self, quincena: tuple[int, int, str]):
        self._quincena = quincena
        self._reload_rows()

    def refresh(self):
        self._reload_rows()

    def _reload_rows(self):
        quincenas = quincenas_disponibles()
        quincena = self._quincena if self._quincena in quincenas else (quincenas[-1] if quincenas else None)

        if quincena is None:
            self.quincena_label.setText("📅  Sin asistencias importadas todavía")
            self._rows = []
        else:
            anio, mes, mitad = quincena
            dias = business_days(anio, mes, mitad)
            fecha_inicio, fecha_fin = (dias[0], dias[-1]) if dias else (None, None)
            self.quincena_label.setText(f"📅  {etiqueta_quincena(anio, mes, mitad)}")
            self._rows = _load_rows(fecha_inicio, fecha_fin)

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
                row["tipo_personal"] or "-",
                row["turno"],
                row["entrada"],
                row["salida"],
                str(row["retardo"]) if row["retardo"] else "-",
                ESTADO_LABELS.get(row["estado"], row["estado"]),
            ]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col_index == 7 and row["retardo"]:
                    item.setForeground(QColor(COLORS["orange"]))
                    font = QFont()
                    font.setBold(True)
                    item.setFont(font)
                if col_index == 8 and row["estado"] != "completo":
                    item.setForeground(QColor(COLORS["orange"]))
                    font = QFont()
                    font.setBold(True)
                    item.setFont(font)
                    item.setToolTip(
                        "El lector no registró una ponchada completa ese día — revisar antes de "
                        "contarlo como retardo o falta."
                    )
                self.table.setItem(row_index, col_index, item)
        size_table_to_contents(self.table)
