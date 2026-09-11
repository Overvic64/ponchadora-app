"""Pantalla 'Configuración': edificios (catálogo) y turnos (editable).

Los turnos se editan aquí en vez de en el SQL Editor de Supabase directamente
-- una vez conectada la base, "Guardar" hará el UPDATE a la tabla `turnos`
en lugar de mutar el diccionario local.
"""
from __future__ import annotations

from PySide6.QtCore import QTime, Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from store import EDIFICIOS, TURNOS
from theme import COLORS


class ConfiguracionView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Configuración")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 18px; font-weight: 700;")
        layout.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(16)
        row.addWidget(self._build_edificios_card(), 1)
        row.addWidget(self._build_turnos_card(), 2)
        layout.addLayout(row)
        layout.addStretch()

    def _build_edificios_card(self):
        card = QFrame()
        card.setObjectName("statCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(8)

        title = QLabel("🏢  Edificios")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px; font-weight: 700;")
        card_layout.addWidget(title)

        hint = QLabel("Catálogo fijo (se administra en Supabase).")
        hint.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px; font-style: italic;")
        card_layout.addWidget(hint)

        for edificio in EDIFICIOS:
            lbl = QLabel(f"•  {edificio}")
            lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px; padding: 3px 0;")
            card_layout.addWidget(lbl)

        card_layout.addStretch()
        return card

    def _build_turnos_card(self):
        card = QFrame()
        card.setObjectName("statCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(10)

        title = QLabel("⏰  Turnos")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px; font-weight: 700;")
        card_layout.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)

        headers = ["Turno", "Hora entrada", "Hora salida", "Tolerancia (min)", ""]
        for col, header in enumerate(headers):
            lbl = QLabel(header)
            lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px; font-weight: 700;")
            grid.addWidget(lbl, 0, col)

        self._rows = {}
        for row_index, (turno_id, datos) in enumerate(TURNOS.items(), start=1):
            nombre_lbl = QLabel(turno_id.capitalize())
            nombre_lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px; font-weight: 600;")

            entrada_edit = QTimeEdit(QTime.fromString(datos["hora_entrada"], "HH:mm"))
            salida_edit = QTimeEdit(QTime.fromString(datos["hora_salida"], "HH:mm"))
            tolerancia_spin = QSpinBox()
            tolerancia_spin.setRange(0, 60)
            tolerancia_spin.setValue(datos["tolerancia_minutos"])

            save_btn = QPushButton("Guardar")
            save_btn.setObjectName("secondaryButton")
            save_btn.setCursor(Qt.PointingHandCursor)
            save_btn.clicked.connect(
                lambda _, tid=turno_id, e=entrada_edit, s=salida_edit, t=tolerancia_spin: self._guardar_turno(tid, e, s, t)
            )

            grid.addWidget(nombre_lbl, row_index, 0)
            grid.addWidget(entrada_edit, row_index, 1)
            grid.addWidget(salida_edit, row_index, 2)
            grid.addWidget(tolerancia_spin, row_index, 3)
            grid.addWidget(save_btn, row_index, 4)

        card_layout.addLayout(grid)
        card_layout.addStretch()
        return card

    def _guardar_turno(self, turno_id, entrada_edit, salida_edit, tolerancia_spin):
        TURNOS[turno_id]["hora_entrada"] = entrada_edit.time().toString("HH:mm")
        TURNOS[turno_id]["hora_salida"] = salida_edit.time().toString("HH:mm")
        TURNOS[turno_id]["tolerancia_minutos"] = tolerancia_spin.value()
        QMessageBox.information(
            self, "Guardado",
            f"Turno '{turno_id}' actualizado (por ahora solo en esta sesión; falta conectar a Supabase)."
        )
