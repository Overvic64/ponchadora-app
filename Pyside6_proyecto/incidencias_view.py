"""Pantalla 'Incidencias': captura manual de permisos, comisiones, incapacidades, etc.

Esto es justo lo que la vista `reporte_asistencias` de Supabase NO puede saber
por si sola (nadie poncha un permiso). Lo capturado aqui se combina despues
con esa vista para resolver la clave final de cada dia en los reportes
F01/F02/F05 (ver conversacion sobre la tabla `incidencias`).
"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from store import TIPOS_INCIDENCIA, store
from theme import COLORS
from widgets import size_table_to_contents


class IncidenciasView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Incidencias")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 18px; font-weight: 700;")
        subtitle = QLabel(
            "Registra permisos, comisiones, incapacidades y atenciones médicas — las faltas y retardos se calculan solos."
        )
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        form_card = QFrame()
        form_card.setObjectName("statCard")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(18, 16, 18, 16)
        form_layout.setSpacing(12)

        form_title = QLabel("➕  Nueva incidencia")
        form_title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px; font-weight: 700;")
        form_layout.addWidget(form_title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)

        self.maestro_combo = QComboBox()
        self._reload_maestros()

        self.tipo_combo = QComboBox()
        for clave, nombre in TIPOS_INCIDENCIA.items():
            self.tipo_combo.addItem(f"{clave} — {nombre}", clave)

        self.fecha_inicio = QDateEdit(QDate.currentDate())
        self.fecha_inicio.setCalendarPopup(True)
        self.fecha_fin = QDateEdit(QDate.currentDate())
        self.fecha_fin.setCalendarPopup(True)

        self.observaciones = QLineEdit()
        self.observaciones.setPlaceholderText("Observaciones (opcional)")

        grid.addWidget(self._label("Empleado"), 0, 0)
        grid.addWidget(self.maestro_combo, 1, 0)
        grid.addWidget(self._label("Tipo de incidencia"), 0, 1)
        grid.addWidget(self.tipo_combo, 1, 1)
        grid.addWidget(self._label("Fecha inicio"), 0, 2)
        grid.addWidget(self.fecha_inicio, 1, 2)
        grid.addWidget(self._label("Fecha fin"), 0, 3)
        grid.addWidget(self.fecha_fin, 1, 3)
        grid.addWidget(self._label("Observaciones"), 2, 0, 1, 4)
        grid.addWidget(self.observaciones, 3, 0, 1, 4)
        form_layout.addLayout(grid)

        save_row = QHBoxLayout()
        save_row.addStretch()
        save_btn = QPushButton("💾  Guardar incidencia")
        save_btn.setObjectName("primaryButton")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self._guardar)
        save_row.addWidget(save_btn)
        form_layout.addLayout(save_row)

        layout.addWidget(form_card)

        list_card = QFrame()
        list_card.setObjectName("statCard")
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(18, 16, 18, 16)
        list_layout.setSpacing(10)

        list_title = QLabel("📋  Incidencias registradas")
        list_title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px; font-weight: 700;")
        list_layout.addWidget(list_title)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Empleado", "Tipo", "Desde", "Hasta", "Observaciones", ""])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(34)
        list_layout.addWidget(self.table)

        layout.addWidget(list_card)
        layout.addStretch()

        self._refresh_table()

    @staticmethod
    def _label(text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px; font-weight: 600;")
        return lbl

    def _reload_maestros(self):
        self.maestro_combo.clear()
        for maestro in store.maestros:
            self.maestro_combo.addItem(f"{maestro.nombre} ({maestro.edificio})", maestro.id)

    def _guardar(self):
        if self.maestro_combo.count() == 0:
            QMessageBox.warning(self, "Sin empleados", "No hay empleados registrados todavía.")
            return
        maestro_id = self.maestro_combo.currentData()
        fecha_inicio = self.fecha_inicio.date().toPython()
        fecha_fin = self.fecha_fin.date().toPython()
        if fecha_fin < fecha_inicio:
            QMessageBox.warning(self, "Fechas inválidas", "La fecha fin no puede ser anterior a la fecha inicio.")
            return

        store.add_incidencia(
            maestro_id=maestro_id,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            tipo=self.tipo_combo.currentData(),
            observaciones=self.observaciones.text().strip(),
        )
        self.observaciones.clear()
        self._refresh_table()

    def _refresh_table(self):
        maestros_by_id = {m.id: m for m in store.maestros}
        self.table.setRowCount(len(store.incidencias))
        for row, incidencia in enumerate(store.incidencias):
            maestro = maestros_by_id.get(incidencia.maestro_id)
            nombre = maestro.nombre if maestro else "(empleado eliminado)"
            tipo_label = f"{incidencia.tipo} — {TIPOS_INCIDENCIA.get(incidencia.tipo, '')}"
            values = [
                nombre,
                tipo_label,
                incidencia.fecha_inicio.strftime("%Y-%m-%d"),
                incidencia.fecha_fin.strftime("%Y-%m-%d"),
                incidencia.observaciones,
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))

            delete_btn = QPushButton("🗑")
            delete_btn.setCursor(Qt.PointingHandCursor)
            delete_btn.setFixedWidth(32)
            delete_btn.clicked.connect(lambda _, inc_id=incidencia.id: self._eliminar(inc_id))
            self.table.setCellWidget(row, 5, delete_btn)
        size_table_to_contents(self.table)

    def _eliminar(self, incidencia_id):
        store.remove_incidencia(incidencia_id)
        self._refresh_table()

    def refresh(self):
        self._reload_maestros()
        self._refresh_table()
