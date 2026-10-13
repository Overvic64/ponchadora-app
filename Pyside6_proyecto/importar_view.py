"""Pantalla 'Importar Excel': sube el archivo de ponchadas, lo depura,
muestra una vista previa y lo envia a Supabase."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.attendance_import import CleaningResult, InputFileError, process_attendance_file
from store import EDIFICIOS, store
from theme import COLORS
from widgets import StatCard

MAX_PREVIEW_ROWS = 300
ORIGEN_GLOBAL = "No especificado (archivo global)"


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
        self.current_origin: str = ""

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

        origen_label = QLabel("Ponchador de origen:")
        origen_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        results_header.addWidget(origen_label)
        self.origen_combo = QComboBox()
        self.origen_combo.addItem(ORIGEN_GLOBAL)
        self.origen_combo.addItems(EDIFICIOS)
        self.origen_combo.setToolTip(
            "Edificio del lector de donde salió el archivo. Si el archivo junta varios "
            "lectores, deja 'No especificado': el edificio de cada empleado se toma de su "
            "registro, no del lector."
        )
        results_header.addWidget(self.origen_combo)

        self.supabase_btn = QPushButton("☁  Enviar a Supabase")
        self.supabase_btn.setObjectName("primaryButton")
        self.supabase_btn.setCursor(Qt.PointingHandCursor)
        self.supabase_btn.clicked.connect(self._enviar_supabase)
        results_header.addWidget(self.supabase_btn)

        results_layout.addLayout(results_header)

        self.preview_table = PreviewTable()
        results_layout.addWidget(self.preview_table)

        layout.addWidget(self.results_card)
        layout.addStretch()

    def _clear_dynamic_widgets(self):
        for container in (self.stats_row, self.warning_container):
            while container.count():
                item = container.takeAt(0)
                if item.widget():
                    item.widget().hide()
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
        self.current_origin = "resumen ya depurado" if result.already_clean else "export crudo del lector"
        self.status_label.setText(f"Completado: {path.name} ({self.current_origin})")
        self.status_label.setStyleSheet(f"color: {COLORS['green']}; font-size: 11px; font-weight: 600;")
        self._render_result(result)

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
        cards.append(StatCard("⚠️", "Filas inválidas", result.invalid_count, icon_bg="#fde8e8"))
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

    def _ofrecer_alta_empleados(self, codigos_compartidos: set[str]) -> bool:
        """Si el archivo trae personas que no existen en la base, ofrece darlas
        de alta. Regresa False si el usuario cancela el envio."""
        pendientes = store.empleados_sin_registrar(self.result.daily_summary, codigos_compartidos)
        if not pendientes:
            return True
        ejemplos = "\n".join(f"• {p['nombre']} ({p['codigo']})" for p in pendientes[:10])
        if len(pendientes) > 10:
            ejemplos += f"\n... y {len(pendientes) - 10} más."
        respuesta = QMessageBox.question(
            self, "Empleados nuevos",
            f"{len(pendientes)} persona(s) del archivo no están registradas:\n\n{ejemplos}\n\n"
            "¿Darlas de alta ahora? Quedarán 'sin clasificar' (tipo, turno y área en blanco) para "
            "que las completes en Profesores/Administrativos.\n\n"
            "Si eliges No, sus ponchadas no se subirán.",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
        )
        if respuesta == QMessageBox.Cancel:
            return False
        if respuesta == QMessageBox.No:
            return True
        edificio, ok = QInputDialog.getItem(
            self, "Edificio inicial",
            "Edificio que se les asignará (lo puedes corregir después por persona):",
            EDIFICIOS, 0, False,
        )
        if not ok:
            return False
        try:
            store.alta_maestros(pendientes, edificio)
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(self, "Error al dar de alta", str(error))
            return False
        return True

    def _enviar_supabase(self):
        if self.result is None:
            return
        if self.current_path is not None:
            fecha_previa = store.ya_importado(self.current_path.name)
            if fecha_previa:
                respuesta = QMessageBox.question(
                    self, "Archivo ya importado",
                    f"'{self.current_path.name}' ya se importó el {fecha_previa}.\n\n"
                    "Volver a enviarlo no duplica registros: los horarios se combinan con los que "
                    "ya existen. ¿Enviarlo de nuevo?",
                )
                if respuesta != QMessageBox.Yes:
                    return

        origen = self.origen_combo.currentText()
        ponchador_id = None if origen == ORIGEN_GLOBAL else store.ponchador_id_por_edificio(origen)
        if origen != ORIGEN_GLOBAL and ponchador_id is None:
            QMessageBox.critical(self, "Ponchador no encontrado", f"No encontré el ponchador de '{origen}' en Supabase.")
            return

        codigos_compartidos = set(self.result.shared_codes)
        if not self._ofrecer_alta_empleados(codigos_compartidos):
            return

        try:
            resultado = store.insertar_asistencias(
                self.result.daily_summary, ponchador_id, codigos_compartidos=codigos_compartidos
            )
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(self, "Error al enviar a Supabase", str(error))
            return

        if self.current_path is not None:
            store.add_import(
                archivo=self.current_path.name,
                fecha=datetime.now().strftime("%Y-%m-%d %H:%M"),
                originales=self.result.input_count,
                conservados=resultado["insertados"] + resultado["actualizados"] + resultado["sin_cambios"],
                descartados=len(resultado["sin_match"]),
                origen=self.current_origin,
            )

        mensaje = (
            f"Nuevos: {resultado['insertados']}\n"
            f"Actualizados (se combinaron con lo existente): {resultado['actualizados']}\n"
            f"Sin cambios (ya estaban igual): {resultado['sin_cambios']}\n"
            f"Sin empleado registrado: {len(resultado['sin_match'])}"
        )
        if resultado["sin_match"]:
            ejemplos = "\n".join(resultado["sin_match"][:10])
            mensaje += f"\n\nNo se subieron (empleado no registrado o nombre ambiguo):\n{ejemplos}"
            if len(resultado["sin_match"]) > 10:
                mensaje += f"\n... y {len(resultado['sin_match']) - 10} más."
        QMessageBox.information(self, "Enviado a Supabase", mensaje)

    def _export_result(self):
        if self.result is None:
            return
        default_name = f"{self.current_path.stem}_Entradas_y_Salidas.xlsx" if self.current_path else "Entradas_y_Salidas.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "Exportar resultado", default_name, "Excel (*.xlsx)")
        if not path:
            return
        export = self.result.daily_summary[["fecha", "codigo", "nombre", "entrada", "salida"]].copy()
        # Mismos encabezados que espera el importador, para poder volver a subirlo.
        export.columns = ["Fecha", "Codigo", "Nombre", "Entrada", "Salida"]
        try:
            export.to_excel(path, index=False)
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(self, "Error al exportar", str(error))
            return
        QMessageBox.information(self, "Exportado", f"Archivo guardado en:\n{path}")
