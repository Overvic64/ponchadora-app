"""Widgets reutilizables entre pantallas."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from theme import COLORS


class StatCard(QFrame):
    def __init__(self, icon, title, value, delta=None, delta_up=True, icon_bg="#e8f0fe",
                 delta_suffix="", parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(10)

        top_row = QHBoxLayout()
        icon_lbl = QLabel(icon)
        icon_lbl.setFixedSize(40, 40)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet(
            f"background-color: {icon_bg}; border-radius: 10px; font-size: 17px;"
        )
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px; font-weight: 600;")
        top_row.addWidget(icon_lbl)
        top_row.addWidget(title_lbl)
        top_row.addStretch()
        outer.addLayout(top_row)

        value_lbl = QLabel(str(value))
        value_lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 26px; font-weight: 700;")
        outer.addWidget(value_lbl)
        self.value_label = value_lbl

        if delta is not None:
            arrow = "↑" if delta_up else "↓"
            color = COLORS["green"] if delta_up else COLORS["red"]
            text = f"{arrow} {delta}  {delta_suffix}".rstrip()
            delta_lbl = QLabel(text)
            delta_lbl.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 600;")
            outer.addWidget(delta_lbl)


def size_table_to_contents(table, max_visible_rows=None):
    """QTableWidget no crece con el numero de filas dentro de un layout con
    stretch; esto fija su alto minimo segun el contenido real para que se
    vean todas las filas sin necesidad de scroll interno."""
    row_count = table.rowCount()
    visible_rows = min(row_count, max_visible_rows) if max_visible_rows else row_count
    row_height = table.verticalHeader().defaultSectionSize()
    header_height = table.horizontalHeader().height() or 32
    total = header_height + visible_rows * row_height + 6
    table.setMinimumHeight(max(total, header_height + row_height))
