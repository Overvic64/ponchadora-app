"""
Sistema de Control de Asistencia y Ponchador
"""
import sys

from PySide6.QtCharts import QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView, QValueAxis
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from asistencias_view import AsistenciasView
from configuracion_view import ConfiguracionView
from importar_view import ImportarExcelView
from incidencias_view import IncidenciasView
from limpieza_view import LimpiezaView
from personas_view import PersonasView
from report_data import etiqueta_quincena, quincenas_disponibles, resumen_global
from reportes_view import ReportesView
from store import store
from theme import COLORS
from widgets import StatCard

NAV_ITEMS = [
    ("🏠", "Inicio"),
    ("📄", "Importar Excel"),
    ("🧹", "Limpieza de registros"),
    ("📅", "Asistencias"),
    ("⚠️", "Incidencias"),
    ("📊", "Reportes"),
    ("👥", "Profesores"),
    ("👤", "Administrativos"),
    ("⚙️", "Configuración"),
]


def _clear_layout(layout):
    """Vacia un layout (widgets y sub-layouts anidados) para reconstruirlo.

    takeAt() saca el widget del layout pero no lo oculta -- hasta que
    deleteLater() se procesa (el siguiente ciclo de eventos) sigue visible
    en su posicion anterior, encimado con lo nuevo que se agregue en el
    mismo refresh(). Por eso se oculta aqui mismo, de una vez.
    """
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.hide()
            widget.deleteLater()
        else:
            sub_layout = item.layout()
            if sub_layout is not None:
                _clear_layout(sub_layout)


def _etiqueta_corta(anio, mes, mitad):
    from report_data import MESES, _ultimo_dia_mes

    rango = "1-15" if mitad == "primera" else f"16-{_ultimo_dia_mes(anio, mes)}"
    return f"{rango} {MESES[mes][:3].capitalize()}"


