"""Pantalla generica de personas (maestros): se reutiliza para 'Profesores'
(PTC + Asignatura) y 'Administrativos' (Administrativo), filtrando por tipo.

Los empleados que todavia no tienen tipo aparecen en ambas pantallas,
marcados como "Sin clasificar", para que se les pueda asignar desde aqui.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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

import clasificador
from iconos import con_icono, icono
from store import EDIFICIOS, TIPOS_PERSONAL, TURNOS, store
from theme import COLORS
from widgets import SectionTitle, size_table_to_contents

SIN_TURNO = "Sin turno"
SIN_TIPO = "Sin clasificar"


class EditarPersonaDialog(QDialog):
    def __init__(self, persona, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Editar — {persona.nombre}")
        self.setMinimumWidth(420)

        self.nombre_input = QLineEdit(persona.nombre)
        self.codigo_input = QLineEdit(persona.codigo or "")

        self.tipo_combo = QComboBox()
        self.tipo_combo.addItem(SIN_TIPO)
        self.tipo_combo.addItems(TIPOS_PERSONAL)
        self.tipo_combo.setCurrentText(persona.tipo_personal or SIN_TIPO)

        self.edificio_combo = QComboBox()
        self.edificio_combo.addItems(EDIFICIOS)
        self.edificio_combo.setCurrentText(persona.edificio)

        self.area_input = QLineEdit(persona.area_carrera or "")
        self.area_input.setPlaceholderText("Área / Dirección / Carrera")

        self.turno_combo = QComboBox()
        self.turno_combo.addItem(SIN_TURNO)
        self.turno_combo.addItems([t.capitalize() for t in TURNOS.keys()])
        self.turno_combo.setCurrentText(persona.turno.capitalize() if persona.turno else SIN_TURNO)

        self.activo_check = QCheckBox("Sigue trabajando aquí (si lo desmarcas, deja de contar faltas)")
        self.activo_check.setChecked(persona.activo)

        form = QFormLayout()
        form.addRow("Nombre", self.nombre_input)
        form.addRow("Código del lector", self.codigo_input)
        form.addRow("Tipo de personal", self.tipo_combo)
        form.addRow("Edificio asignado", self.edificio_combo)
        form.addRow("Área / Carrera", self.area_input)
        form.addRow("Turno", self.turno_combo)
        form.addRow("Activo", self.activo_check)

        botones = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        botones.accepted.connect(self._validar)
        botones.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(botones)

    def _validar(self):
        if not self.nombre_input.text().strip() or not self.codigo_input.text().strip():
            QMessageBox.warning(self, "Datos incompletos", "El nombre y el código no pueden quedar vacíos.")
            return
        self.accept()

    def valores(self) -> dict:
        tipo = self.tipo_combo.currentText()
        turno = self.turno_combo.currentText()
        return {
            "nombre": self.nombre_input.text().strip(),
            "codigo": self.codigo_input.text().strip(),
            "tipo_personal": None if tipo == SIN_TIPO else tipo,
            "edificio": self.edificio_combo.currentText(),
            "area_carrera": self.area_input.text().strip() or None,
            "turno": None if turno == SIN_TURNO else turno.lower(),
            "turno_confirmado": turno != SIN_TURNO,
            "activo": self.activo_check.isChecked(),
        }


class PersonasView(QWidget):
    def __init__(self, titulo: str, tipos_permitidos: list[str], parent=None):
        super().__init__(parent)
        self.titulo = titulo
        self.tipos_permitidos = tipos_permitidos

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        subtitle = QLabel(f"Tipos incluidos: {', '.join(tipos_permitidos)}")
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        layout.addWidget(subtitle)

        form_card = QFrame()
        form_card.setObjectName("statCard")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(18, 16, 18, 16)
        form_layout.setSpacing(12)

        form_layout.addWidget(SectionTitle("agregar", "Agregar"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)

        self.nombre_input = QLineEdit()
        self.nombre_input.setPlaceholderText("Nombre completo")
        self.codigo_input = QLineEdit()
        self.codigo_input.setPlaceholderText("Código (opcional)")

        self.tipo_combo = QComboBox()
        self.tipo_combo.addItems(tipos_permitidos)

        self.edificio_combo = QComboBox()
        self.edificio_combo.addItems(EDIFICIOS)

        self.area_input = QLineEdit()
        self.area_input.setPlaceholderText("Área / Dirección / Carrera")

        self.turno_combo = QComboBox()
        self.turno_combo.addItems([t.capitalize() for t in TURNOS.keys()])

        grid.addWidget(self._label("Nombre"), 0, 0)
        grid.addWidget(self.nombre_input, 1, 0)
        grid.addWidget(self._label("Código"), 0, 1)
        grid.addWidget(self.codigo_input, 1, 1)
        grid.addWidget(self._label("Tipo"), 0, 2)
        grid.addWidget(self.tipo_combo, 1, 2)
        grid.addWidget(self._label("Edificio asignado"), 2, 0)
        grid.addWidget(self.edificio_combo, 3, 0)
        grid.addWidget(self._label("Área / Carrera"), 2, 1)
        grid.addWidget(self.area_input, 3, 1)
        grid.addWidget(self._label("Turno"), 2, 2)
        grid.addWidget(self.turno_combo, 3, 2)
        form_layout.addLayout(grid)

        save_row = QHBoxLayout()
        save_row.addStretch()
        save_btn = con_icono(QPushButton("Guardar"), "guardar", "#ffffff")
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

        list_header = QHBoxLayout()
        list_header.addWidget(SectionTitle("personas", f"{titulo} registrados"))
        list_header.addStretch()

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Buscar por nombre o código")
        self.search_box.addAction(icono("buscar"), QLineEdit.LeadingPosition)
        self.search_box.setFixedWidth(240)
        self.search_box.textChanged.connect(lambda _: self.refresh())
        list_header.addWidget(self.search_box)

        self.filtro_combo = QComboBox()
        self.filtro_combo.addItems(["Todos", "Solo sin clasificar"])
        self.filtro_combo.currentIndexChanged.connect(lambda _: self.refresh())
        list_header.addWidget(self.filtro_combo)

        auto_btn = con_icono(QPushButton("Clasificar automáticamente"), "clasificar")
        auto_btn.setObjectName("secondaryButton")
        auto_btn.setCursor(Qt.PointingHandCursor)
        auto_btn.setToolTip("Deduce tipo, turno y área de quien no los tenga, con sus ponchadas y su edificio")
        auto_btn.clicked.connect(self._clasificar_automaticamente)
        list_header.addWidget(auto_btn)
        list_layout.addLayout(list_header)

        self.pendientes_label = QLabel("")
        self.pendientes_label.setStyleSheet(f"color: {COLORS['orange']}; font-size: 11px; font-weight: 600;")
        self.pendientes_label.setWordWrap(True)
        list_layout.addWidget(self.pendientes_label)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Nombre", "Código", "Tipo", "Edificio", "Área / Carrera", "Turno", "", ""]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        for col, width in ((6, 76), (7, 44)):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.Fixed)
            self.table.setColumnWidth(col, width)
        self.table.verticalHeader().setDefaultSectionSize(34)
        list_layout.addWidget(self.table)

        layout.addWidget(list_card)
        layout.addStretch()

        self.refresh()

    @staticmethod
    def _label(text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px; font-weight: 600;")
        return lbl

    def _guardar(self):
        nombre = self.nombre_input.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Falta el nombre", "Escribe el nombre completo del empleado.")
            return
        try:
            store.add_maestro(
                codigo=self.codigo_input.text().strip(),
                nombre=nombre,
                tipo_personal=self.tipo_combo.currentText(),
                edificio=self.edificio_combo.currentText(),
                area_carrera=self.area_input.text().strip() or "General",
                turno=self.turno_combo.currentText().lower(),
            )
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(self, "Error al guardar", str(error))
            return
        self.nombre_input.clear()
        self.codigo_input.clear()
        self.area_input.clear()
        self.refresh()

    def _clasificar_automaticamente(self):
        """Llena tipo, turno y area de quien no los tenga (nunca pisa lo ya capturado)."""
        faltantes = [m for m in store.maestros if not m.tipo_personal or not m.turno or not m.area_carrera]
        if not faltantes:
            QMessageBox.information(self, "Todo clasificado", "Todo el personal ya tiene tipo, turno y área.")
            return
        confirm = QMessageBox.question(
            self,
            "Clasificar automáticamente",
            f"{len(faltantes)} persona(s) tienen algo en blanco (tipo, turno o área).\n\n"
            "Se deducen de sus ponchadas y su edificio; lo que ya esté capturado no se toca. "
            "Antes de guardar se hace un respaldo en la carpeta 'respaldos'.\n\n¿Continuar?",
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            propuestas, respaldo = clasificador.clasificar_pendientes(faltantes)
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo clasificar", str(error))
            return
        self.refresh()
        extra = f"\n\nRespaldo previo: {respaldo.name}" if respaldo else ""
        QMessageBox.information(self, "Clasificación terminada", f"{clasificador.resumen(propuestas)}.{extra}")

    def _eliminar(self, maestro_id):
        confirm = QMessageBox.question(
            self, "Eliminar", "¿Eliminar este registro? Esta acción no se puede deshacer."
        )
        if confirm == QMessageBox.Yes:
            try:
                store.remove_maestro(maestro_id)
            except Exception as error:  # noqa: BLE001 - ej. tiene incidencias/asistencias asociadas
                QMessageBox.critical(self, "No se pudo eliminar", str(error))
                return
            self.refresh()

    def _editar(self, maestro_id):
        persona = next((m for m in store.maestros if m.id == maestro_id), None)
        if persona is None:
            return
        dialog = EditarPersonaDialog(persona, self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            store.update_maestro(maestro_id, **dialog.valores())
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(self, "Error al guardar", str(error))
            return
        self.refresh()

    def refresh(self):
        sin_clasificar = [m for m in store.maestros if not m.tipo_personal]
        personas = store.maestros_por_tipo(self.tipos_permitidos) + sin_clasificar
        if self.filtro_combo.currentText() == "Solo sin clasificar":
            personas = sin_clasificar
        busqueda = self.search_box.text().strip().lower()
        if busqueda:
            personas = [p for p in personas if busqueda in p.nombre.lower() or busqueda in (p.codigo or "").lower()]
        personas.sort(key=lambda p: (p.tipo_personal is not None, p.nombre.lower()))

        if sin_clasificar:
            self.pendientes_label.setText(
                f"{len(sin_clasificar)} empleado(s) sin tipo de personal. Aparecen aquí y en la otra "
                "pantalla de personal hasta que los clasifiques con \"Editar\" o con \"Clasificar automáticamente\"."
            )
        self.pendientes_label.setVisible(bool(sin_clasificar))

        self.table.setRowCount(len(personas))
        for row, persona in enumerate(personas):
            values = [
                persona.nombre,
                persona.codigo,
                persona.tipo_personal or SIN_TIPO,
                persona.edificio,
                persona.area_carrera or "-",
                persona.turno.capitalize() if persona.turno else "-",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 2 and not persona.tipo_personal:
                    item.setForeground(QColor(COLORS["orange"]))
                    font = QFont()
                    font.setBold(True)
                    item.setFont(font)
                self.table.setItem(row, col, item)

            edit_btn = QPushButton("Editar")
            edit_btn.setObjectName("tableButton")
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.setFixedWidth(64)
            edit_btn.setToolTip("Editar / clasificar")
            edit_btn.clicked.connect(lambda _, pid=persona.id: self._editar(pid))
            self.table.setCellWidget(row, 6, edit_btn)

            delete_btn = con_icono(QPushButton(), "eliminar")
            delete_btn.setObjectName("tableButton")
            delete_btn.setCursor(Qt.PointingHandCursor)
            delete_btn.setFixedSize(34, 28)
            delete_btn.setToolTip("Eliminar")
            delete_btn.clicked.connect(lambda _, pid=persona.id: self._eliminar(pid))
            self.table.setCellWidget(row, 7, delete_btn)
        size_table_to_contents(self.table)
