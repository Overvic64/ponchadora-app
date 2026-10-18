"""Pantalla 'Reportes': F01, F02 y F05 con datos reales.

`generar_quincena()` en report_data.py consulta `reporte_asistencias` +
`incidencias` en Supabase para la quincena elegida.
"""
from __future__ import annotations

import os

import pandas as pd
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
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

from exportar_excel import _par, corte_entrada, excel_disponible, exportar_f01, exportar_f02, exportar_f05
from report_data import etiqueta_quincena, generar_quincena, quincenas_disponibles, resumen_concentrado
from store import store
from iconos import con_icono, etiqueta_icono, icono
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
        icon = etiqueta_icono("archivo", 18, COLORS["text_secondary"])
        label = QLabel(nombre)
        label.setWordWrap(True)
        label.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 11px; font-weight: 600; background: transparent;"
        )
        layout.addWidget(icon)
        layout.addWidget(label)
        self.set_active(False)

    def mousePressEvent(self, event):
        self.on_click(self.clave)
        super().mousePressEvent(event)

    def set_active(self, active: bool):
        if active:
            self.setStyleSheet(
                f"#statCard {{ background-color: {COLORS['card_bg']}; border: 1px solid {COLORS['accent']}; border-radius: 10px; }}"
            )
        else:
            self.setStyleSheet(
                f"#statCard {{ background-color: {COLORS['card_bg']}; border: 1px solid {COLORS['border']}; border-radius: 10px; }}"
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

        self.quincena_label = QLabel("")
        self.quincena_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        header_row.addWidget(self.quincena_label)

        # Lista desplegable con todas las quincenas (la mas reciente arriba): un clic en vez de ir de una en una.
        self.quincena_combo = QComboBox()
        self.quincena_combo.setFixedWidth(300)
        self.quincena_combo.setMaxVisibleItems(14)
        self.quincena_combo.setIconSize(QSize(16, 16))
        self.quincena_combo.currentIndexChanged.connect(self._on_quincena_elegida)
        header_row.addWidget(self.quincena_combo)

        self.export_btn = con_icono(QPushButton("Exportar a Excel"), "exportar")
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

    def _cargar_quincenas(self):
        """Llena el desplegable (mas reciente primero) conservando la quincena que estaba elegida."""
        previa = self._quincenas[self._quincena_idx] if 0 <= self._quincena_idx < len(self._quincenas) else None
        self._quincenas = quincenas_disponibles()
        if previa in self._quincenas:
            self._quincena_idx = self._quincenas.index(previa)
        else:
            self._quincena_idx = len(self._quincenas) - 1
        calendario = icono("calendario")
        self.quincena_combo.blockSignals(True)
        self.quincena_combo.clear()
        for anio, mes, mitad in reversed(self._quincenas):
            self.quincena_combo.addItem(calendario, f"Quincena {etiqueta_quincena(anio, mes, mitad)}")
        if self._quincenas:
            self.quincena_combo.setCurrentIndex(len(self._quincenas) - 1 - self._quincena_idx)
        self.quincena_combo.blockSignals(False)
        self.quincena_combo.setEnabled(bool(self._quincenas))

    def _on_quincena_elegida(self, indice):
        if 0 <= indice < len(self._quincenas):
            self._quincena_idx = len(self._quincenas) - 1 - indice
            self._mostrar_quincena()

    def refresh(self):
        self._cargar_quincenas()
        self._mostrar_quincena()

    def _mostrar_quincena(self):
        if not self._quincenas:
            self.quincena_label.setText("Sin asistencias importadas todavía")
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            return
        anio, mes, mitad = self._quincenas[self._quincena_idx]

        clave = self.active_report
        datos = REPORTES[clave]
        maestros = store.maestros_por_tipo(datos["tipos"])

        dias, celdas_por_maestro = generar_quincena(maestros, anio, mes, mitad)
        self._datos_quincena = (maestros, dias, celdas_por_maestro)
        self.quincena_label.setText(f"{len(dias)} días hábiles")

        if datos["modo"] == "control":
            self._render_control(maestros, dias, celdas_por_maestro)
        else:
            self._render_concentrado(maestros, celdas_por_maestro)

    def _render_control(self, maestros, dias, celdas_por_maestro):
        headers = ["Nombre"]
        for dia in dias:
            headers.append(f"{dia.day:02d}-E")
            headers.append(f"{dia.day:02d}-S")

        self.table.clearSpans()
        self.table.clearContents()
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(maestros))
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for col in range(1, len(headers)):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.Fixed)
            self.table.setColumnWidth(col, 48)

        corte = corte_entrada()
        self.table.verticalHeader().setDefaultSectionSize(40)
        for row, maestro in enumerate(maestros):
            self.table.setItem(row, 0, QTableWidgetItem(maestro.nombre))
            celdas = celdas_por_maestro.get(maestro.id, [])
            for day_index, celda in enumerate(celdas):
                col_entrada = 1 + day_index * 2
                col_salida = col_entrada + 1
                # Igual que el Excel: solo minutos de retardo y claves (FI, FIE, FIS, P, C, I...), sin horas.
                entrada, salida, unido = _par(celda, corte)
                if celda["tipo"] in ("sin_datos", "no_aplica"):
                    # Nadie tiene ponchada ese dia: no se ha importado ese periodo todavia.
                    entrada, color = "—", COLORS["text_muted"]
                elif celda["tipo"] == "completo":
                    color = COLORS["orange"]
                elif celda["tipo"] == "incidencia":
                    color = COLORS["blue"]
                else:
                    color = COLORS["red"]
                entrada_item = QTableWidgetItem(entrada)
                salida_item = QTableWidgetItem(salida)
                for item in (entrada_item, salida_item):
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setForeground(QColor(color))
                    if item.text() not in ("", "—"):
                        font = QFont()
                        font.setBold(True)
                        item.setFont(font)
                self.table.setItem(row, col_entrada, entrada_item)
                self.table.setItem(row, col_salida, salida_item)
                if unido:
                    self.table.setSpan(row, col_entrada, 1, 2)
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
        if excel_disponible():
            self._exportar_formato_oficial(path, anio, mes, mitad)
            return
        QMessageBox.information(
            self,
            "Excel no encontrado",
            "No se encontró Microsoft Excel en esta computadora, así que el reporte se guardará en una versión "
            "simple (sin el formato oficial). Para el formato oficial, exporta desde una PC con Excel.",
        )
        self._exportar_simple(path, anio, mes, mitad)

    def _exportar_formato_oficial(self, path, anio, mes, mitad):
        """Llena el formato oficial (plantillas/F01, F02 o F05) con los datos de la quincena."""
        maestros, dias, celdas_por_maestro = self._datos_quincena
        # Personal dado de baja solo sale si tuvo ponchadas o incidencias en la quincena.
        maestros = [
            m for m in maestros
            if m.activo or any(c["tipo"] in ("completo", "incompleto", "incidencia") for c in celdas_por_maestro.get(m.id, []))
        ]
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            if self.active_report == "F01":
                exportar_f01(path, maestros, dias, celdas_por_maestro, anio, mes, mitad)
            elif self.active_report == "F02":
                exportar_f02(path, maestros, dias, celdas_por_maestro, anio, mes, mitad)
            else:
                exportar_f05(path, maestros, celdas_por_maestro, anio, mes, mitad)
        except Exception as error:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(
                self,
                "Error al exportar",
                f"{error}\n\nSi el archivo ya está abierto en Excel, ciérralo e inténtalo de nuevo.",
            )
            return
        QApplication.restoreOverrideCursor()
        abrir = QMessageBox.question(self, "Exportado", f"Reporte guardado en:\n{path}\n\n¿Abrirlo ahora?")
        if abrir == QMessageBox.Yes:
            os.startfile(path)  # noqa: S606 - abre el archivo con Excel

    def _exportar_simple(self, path, anio, mes, mitad):
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
        self.table.clearSpans()
        self.table.clearContents()
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
