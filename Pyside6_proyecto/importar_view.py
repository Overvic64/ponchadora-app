"""Pantalla 'Importar Excel': sube el archivo de ponchadas, lo depura y
muestra una vista previa antes de (mas adelante) enviarlo a Supabase."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
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

from core.attendance_import import CleaningResult, InputFileError, process_attendance_file
from store import store
from theme import COLORS
from widgets import StatCard

MAX_PREVIEW_ROWS = 300


class DropZone(QFrame):
    """Area de arrastrar-y-soltar / click para elegir el archivo de ponchadas."""

    def __init__(self, on_file_chosen, parent=None):
        super().__init__(parent)
        self.on_file_chosen = on_file_chosen
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(8)

        icon = QLabel("📊")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size: 30px;")

        self.title_label = QLabel("Arrastra y suelta aquí tu archivo de Excel")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px; font-weight: 600;")

        subtitle = QLabel("o haz clic en el botón para seleccionar")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")

        browse_btn = QPushButton("⬆  Subir archivo")
        browse_btn.setObjectName("primaryButton")
        browse_btn.setCursor(Qt.PointingHandCursor)
        browse_btn.setFixedWidth(160)
        browse_btn.clicked.connect(self._browse)

        hint = QLabel("Formatos aceptados: .xlsx, .xls, .csv — crudo del lector o ya depurado")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px;")

        layout.addWidget(icon)
        layout.addWidget(self.title_label)
        layout.addWidget(subtitle)
        layout.addWidget(browse_btn, alignment=Qt.AlignCenter)
        layout.addWidget(hint)

    def mousePressEvent(self, event):
        self._browse()
        super().mousePressEvent(event)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecciona el archivo de ponchadas", "", "Excel/CSV (*.xlsx *.xls *.csv)"
        )
        if path:
            self.on_file_chosen(Path(path))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            self.on_file_chosen(Path(urls[0].toLocalFile()))


class WarningBanner(QFrame):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "background-color: #fdf3e0; border: 1px solid #f0d9a8; border-radius: 8px;"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        icon = QLabel("⚠️")
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 11px;")
        layout.addWidget(icon)
        layout.addWidget(label, 1)


class PreviewTable(QTableWidget):
    HEADERS = ["Fecha", "Código", "Nombre", "Entrada", "Salida"]

    def __init__(self, parent=None):
        super().__init__(0, len(self.HEADERS), parent)
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSelectionMode(QTableWidget.NoSelection)
        self.setShowGrid(False)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.verticalHeader().setDefaultSectionSize(34)

    def load(self, daily_summary, shared_codes: dict[str, list[str]]):
        rows = daily_summary.head(MAX_PREVIEW_ROWS)
        self.setRowCount(len(rows))
        for row_index, record in enumerate(rows.itertuples(index=False)):
            values = [record.fecha, record.codigo, record.nombre, record.entrada, record.salida]
            flagged = record.codigo in shared_codes
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if flagged:
                    item.setBackground(Qt.GlobalColor.yellow)
                    item.setToolTip("Código compartido por varios nombres distintos — revisar.")
                self.setItem(row_index, col_index, item)


class ImportarExcelView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.result: CleaningResult | None = None
        self.current_path: Path | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Importar Excel de ponchadas")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 18px; font-weight: 700;")
        subtitle = QLabel(
            "Sube el export del lector biométrico (crudo) o el resumen ya depurado. "
            "Se detecta el formato automáticamente."
        )
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.drop_card = QFrame()
        self.drop_card.setObjectName("statCard")
        drop_layout = QVBoxLayout(self.drop_card)
        drop_layout.setContentsMargins(18, 16, 18, 16)
        self.drop_zone = DropZone(self._process_file)
        drop_layout.addWidget(self.drop_zone)
        layout.addWidget(self.drop_card)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.stats_row = QHBoxLayout()
        self.stats_row.setSpacing(16)
        layout.addLayout(self.stats_row)

        self.warning_container = QVBoxLayout()
        layout.addLayout(self.warning_container)

        self.results_card = QFrame()
        self.results_card.setObjectName("statCard")
        self.results_card.setVisible(False)
        results_layout = QVBoxLayout(self.results_card)
        results_layout.setContentsMargins(18, 16, 18, 16)
        results_layout.setSpacing(10)

        results_header = QHBoxLayout()
        results_title = QLabel("Vista previa (Fecha / Código / Nombre / Entrada / Salida)")
        results_title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px; font-weight: 700;")
        results_header.addWidget(results_title)
        results_header.addStretch()

        self.export_btn = QPushButton("⬇  Exportar a Excel")
        self.export_btn.setObjectName("secondaryButton")
        self.export_btn.setCursor(Qt.PointingHandCursor)
        self.export_btn.clicked.connect(self._export_result)
        results_header.addWidget(self.export_btn)

        self.supabase_btn = QPushButton("☁  Enviar a Supabase (próximamente)")
        self.supabase_btn.setObjectName("primaryButton")
        self.supabase_btn.setCursor(Qt.PointingHandCursor)
        self.supabase_btn.setEnabled(False)
        results_header.addWidget(self.supabase_btn)

        results_layout.addLayout(results_header)

        self.preview_table = PreviewTable()
        results_layout.addWidget(self.preview_table)

        layout.addWidget(self.results_card)
        layout.addStretch()

    def _clear_dynamic_widgets(self):
        while self.stats_row.count():
            item = self.stats_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        while self.warning_container.count():
            item = self.warning_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _process_file(self, path: Path):
        self.current_path = path
        self.status_label.setText(f"Procesando: {path.name}...")
        self.status_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        try:
            result = process_attendance_file(path)
        except InputFileError as error:
            self.result = None
            self.results_card.setVisible(False)
            self.status_label.setText(str(error))
            self.status_label.setStyleSheet(f"color: {COLORS['red']}; font-size: 11px; font-weight: 600;")
            self._clear_dynamic_widgets()
            return
        except Exception as error:  # noqa: BLE001 - mostramos cualquier error inesperado al usuario
            self.result = None
            self.results_card.setVisible(False)
            self.status_label.setText(f"Error inesperado al leer el archivo: {error}")
            self.status_label.setStyleSheet(f"color: {COLORS['red']}; font-size: 11px; font-weight: 600;")
            self._clear_dynamic_widgets()
            return

        self.result = result
        origin = "resumen ya depurado" if result.already_clean else "export crudo del lector"
        self.status_label.setText(f"Completado: {path.name} ({origin})")
        self.status_label.setStyleSheet(f"color: {COLORS['green']}; font-size: 11px; font-weight: 600;")
        self._render_result(result)

        descartados = result.duplicate_count + result.window_discard_count + result.invalid_date_count
        store.add_import(
            archivo=path.name,
            fecha=datetime.now().strftime("%Y-%m-%d %H:%M"),
            originales=result.input_count,
            conservados=len(result.daily_summary),
            descartados=descartados,
            origen=origin,
        )

    def _render_result(self, result: CleaningResult):
        self._clear_dynamic_widgets()

        date_range = result.date_range
        range_text = f"{date_range[0]} a {date_range[1]}" if date_range else "-"

        cards = [
            StatCard("📄", "Registros originales", result.input_count, icon_bg="#e8f0fe"),
        ]
        if not result.already_clean:
            cards.append(StatCard("🧹", "Duplicados descartados", result.duplicate_count, icon_bg="#fdece0"))
            cards.append(StatCard("⏱", "Descartados por ventana (5 min)", result.window_discard_count, icon_bg="#fdece0"))
        cards.append(StatCard("⚠️", "Fechas inválidas", result.invalid_date_count, icon_bg="#fde8e8"))
        cards.append(StatCard("👥", "Empleados únicos", result.unique_employees, icon_bg="#e6f7ec"))

        for card in cards:
            self.stats_row.addWidget(card)
        self.stats_row.addStretch()

        range_label = QLabel(f"📅 Rango de fechas: {range_text}")
        range_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        self.warning_container.addWidget(range_label)

        if result.shared_codes:
            names_preview = "; ".join(
                f"{codigo} → {', '.join(nombres[:3])}{'…' if len(nombres) > 3 else ''}"
                for codigo, nombres in list(result.shared_codes.items())[:5]
            )
            more = len(result.shared_codes) - 5
            suffix = f" (+{more} código(s) más)" if more > 0 else ""
            banner = WarningBanner(
                "Se encontraron códigos de empleado compartidos por varios nombres distintos "
                "(probablemente un lector sin huella registrada). Estas filas se resaltan en amarillo "
                "en la vista previa — deben emparejarse por nombre, no por código, al enviarlas a Supabase.\n"
                f"{names_preview}{suffix}"
            )
            self.warning_container.addWidget(banner)

        self.preview_table.load(result.daily_summary, result.shared_codes)
        self.results_card.setVisible(True)

    def _export_result(self):
        if self.result is None:
            return
        default_name = f"{self.current_path.stem}_Entradas_y_Salidas.xlsx" if self.current_path else "Entradas_y_Salidas.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "Exportar resultado", default_name, "Excel (*.xlsx)")
        if not path:
            return
        export_columns = ["fecha", "codigo", "nombre", "entrada", "salida"]
        try:
            self.result.daily_summary[export_columns].to_excel(path, index=False)
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(self, "Error al exportar", str(error))
            return
        QMessageBox.information(self, "Exportado", f"Archivo guardado en:\n{path}")
