"""Pantalla 'Limpieza de registros': historial de archivos importados y depurados."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from store import store
from theme import COLORS
from widgets import StatCard, size_table_to_contents


class LimpiezaView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Limpieza de registros")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 18px; font-weight: 700;")
        subtitle = QLabel("Historial de archivos importados en esta sesión y cuántos registros se conservaron.")
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.stats_row = QHBoxLayout()
        self.stats_row.setSpacing(16)
        layout.addLayout(self.stats_row)

        table_card = QFrame()
        table_card.setObjectName("statCard")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(18, 16, 18, 16)
        table_layout.setSpacing(10)

        table_title = QLabel("📄  Importaciones realizadas")
        table_title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px; font-weight: 700;")
        table_layout.addWidget(table_title)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Archivo", "Fecha", "Originales", "Conservados", "Descartados", "Origen"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(34)
        table_layout.addWidget(self.table)

        self.empty_label = QLabel("Todavía no has importado ningún archivo. Ve a \"Importar Excel\" para empezar.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px; padding: 24px;")
        table_layout.addWidget(self.empty_label)

        layout.addWidget(table_card)
        layout.addStretch()

        self.refresh()

    def _clear_stats(self):
        while self.stats_row.count():
            item = self.stats_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def refresh(self):
        self._clear_stats()
        history = store.import_history
        total_originales = sum(r.originales for r in history)
        total_conservados = sum(r.conservados for r in history)
        total_descartados = sum(r.descartados for r in history)

        cards = [
            StatCard("📥", "Importaciones", len(history), icon_bg="#e8f0fe"),
            StatCard("📄", "Registros originales", total_originales, icon_bg="#e8f0fe"),
            StatCard("✅", "Conservados", total_conservados, icon_bg="#e6f7ec"),
            StatCard("🧹", "Descartados", total_descartados, icon_bg="#fdece0"),
        ]
        for card in cards:
            self.stats_row.addWidget(card)
        self.stats_row.addStretch()

        self.table.setRowCount(len(history))
        for row, record in enumerate(history):
            values = [
                record.archivo,
                record.fecha,
                str(record.originales),
                str(record.conservados),
                str(record.descartados),
                record.origen,
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))
        size_table_to_contents(self.table)

        self.table.setVisible(bool(history))
        self.empty_label.setVisible(not history)