class Sidebar(QFrame):
    page_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(230)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 20, 0, 16)
        layout.setSpacing(4)

        logo_row = QHBoxLayout()
        logo_row.setContentsMargins(20, 0, 20, 24)
        logo_icon = QLabel("🎓")
        logo_icon.setStyleSheet("font-size: 22px;")
        logo_text = QLabel("Sistema de Control\nde Asistencia")
        logo_text.setStyleSheet(
            f"color: {COLORS['sidebar_text_active']}; font-size: 13px; font-weight: 600;"
        )
        logo_row.addWidget(logo_icon)
        logo_row.addWidget(logo_text)
        logo_row.addStretch()
        layout.addLayout(logo_row)

        self.nav_buttons = []
        for i, (icon, text) in enumerate(NAV_ITEMS):
            btn = QPushButton(f"  {icon}   {text}")
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setObjectName("navButton")
            btn.setProperty("active", i == 0)
            btn.clicked.connect(lambda _, b=btn, idx=i: self._select(b, idx))
            layout.addWidget(btn)
            self.nav_buttons.append(btn)

        layout.addStretch()

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background-color: {COLORS['sidebar_bg_hover']}; max-height:1px;")
        layout.addWidget(sep)

        footer = QLabel("v1.0.0\nSistema Institucional\n2026")
        footer.setStyleSheet(f"color: {COLORS['sidebar_text']}; font-size: 11px; padding: 12px 20px 0 20px;")
        layout.addWidget(footer)

    def _select(self, selected_btn, index):
        for btn in self.nav_buttons:
            active = btn is selected_btn
            btn.setChecked(active)
            btn.setProperty("active", active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.page_changed.emit(index)


class TopBar(QFrame):
    quincena_changed = Signal(tuple)
    busqueda = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("topbar")
        self.setFixedHeight(64)
        self._quincenas: list[tuple[int, int, str]] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(16)

        title = QLabel("Sistema de Control de Asistencia y Ponchador")
        title.setStyleSheet("color: white; font-size: 16px; font-weight: 600;")
        sub = QLabel("Institución Educativa")
        sub.setStyleSheet("color: rgba(255,255,255,0.65); font-size: 11px;")

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title_box.addWidget(title)
        title_box.addWidget(sub)
        layout.addLayout(title_box)

        layout.addStretch()

        self.quincena_combo = QComboBox()
        self.quincena_combo.setObjectName("quincenaBox")
        self.quincena_combo.setFixedWidth(260)
        self.quincena_combo.currentIndexChanged.connect(self._on_index_changed)
        layout.addWidget(self.quincena_combo)

        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍  Buscar empleado y Enter...")
        self.search.setObjectName("searchBox")
        self.search.setFixedWidth(220)
        self.search.returnPressed.connect(lambda: self.busqueda.emit(self.search.text().strip()))
        layout.addWidget(self.search)

        avatar = QLabel("👤")
        avatar.setStyleSheet(
            "background-color: rgba(255,255,255,0.15); border-radius: 16px;"
            "font-size: 15px; padding: 4px 8px;"
        )
        user_box = QVBoxLayout()
        user_box.setSpacing(0)
        name = QLabel("Admin")
        name.setStyleSheet("color: white; font-size: 12px; font-weight: 600;")
        role = QLabel("Administrador")
        role.setStyleSheet("color: rgba(255,255,255,0.65); font-size: 10px;")
        user_box.addWidget(name)
        user_box.addWidget(role)

        user_row = QHBoxLayout()
        user_row.setSpacing(8)
        user_row.addWidget(avatar)
        user_row.addLayout(user_box)
        layout.addLayout(user_row)

        self.set_quincenas(quincenas_disponibles())

    def quincena_actual(self) -> tuple[int, int, str] | None:
        index = self.quincena_combo.currentIndex()
        return self._quincenas[index] if 0 <= index < len(self._quincenas) else None

    def set_quincenas(self, quincenas: list[tuple[int, int, str]]):
        """Recarga la lista conservando la quincena elegida. Si esa quincena
        ya no existe, cae en la mas reciente y avisa a las pantallas para que
        no se queden mostrando un periodo distinto al del selector."""
        previa = self.quincena_actual()
        self._quincenas = quincenas
        self.quincena_combo.blockSignals(True)
        self.quincena_combo.clear()
        if not quincenas:
            self.quincena_combo.addItem("📅  Sin asistencias importadas")
        else:
            for anio, mes, mitad in quincenas:
                self.quincena_combo.addItem(f"📅  Quincena: {etiqueta_quincena(anio, mes, mitad)}")
            index = quincenas.index(previa) if previa in quincenas else len(quincenas) - 1
            self.quincena_combo.setCurrentIndex(index)
        self.quincena_combo.blockSignals(False)
        nueva = self.quincena_actual()
        if previa is not None and nueva is not None and nueva != previa:
            self.quincena_changed.emit(nueva)

    def _on_index_changed(self, index):
        if 0 <= index < len(self._quincenas):
            self.quincena_changed.emit(self._quincenas[index])


def _make_chart(datos: list[tuple[str, dict]]):
    set_retardos = QBarSet("Retardos")
    set_permisos = QBarSet("Permisos")
    set_faltas = QBarSet("Faltas")

    categorias = []
    max_valor = 5
    for etiqueta, resumen in datos:
        categorias.append(etiqueta)
        set_retardos.append(resumen["retardos"])
        set_permisos.append(resumen["permisos"])
        set_faltas.append(resumen["faltas"])
        max_valor = max(max_valor, resumen["retardos"], resumen["permisos"], resumen["faltas"])

    set_retardos.setColor(QColor(COLORS["orange"]))
    set_permisos.setColor(QColor(COLORS["blue"]))
    set_faltas.setColor(QColor(COLORS["red"]))

    series = QBarSeries()
    series.append(set_retardos)
    series.append(set_permisos)
    series.append(set_faltas)
    series.setBarWidth(0.6)

    chart = QChart()
    chart.addSeries(series)
    chart.legend().setVisible(True)
    chart.legend().setAlignment(Qt.AlignRight)
    chart.legend().setFont(QFont("Segoe UI", 8))
    chart.setBackgroundVisible(False)
    chart.setMargins(chart.margins() * 0)
    chart.layout().setContentsMargins(0, 0, 0, 0)

    axis_x = QBarCategoryAxis()
    axis_x.append(categorias or ["Sin datos"])
    axis_x.setLabelsFont(QFont("Segoe UI", 7))
    chart.addAxis(axis_x, Qt.AlignBottom)
    series.attachAxis(axis_x)

    axis_y = QValueAxis()
    axis_y.setRange(0, max(10, int(max_valor * 1.2)))
    axis_y.setLabelsFont(QFont("Segoe UI", 7))
    chart.addAxis(axis_y, Qt.AlignLeft)
    series.attachAxis(axis_y)

    view = QChartView(chart)
    view.setRenderHint(QPainter.Antialiasing)
    view.setStyleSheet("background: transparent;")
    return view


class IncidenciasChartCard(QFrame):
    def __init__(self, datos, parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.setSpacing(8)

        title = QLabel("📈  Incidencias por quincena")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px; font-weight: 700;")
        layout.addWidget(title)
        layout.addWidget(_make_chart(datos))


class UploadCard(QFrame):
    def __init__(self, on_click, parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        self.setCursor(Qt.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title = QLabel("📄  Cargar archivo Excel de ponchadas")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px; font-weight: 700;")
        layout.addWidget(title)

        drop = QFrame()
        drop.setObjectName("dropZone")
        drop_layout = QVBoxLayout(drop)
        drop_layout.setAlignment(Qt.AlignCenter)
        drop_layout.setSpacing(8)

        icon = QLabel("📊")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size: 30px;")
        text1 = QLabel("Ve a la pantalla de importación")
        text1.setAlignment(Qt.AlignCenter)
        text1.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px; font-weight: 600;")
        text2 = QLabel("ahí subes y depuras el Excel de ponchadas")
        text2.setAlignment(Qt.AlignCenter)
        text2.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")

        upload_btn = QPushButton("⬆  Ir a Importar Excel")
        upload_btn.setObjectName("primaryButton")
        upload_btn.setCursor(Qt.PointingHandCursor)
        upload_btn.setFixedWidth(180)
        upload_btn.clicked.connect(on_click)

        drop_layout.addWidget(icon)
        drop_layout.addWidget(text1)
        drop_layout.addWidget(text2)
        drop_layout.addWidget(upload_btn, alignment=Qt.AlignCenter)

        layout.addWidget(drop)
        self._on_click = on_click

    def mousePressEvent(self, event):
        self._on_click()
        super().mousePressEvent(event)


class ProcessCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(18, 16, 18, 16)
        self._layout.setSpacing(14)

        title = QLabel("✅  Pendientes de configuración")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px; font-weight: 700;")
        self._layout.addWidget(title)

        self._steps_container = QVBoxLayout()
        self._steps_container.setSpacing(14)
        self._layout.addLayout(self._steps_container)
        self._layout.addStretch()

        self.refresh()

    def _step_widget(self, index, title, desc, done):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(12)

        badge = QLabel("✓" if done else str(index))
        badge.setFixedSize(26, 26)
        badge.setAlignment(Qt.AlignCenter)
        bg = COLORS["green"] if done else COLORS["blue"]
        badge.setStyleSheet(
            f"background-color: {bg}; color: white; border-radius: 13px; font-size: 12px; font-weight: 700;"
        )
        row_layout.addWidget(badge)

        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        t = QLabel(title)
        t.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px; font-weight: 600;")
        d = QLabel(desc)
        d.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px;")
        d.setWordWrap(True)
        text_box.addWidget(t)
        text_box.addWidget(d)
        row_layout.addLayout(text_box, 1)
        return row

    def refresh(self):
        _clear_layout(self._steps_container)

        maestros = store.maestros
        total = len(maestros)
        sin_clasificar = sum(1 for m in maestros if not m.tipo_personal)
        sin_turno = sum(1 for m in maestros if not m.turno)

        if total == 0:
            paso_clasificar = ("Clasificar tipo de personal", "Todavía no hay empleados registrados.", False)
            paso_turno = ("Asignar turno a los empleados", "Todavía no hay empleados registrados.", False)
        else:
            paso_clasificar = (
                "Clasificar tipo de personal",
                "Todos los empleados están clasificados."
                if sin_clasificar == 0
                else f"Faltan {sin_clasificar} de {total} empleados por clasificar.",
                sin_clasificar == 0,
            )
            paso_turno = (
                "Asignar turno a los empleados",
                "Todos los empleados tienen turno asignado."
                if sin_turno == 0
                else f"Faltan {sin_turno} de {total} empleados por asignarles turno.",
                sin_turno == 0,
            )

        pasos = [
            (
                "Importar ponchadas de Excel",
                f"{len(store.import_history)} archivo(s) importado(s)."
                if store.import_history
                else "Todavía no se ha importado ningún archivo.",
                bool(store.import_history),
            ),
            paso_clasificar,
            paso_turno,
        ]
        for i, (paso_titulo, paso_desc, done) in enumerate(pasos, start=1):
            self._steps_container.addWidget(self._step_widget(i, paso_titulo, paso_desc, done))


class ReportChip(QFrame):
    def __init__(self, title, color, on_click, parent=None):
        super().__init__(parent)
        self.setObjectName("reportChip")
        self.setProperty("chipColor", color)
        self.setCursor(Qt.PointingHandCursor)
        self._on_click = on_click
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)

        icon = QLabel("📄")
        icon.setStyleSheet("font-size: 15px;")
        label = QLabel(title)
        label.setWordWrap(True)
        label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 11px; font-weight: 600;")
        arrow = QLabel("›")
        arrow.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 16px; font-weight: 700;")

        layout.addWidget(icon)
        layout.addWidget(label, 1)
        layout.addWidget(arrow)

        self.setStyleSheet(f"#reportChip {{ background-color: {color}; border-radius: 10px; }}")

    def mousePressEvent(self, event):
        self._on_click()
        super().mousePressEvent(event)


class ReportsCard(QFrame):
    CHIPS = [
        ("Concentrado Incidencias\nProfesor de Asignatura", "#e8f0fe", None),
        ("Concentrado Incidencias\nAdministrativo y PTC", "#e6f7ec", "F05"),
        ("Control Quincenal\nProfesor de Asignatura", "#e8f0fe", "F02"),
        ("Control Quincenal\nAdministrativos y PTC", "#fdece0", "F01"),
    ]

    def __init__(self, navigate, parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title = QLabel("📊  Reportes disponibles")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px; font-weight: 700;")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(10)
        for i, (text, color, clave) in enumerate(self.CHIPS):
            chip = ReportChip(text, color, lambda c=clave: navigate(5, c))
            grid.addWidget(chip, i // 2, i % 2)
        layout.addLayout(grid)

        all_btn = QPushButton("📄  Ver todos los reportes")
        all_btn.setObjectName("secondaryButton")
        all_btn.setCursor(Qt.PointingHandCursor)
        all_btn.clicked.connect(lambda: navigate(5))
        layout.addWidget(all_btn)


TIPO_COLORS = {
    "Administrativo": ("#e6f7ec", "#16a34a"),
    "Profesor de Tiempo Completo": ("#f3e8fd", "#7c3aed"),
    "Profesor de Asignatura": ("#e8f0fe", "#2563eb"),
}


class TypeBadge(QWidget):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        bg, fg = TIPO_COLORS.get(text, ("#eee", "#666"))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        lbl = QLabel(text or "Sin clasificar")
        lbl.setStyleSheet(
            f"background-color: {bg}; color: {fg}; border-radius: 8px; padding: 3px 10px;"
            f"font-size: 10px; font-weight: 600;"
        )
        layout.addWidget(lbl)
        layout.addStretch()


class RecordsTable(QFrame):
    HEADERS = ["Fecha", "Empleado", "Tipo", "Entrada", "Salida", "Retardo (min)", "Observaciones"]

    def __init__(self, filas, parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 10)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        title = QLabel("📄  Últimas ponchadas registradas")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px; font-weight: 700;")
        header_row.addWidget(title)
        header_row.addStretch()
        layout.addLayout(header_row)

        table = QTableWidget(len(filas), len(self.HEADERS))
        table.setHorizontalHeaderLabels(self.HEADERS)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setShowGrid(False)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        table.verticalHeader().setDefaultSectionSize(40)

        for row, r in enumerate(filas):
            table.setItem(row, 0, QTableWidgetItem(r["fecha"]))
            table.setItem(row, 1, QTableWidgetItem(r["nombre"]))
            table.setCellWidget(row, 2, TypeBadge(r["tipo_personal"]))
            table.setItem(row, 3, QTableWidgetItem(r["entrada"]))
            table.setItem(row, 4, QTableWidgetItem(r["salida"]))

            retardo_item = QTableWidgetItem(str(r["retardo"]) if r["retardo"] else "-")
            if r["retardo"]:
                retardo_item.setForeground(QColor(COLORS["orange"]))
                f = QFont()
                f.setBold(True)
                retardo_item.setFont(f)
            table.setItem(row, 5, retardo_item)
            table.setItem(row, 6, QTableWidgetItem(r["observaciones"] or "-"))

        layout.addWidget(table)

        if not filas:
            empty = QLabel("Todavía no hay ponchadas importadas.")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px; padding: 20px;")
            layout.addWidget(empty)


class DashboardContent(QWidget):
    def __init__(self, navigate, parent=None):
        super().__init__(parent)
        self.navigate = navigate
        self._quincena_actual: tuple[int, int, str] | None = None

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(24, 20, 24, 24)
        self._layout.setSpacing(16)

        self._stats_row = QHBoxLayout()
        self._stats_row.setSpacing(16)
        self._layout.addLayout(self._stats_row)

        self._coverage_label = QLabel("")
        self._coverage_label.setStyleSheet(
            f"color: {COLORS['orange']}; font-size: 11px; font-weight: 600; padding: 2px 2px 0 2px;"
        )
        self._coverage_label.setVisible(False)
        self._layout.addWidget(self._coverage_label)

        mid_row = QHBoxLayout()
        mid_row.setSpacing(16)
        self.process_card = ProcessCard()
        mid_row.addWidget(UploadCard(lambda: self.navigate(1)), 1)
        mid_row.addWidget(self.process_card, 1)
        mid_row.addWidget(ReportsCard(self.navigate), 1)
        self._layout.addLayout(mid_row)

        self._table_container = QVBoxLayout()
        self._layout.addLayout(self._table_container)
        self._layout.addStretch()

        self.refresh()

    def set_quincena(self, quincena: tuple[int, int, str]):
        self._quincena_actual = quincena
        self.refresh()

    def refresh(self):
        self.process_card.refresh()
        self._rebuild_stats_and_chart()
        self._rebuild_table()

    def _rebuild_stats_and_chart(self):
        _clear_layout(self._stats_row)

        quincenas = quincenas_disponibles()
        maestros = store.maestros
        # Memo por si la quincena actual/anterior coincide con alguna de las
        # ultimas 4 que tambien se grafican -- resumen_global ya hace una
        # consulta a Supabase, no tiene sentido repetirla en el mismo refresh.
        cache: dict[tuple[int, int, str], dict] = {}

        def resumen(quincena):
            if quincena not in cache:
                cache[quincena] = resumen_global(maestros, *quincena)
            return cache[quincena]

        actual_q = self._quincena_actual if self._quincena_actual in quincenas else (quincenas[-1] if quincenas else None)
        anterior_q = None
        if actual_q and actual_q in quincenas:
            idx = quincenas.index(actual_q)
            if idx > 0:
                anterior_q = quincenas[idx - 1]

        actual = (
            resumen(actual_q)
            if actual_q
            else {"asistencias": 0, "retardos": 0, "permisos": 0, "faltas": 0, "dias_totales": 0, "dias_con_datos": 0}
        )
        anterior = resumen(anterior_q) if anterior_q else None
        suffix = "vs. quincena anterior" if anterior else ""

        def delta(clave):
            if anterior is None:
                return None, True
            a, b = actual[clave], anterior[clave]
            if b == 0:
                return (None, True) if a == 0 else ("nuevo", True)
            pct = round((a - b) / b * 100)
            return f"{pct:+d}%", pct >= 0

        cards_def = [
            ("⏱", "Retardos", "retardos", "#fdece0"),
            ("📄", "Permisos", "permisos", "#e8f0fe"),
            ("✕", "Faltas", "faltas", "#fde8e8"),
            ("👥", "Asistencias", "asistencias", "#e6f7ec"),
        ]
        left_col = QVBoxLayout()
        left_col.setSpacing(16)
        top_stats = QHBoxLayout()
        top_stats.setSpacing(16)
        for icon, titulo, clave, bg in cards_def:
            delta_text, delta_up = delta(clave)
            top_stats.addWidget(StatCard(icon, titulo, actual[clave], delta_text, delta_up, bg, delta_suffix=suffix))
        left_col.addLayout(top_stats)
        self._stats_row.addLayout(left_col, 2)

        faltantes = actual["dias_totales"] - actual["dias_con_datos"]
        if actual_q and faltantes > 0:
            self._coverage_label.setText(
                f"⚠️  {faltantes} de {actual['dias_totales']} días hábiles de esta quincena todavía no tienen "
                "ninguna ponchada importada — no se cuentan como falta, solo se excluyen del total."
            )
            self._coverage_label.setVisible(True)
        else:
            self._coverage_label.setVisible(False)

        ultimas = quincenas[-4:] if quincenas else []
        datos_chart = [(_etiqueta_corta(*q), resumen(q)) for q in ultimas]
        self._stats_row.addWidget(IncidenciasChartCard(datos_chart), 2)

    def _rebuild_table(self):
        _clear_layout(self._table_container)
        maestros_by_id = {m.id: m for m in store.maestros}
        filas = []
        for r in store.reporte_asistencias(limit=8):
            maestro = maestros_by_id.get(r.get("maestro_id"))
            filas.append(
                {
                    "fecha": r.get("fecha") or "",
                    "nombre": r.get("nombre") or "",
                    "tipo_personal": maestro.tipo_personal if maestro else None,
                    "entrada": (r.get("entrada") or "-")[:5],
                    "salida": (r.get("salida") or "-")[:5],
                    "retardo": r.get("retardo_minutos_referencia") or 0,
                    "observaciones": r.get("observaciones"),
                }
            )
        self._table_container.addWidget(RecordsTable(filas))


class ComingSoonPage(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        icon = QLabel("🚧")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size: 40px;")
        label = QLabel(f"{title} — en construcción")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 14px; font-weight: 600;")
        layout.addWidget(icon)
        layout.addWidget(label)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sistema de Control de Asistencia y Ponchador")
        self.resize(1440, 900)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.page_changed.connect(self._show_page)
        root.addWidget(self.sidebar)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)

        self.topbar = TopBar()
        self.topbar.quincena_changed.connect(self._on_quincena_changed)
        self.topbar.busqueda.connect(self._buscar_empleado)
        right.addWidget(self.topbar)

        self.pages = QStackedWidget()
        self.page_indices = {}
        page_factories = {
            0: lambda: DashboardContent(self.navigate),
            1: ImportarExcelView,
            2: LimpiezaView,
            3: AsistenciasView,
            4: IncidenciasView,
            5: ReportesView,
            6: lambda: PersonasView("Profesores", ["Profesor de Tiempo Completo", "Profesor de Asignatura"]),
            7: lambda: PersonasView("Administrativos", ["Administrativo"]),
            8: ConfiguracionView,
        }
        for i, (_icon, label) in enumerate(NAV_ITEMS):
            factory = page_factories.get(i)
            page = factory() if factory else ComingSoonPage(label)
            if i == 0:
                self.dashboard = page
            if i == 3:
                self.asistencias_page = page
            if i == 4:
                self.incidencias_page = page
            if i == 5:
                self.reportes_page = page

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setWidget(page)
            self.page_indices[i] = self.pages.count()
            self.pages.addWidget(scroll)

        right.addWidget(self.pages)

        right_widget = QWidget()
        right_widget.setLayout(right)
        root.addWidget(right_widget, 1)

    def navigate(self, nav_index, report_key=None):
        self.sidebar._select(self.sidebar.nav_buttons[nav_index], nav_index)
        if report_key and nav_index == 5:
            self.reportes_page._select_report(report_key)

    def _on_quincena_changed(self, quincena):
        self.dashboard.set_quincena(quincena)
        self.asistencias_page.set_quincena(quincena)
        self.incidencias_page.set_quincena(quincena)

    def _buscar_empleado(self, texto):
        self.asistencias_page.search_box.setText(texto)
        self.navigate(3)

    def _show_page(self, nav_index):
        self.pages.setCurrentIndex(self.page_indices[nav_index])
        scroll = self.pages.currentWidget()
        page = scroll.widget()
        if hasattr(page, "refresh"):
            page.refresh()
        if nav_index == 0:
            self.topbar.set_quincenas(quincenas_disponibles())


STYLE_SHEET = f"""
QWidget {{
    font-family: 'Segoe UI';
}}
QMainWindow, #scrollArea {{
    background-color: {COLORS['page_bg']};
}}
QScrollArea {{
    background-color: {COLORS['page_bg']};
    border: none;
}}
DashboardContent, ImportarExcelView, ComingSoonPage, LimpiezaView, AsistenciasView,
IncidenciasView, ReportesView, PersonasView, ConfiguracionView {{
    background-color: {COLORS['page_bg']};
}}

/* Sidebar */
#sidebar {{
    background-color: {COLORS['sidebar_bg']};
    border: none;
}}
QPushButton#navButton {{
    text-align: left;
    color: {COLORS['sidebar_text']};
    background-color: transparent;
    border: none;
    padding: 11px 20px;
    font-size: 12.5px;
    font-weight: 500;
}}
QPushButton#navButton:hover {{
    background-color: {COLORS['sidebar_bg_hover']};
    color: {COLORS['sidebar_text_active']};
}}
QPushButton#navButton[active="true"] {{
    background-color: {COLORS['sidebar_active']};
    color: {COLORS['sidebar_text_active']};
    border-left: 3px solid white;
    font-weight: 700;
}}

/* Topbar */
#topbar {{
    background-color: {COLORS['topbar_bg']};
    border: none;
}}
QComboBox#quincenaBox {{
    background-color: rgba(255,255,255,0.12);
    color: white;
    border: 1px solid rgba(255,255,255,0.25);
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 11px;
}}
QComboBox#quincenaBox QAbstractItemView {{
    background-color: white;
    color: {COLORS['text_primary']};
}}
QLineEdit#searchBox {{
    background-color: rgba(255,255,255,0.12);
    color: white;
    border: 1px solid rgba(255,255,255,0.25);
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 11px;
}}
QLineEdit#searchBox:focus {{
    background-color: rgba(255,255,255,0.2);
}}

QLineEdit#searchBoxLight {{
    background-color: {COLORS['page_bg']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 7px 10px;
    font-size: 11px;
}}
QLineEdit#searchBoxLight:focus {{
    border: 1px solid {COLORS['blue']};
}}
QComboBox {{
    background-color: {COLORS['page_bg']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 7px 10px;
    font-size: 11px;
}}
QComboBox QAbstractItemView {{
    background-color: white;
    color: {COLORS['text_primary']};
    selection-background-color: {COLORS['blue']};
    selection-color: white;
}}
QDateEdit, QTimeEdit, QSpinBox {{
    background-color: {COLORS['page_bg']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 11px;
}}
QDateEdit::drop-down {{
    border: none;
    width: 20px;
}}
QDateEdit QAbstractItemView {{
    background-color: white;
    color: {COLORS['text_primary']};
    selection-background-color: {COLORS['blue']};
    selection-color: white;
}}
QCalendarWidget QWidget {{
    background-color: white;
    color: {COLORS['text_primary']};
}}
QCalendarWidget QToolButton {{
    color: {COLORS['text_primary']};
}}
QLineEdit {{
    color: {COLORS['text_primary']};
    background-color: white;
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 5px 8px;
}}

/* Cards */
QFrame#statCard {{
    background-color: {COLORS['card_bg']};
    border: 1px solid {COLORS['border']};
    border-radius: 12px;
}}
QFrame#dropZone {{
    border: 2px dashed #c9d3e8;
    border-radius: 10px;
    background-color: #f8faff;
    padding: 22px;
}}

QPushButton#primaryButton {{
    background-color: {COLORS['blue']};
    color: white;
    border: none;
    border-radius: 8px;
    padding: 9px 14px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#primaryButton:hover {{
    background-color: #1d4ed8;
}}
QPushButton#secondaryButton {{
    background-color: white;
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 9px 14px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#secondaryButton:hover {{
    background-color: #f2f4f9;
}}

/* Table */
QTableWidget {{
    border: none;
    background-color: white;
    color: {COLORS['text_primary']};
    gridline-color: {COLORS['border']};
    font-size: 11.5px;
}}
QHeaderView::section {{
    background-color: #f8f9fc;
    color: {COLORS['text_secondary']};
    border: none;
    border-bottom: 1px solid {COLORS['border']};
    padding: 8px;
    font-size: 10.5px;
    font-weight: 700;
    text-transform: uppercase;
}}
QTableWidget::item {{
    border-bottom: 1px solid {COLORS['border']};
    padding-left: 4px;
}}
QDialog {{
    background-color: white;
}}
QDialog QLabel, QDialog QCheckBox {{
    color: {COLORS['text_primary']};
    font-size: 12px;
}}
QDialog QScrollArea, QDialog QScrollArea > QWidget > QWidget {{
    background-color: white;
}}
QDialog QPushButton {{
    background-color: white;
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 6px 18px;
    font-size: 12px;
}}
QDialog QPushButton:hover {{
    background-color: #f2f4f9;
}}
QDialog QPushButton:default {{
    background-color: {COLORS['blue']};
    color: white;
    border: none;
}}
QPushButton#tableButton {{
    background-color: white;
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 2px 6px;
    font-size: 11px;
}}
QPushButton#tableButton:hover {{
    background-color: #f2f4f9;
}}
"""


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE_SHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
