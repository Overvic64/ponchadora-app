"""Pantalla 'Configuración': edificios (catálogo) y turnos (editable).

Los turnos se editan aquí en vez de en el SQL Editor de Supabase directamente
-- una vez conectada la base, "Guardar" hará el UPDATE a la tabla `turnos`
en lugar de mutar el diccionario local.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTime
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

from iconos import con_icono, etiqueta_icono
from store import EDIFICIOS, TURNOS, store
from theme import COLORS
from widgets import SectionTitle


class ConfiguracionView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)


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

        card_layout.addWidget(SectionTitle("edificios", "Edificios"))

        hint = QLabel("Catálogo fijo (se administra en Supabase).")
        hint.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px;")
        card_layout.addWidget(hint)

        for edificio in EDIFICIOS:
            fila = QHBoxLayout()
            fila.setSpacing(10)
            fila.addWidget(etiqueta_icono("siguiente", 12, COLORS["text_muted"]))
            lbl = QLabel(edificio)
            lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px; padding: 3px 0;")
            fila.addWidget(lbl, 1)
            card_layout.addLayout(fila)

        card_layout.addStretch()
        return card

    def _build_turnos_card(self):
        card = QFrame()
        card.setObjectName("statCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(10)

        card_layout.addWidget(SectionTitle("reloj", "Turnos"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)

        headers = ["Turno", "Hora entrada", "Hora salida", "Tolerancia (min)", ""]
        for col, header in enumerate(headers):
            lbl = QLabel(header)
            lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; font-weight: 600;")
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

            save_btn = con_icono(QPushButton("Guardar"), "guardar")
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
        try:
            store.update_turno(
                turno_id,
                hora_entrada=entrada_edit.time().toString("HH:mm"),
                hora_salida=salida_edit.time().toString("HH:mm"),
                tolerancia_minutos=tolerancia_spin.value(),
            )
        except Exception as error:  # noqa: BLE001 - mostramos cualquier error al usuario
            QMessageBox.critical(self, "Error al guardar", str(error))
            return
        QMessageBox.information(self, "Guardado", f"Turno '{turno_id}' actualizado en Supabase.")
