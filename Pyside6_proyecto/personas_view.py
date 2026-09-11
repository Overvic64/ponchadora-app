"""Pantalla generica de personas (maestros): se reutiliza para 'Profesores'
(PTC + Asignatura) y 'Administrativos' (Administrativo), filtrando por tipo.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
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

from store import EDIFICIOS, TURNOS, store
from theme import COLORS
from widgets import size_table_to_contents


class PersonasView(QWidget):
    def __init__(self, titulo: str, tipos_permitidos: list[str], parent=None):
        super().__init__(parent)
        self.titulo = titulo
        self.tipos_permitidos = tipos_permitidos

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        title = QLabel(titulo)
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 18px; font-weight: 700;")
        subtitle = QLabel(f"Tipos incluidos: {', '.join(tipos_permitidos)}")
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        form_card = QFrame()
        form_card.setObjectName("statCard")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(18, 16, 18, 16)
        form_layout.setSpacing(12)

        form_title = QLabel("➕  Agregar")
        form_title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px; font-weight: 700;")
        form_layout.addWidget(form_title)

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
        save_btn = QPushButton("💾  Guardar")
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

        list_title = QLabel(f"👥  {titulo} registrados")
        list_title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px; font-weight: 700;")
        list_layout.addWidget(list_title)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Nombre", "Código", "Tipo", "Edificio", "Área / Carrera", "Turno", ""]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
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
        store.add_maestro(
            codigo=self.codigo_input.text().strip(),
            nombre=nombre,
            tipo_personal=self.tipo_combo.currentText(),
            edificio=self.edificio_combo.currentText(),
            area_carrera=self.area_input.text().strip() or "General",
            turno=self.turno_combo.currentText().lower(),
        )
        self.nombre_input.clear()
        self.codigo_input.clear()
        self.area_input.clear()
        self.refresh()

    def _eliminar(self, maestro_id):
        confirm = QMessageBox.question(
            self, "Eliminar", "¿Eliminar este registro? Esta acción no se puede deshacer."
        )
        if confirm == QMessageBox.Yes:
            store.remove_maestro(maestro_id)
            self.refresh()

    def refresh(self):
        personas = store.maestros_por_tipo(self.tipos_permitidos)
        self.table.setRowCount(len(personas))
        for row, persona in enumerate(personas):
            values = [
                persona.nombre,
                persona.codigo,
                persona.tipo_personal,
                persona.edificio,
                persona.area_carrera,
                persona.turno.capitalize(),
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))

            delete_btn = QPushButton("🗑")
            delete_btn.setCursor(Qt.PointingHandCursor)
            delete_btn.setFixedWidth(32)
            delete_btn.clicked.connect(lambda _, pid=persona.id: self._eliminar(pid))
            self.table.setCellWidget(row, 6, delete_btn)
        size_table_to_contents(self.table)
