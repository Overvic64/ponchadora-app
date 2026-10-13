"""Pantalla 'Reportes': F01, F02 y F05 con datos reales.

`generar_quincena()` en report_data.py consulta `reporte_asistencias` +
`incidencias` en Supabase para la quincena elegida.
"""
from __future__ import annotations

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from report_data import etiqueta_quincena, generar_quincena, quincenas_disponibles, resumen_concentrado
from store import store
from theme import COLORS
from widgets import size_table_to_contents

REPORTES = {
    "F01": {
        "nombre": "F01 — Control Quincenal Administrativos y PTC",
        "tipos": ["Administrativo", "Profesor de Tiempo Completo"],
        "modo": "control",
    },
    "F02": {
        "nombre": "F02 — Control Quincenal Profesor de Asignatura",
        "tipos": ["Profesor de Asignatura"],
        "modo": "control",
    },
    "F05": {
        "nombre": "F05 — Concentrado Incidencias Administrativo y PTC",
        "tipos": ["Administrativo", "Profesor de Tiempo Completo"],
        "modo": "concentrado",
    },
}


class ReportSelector(QFrame):
    def __init__(self, clave, nombre, on_click, parent=None):
        super().__init__(parent)
        self.clave = clave
        self.on_click = on_click
        self.setObjectName("statCard")
        self.setCursor(Qt.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        icon = QLabel("📄")
        icon.setStyleSheet("font-size: 18px;")
        label = QLabel(nombre)
        label.setWordWrap(True)
        label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 11px; font-weight: 700;")
        layout.addWidget(icon)
        layout.addWidget(label)
        self.set_active(False)

    def mousePressEvent(self, event):
        self.on_click(self.clave)
        super().mousePressEvent(event)

    def set_active(self, active: bool):
        if active:
            self.setStyleSheet(
                f"#statCard {{ background-color: {COLORS['card_bg']}; border: 2px solid {COLORS['blue']}; border-radius: 12px; }}"
            )
        else:
            self.setStyleSheet(
                f"#statCard {{ background-color: {COLORS['card_bg']}; border: 1px solid {COLORS['border']}; border-radius: 12px; }}"
            )


class ReportesView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_report = "F01"
        self._quincenas = quincenas_disponibles()
        self._quincena_idx = len(self._quincenas) - 1 if self._quincenas else 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Reportes")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 18px; font-weight: 700;")
        subtitle = QLabel(
            "Datos reales de Supabase (reporte_asistencias), combinados con lo que captures en Incidencias."
        )
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; font-style: italic;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        selectors_row = QHBoxLayout()
        selectors_row.setSpacing(12)
        self.selectors: dict[str, ReportSelector] = {}
        for clave, datos in REPORTES.items():
            selector = ReportSelector(clave, datos["nombre"], self._select_report)
            self.selectors[clave] = selector
            selectors_row.addWidget(selector)
        layout.addLayout(selectors_row)

        header_row = QHBoxLayout()
        self.report_title = QLabel("")
        self.report_title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 14px; font-weight: 700;")
        header_row.addWidget(self.report_title)
        header_row.addStretch()

        self.prev_btn = QPushButton("‹")
        self.prev_btn.setObjectName("secondaryButton")
        self.prev_btn.setFixedWidth(32)
        self.prev_btn.setCursor(Qt.PointingHandCursor)
        self.prev_btn.clicked.connect(self._quincena_anterior)
        header_row.addWidget(self.prev_btn)

        self.quincena_label = QLabel("")
        self.quincena_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        header_row.addWidget(self.quincena_label)

        self.next_btn = QPushButton("›")
        self.next_btn.setObjectName("secondaryButton")
        self.next_btn.setFixedWidth(32)
        self.next_btn.setCursor(Qt.PointingHandCursor)
        self.next_btn.clicked.connect(self._quincena_siguiente)
        header_row.addWidget(self.next_btn)

        self.export_btn = QPushButton("⬇  Exportar a Excel")
        self.export_btn.setObjectName("secondaryButton")
        self.export_btn.setCursor(Qt.PointingHandCursor)
        self.export_btn.clicked.connect(self._exportar)
        header_row.addWidget(self.export_btn)
        layout.addLayout(header_row)

        table_card = QFrame()
        table_card.setObjectName("statCard")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(12, 12, 12, 12)
        self.table = QTableWidget()
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        table_layout.addWidget(self.table)
        layout.addWidget(table_card, 1)

        self._select_report("F01")

    def _select_report(self, clave):
        self.active_report = clave
        for key, selector in self.selectors.items():
            selector.set_active(key == clave)
        self.report_title.setText(REPORTES[clave]["nombre"])
        self.refresh()

    def _quincena_anterior(self):
        if self._quincena_idx > 0:
            self._quincena_idx -= 1
            self.refresh()

    def _quincena_siguiente(self):
        if self._quincena_idx < len(self._quincenas) - 1:
            self._quincena_idx += 1
            self.refresh()

    def refresh(self):
        self._quincenas = quincenas_disponibles()
        if not self._quincenas:
            self.quincena_label.setText("Sin asistencias importadas todavía")
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            return
        self._quincena_idx = min(self._quincena_idx, len(self._quincenas) - 1)
        anio, mes, mitad = self._quincenas[self._quincena_idx]
        self.prev_btn.setEnabled(self._quincena_idx > 0)
        self.next_btn.setEnabled(self._quincena_idx < len(self._quincenas) - 1)

        clave = self.active_report
        datos = REPORTES[clave]
        maestros = store.maestros_por_tipo(datos["tipos"])

        dias, celdas_por_maestro = generar_quincena(maestros, anio, mes, mitad)
        self.quincena_label.setText(f"📅  {etiqueta_quincena(anio, mes, mitad)} — {len(dias)} días hábiles")

        if datos["modo"] == "control":
            self._render_control(maestros, dias, celdas_por_maestro)
        else:
            self._render_concentrado(maestros, celdas_por_maestro)

    def _render_control(self, maestros, dias, celdas_por_maestro):
        headers = ["Nombre"]
        for dia in dias:
            headers.append(f"{dia.day:02d}-E")
            headers.append(f"{dia.day:02d}-S")

        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(maestros))
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for col in range(1, len(headers)):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.Fixed)
            self.table.setColumnWidth(col, 48)

        for row, maestro in enumerate(maestros):
            self.table.setItem(row, 0, QTableWidgetItem(maestro.nombre))
            celdas = celdas_por_maestro.get(maestro.id, [])
            for day_index, celda in enumerate(celdas):
                col_entrada = 1 + day_index * 2
                col_salida = col_entrada + 1
                if celda["tipo"] == "completo":
                    entrada_item = QTableWidgetItem(celda["entrada"])
                    salida_item = QTableWidgetItem(celda["salida"])
                    if celda["retardo_min"] > 0:
                        font = QFont()
                        font.setBold(True)
                        entrada_item.setFont(font)
                        entrada_item.setForeground(QColor(COLORS["orange"]))
                elif celda["tipo"] in ("sin_datos", "no_aplica"):
                    # Nadie tiene ponchada ese dia: no se ha importado ese
                    # periodo todavia. Se muestra neutral, no como problema.
                    entrada_item = QTableWidgetItem("—")
                    salida_item = QTableWidgetItem("")
                    entrada_item.setForeground(QColor(COLORS["text_secondary"]))
                else:
                    clave = celda.get("clave", celda["tipo"])
                    entrada_item = QTableWidgetItem(clave)
                    salida_item = QTableWidgetItem("")
                    entrada_item.setForeground(QColor(COLORS["red"]))
                    font = QFont()
                    font.setBold(True)
                    entrada_item.setFont(font)
                entrada_item.setTextAlignment(Qt.AlignCenter)
                salida_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, col_entrada, entrada_item)
                self.table.setItem(row, col_salida, salida_item)
        size_table_to_contents(self.table)

    def _exportar(self):
        """Exporta la tabla tal como se ve (mismas columnas y claves)."""
        if self.table.rowCount() == 0:
            QMessageBox.information(self, "Sin datos", "No hay filas que exportar en este reporte.")
            return
        anio, mes, mitad = self._quincenas[self._quincena_idx]
        nombre = f"{self.active_report} {etiqueta_quincena(anio, mes, mitad)}.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "Exportar reporte", nombre, "Excel (*.xlsx)")
        if not path:
            return
        headers = [self.table.horizontalHeaderItem(c).text() for c in range(self.table.columnCount())]
        filas = [
            [(self.table.item(r, c).text() if self.table.item(r, c) else "") for c in range(self.table.columnCount())]
            for r in range(self.table.rowCount())
        ]
        try:
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                titulo = pd.DataFrame([[REPORTES[self.active_report]["nombre"]], [f"Quincena: {etiqueta_quincena(anio, mes, mitad)}"]])
                titulo.to_excel(writer, index=False, header=False, startrow=0)
                pd.DataFrame(filas, columns=headers).to_excel(writer, index=False, startrow=3)
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(self, "Error al exportar", str(error))
            return
        QMessageBox.information(self, "Exportado", f"Reporte guardado en:\n{path}")

    def _render_concentrado(self, maestros, celdas_por_maestro):
        headers = ["Nombre", "Área / Carrera", "Días", "Horas", "Minutos"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(maestros))
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

        for row, maestro in enumerate(maestros):
            celdas = celdas_por_maestro.get(maestro.id, [])
            resumen = resumen_concentrado(celdas)
            values = [
                maestro.nombre,
                maestro.area_carrera or "-",
                str(resumen["dias"]),
                str(resumen["horas"]),
                str(resumen["minutos"]),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col >= 2:
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, col, item)
        size_table_to_contents(self.table)
