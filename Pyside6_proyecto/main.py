"""
Sistema de Control de Asistencia y Ponchador
Réplica de la interfaz de referencia construida con PySide6.
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
    QSizePolicy,
    QSpacerItem,
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
from reportes_view import ReportesView
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

        footer = QLabel("v1.0.0\nSistema Institucional\n2024")
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("topbar")
        self.setFixedHeight(64)

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

        quincena = QComboBox()
        quincena.addItem("📅  Quincena: 01 - 15 de octubre de 2024")
        quincena.setObjectName("quincenaBox")
        quincena.setFixedWidth(260)
        layout.addWidget(quincena)

        search = QLineEdit()
        search.setPlaceholderText("🔍  Buscar empleado...")
        search.setObjectName("searchBox")
        search.setFixedWidth(220)
        layout.addWidget(search)

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


def make_chart():
    set_retardos = QBarSet("Retardos")
    set_permisos = QBarSet("Permisos")
    set_faltas = QBarSet("Faltas")

    set_retardos.append([8, 10, 22, 12])
    set_permisos.append([6, 7, 9, 8])
    set_faltas.append([3, 4, 8, 5])

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
    axis_x.append(["16-31 Ago", "01-15 Sep", "16-30 Sep", "01-15 Oct"])
    axis_x.setLabelsFont(QFont("Segoe UI", 7))
    chart.addAxis(axis_x, Qt.AlignBottom)
    series.attachAxis(axis_x)

    axis_y = QValueAxis()
    axis_y.setRange(0, 30)
    axis_y.setLabelsFont(QFont("Segoe UI", 7))
    chart.addAxis(axis_y, Qt.AlignLeft)
    series.attachAxis(axis_y)

    view = QChartView(chart)
    view.setRenderHint(QPainter.Antialiasing)
    view.setStyleSheet("background: transparent;")
    return view


class IncidenciasChartCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.setSpacing(8)

        title = QLabel("📈  Incidencias por quincena")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px; font-weight: 700;")
        layout.addWidget(title)
        layout.addWidget(make_chart())


class UploadCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
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
        text1 = QLabel("Arrastra y suelta aquí tu archivo de Excel")
        text1.setAlignment(Qt.AlignCenter)
        text1.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px; font-weight: 600;")
        text2 = QLabel("o haz clic en el botón para seleccionar")
        text2.setAlignment(Qt.AlignCenter)
        text2.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")

        upload_btn = QPushButton("⬆  Subir archivo")
        upload_btn.setObjectName("primaryButton")
        upload_btn.setCursor(Qt.PointingHandCursor)
        upload_btn.setFixedWidth(160)

        hint = QLabel("Formatos aceptados: .xlsx, .xls  |  Tamaño máximo: 10 MB")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px;")

        drop_layout.addWidget(icon)
        drop_layout.addWidget(text1)
        drop_layout.addWidget(text2)
        drop_layout.addWidget(upload_btn, alignment=Qt.AlignCenter)
        drop_layout.addWidget(hint)

        layout.addWidget(drop)


class ProcessCard(QFrame):
    STEPS = [
        ("Leer archivo", "Se cargan los registros del archivo Excel.", "done"),
        ("Depurar registros duplicados", "Se eliminan registros repetidos.", "done"),
        ("Conservar 1 entrada y 1 salida por día", "Se valida y deja solo un registro de entrada y uno de salida.", "pending"),
        ("Validar horarios", "Se revisan los horarios contra la configuración.", "pending"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        title = QLabel("⚙️  Proceso de limpieza")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px; font-weight: 700;")
        layout.addWidget(title)

        for i, (step_title, desc, status) in enumerate(self.STEPS, start=1):
            row = QHBoxLayout()
            row.setSpacing(12)

            badge = QLabel("✓" if status == "done" else str(i))
            badge.setFixedSize(26, 26)
            badge.setAlignment(Qt.AlignCenter)
            bg = COLORS["green"] if status == "done" else COLORS["blue"]
            badge.setStyleSheet(
                f"background-color: {bg}; color: white; border-radius: 13px; font-size: 12px; font-weight: 700;"
            )
            row.addWidget(badge)

            text_box = QVBoxLayout()
            text_box.setSpacing(1)
            t = QLabel(step_title)
            t.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px; font-weight: 600;")
            d = QLabel(desc)
            d.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px;")
            d.setWordWrap(True)
            text_box.addWidget(t)
            text_box.addWidget(d)
            row.addLayout(text_box, 1)

            layout.addLayout(row)

        layout.addStretch()

        btn_row = QHBoxLayout()
        run_btn = QPushButton("▶  Ejecutar proceso de limpieza")
        run_btn.setObjectName("primaryButton")
        run_btn.setCursor(Qt.PointingHandCursor)
        detail_btn = QPushButton("Ver detalle")
        detail_btn.setObjectName("secondaryButton")
        detail_btn.setCursor(Qt.PointingHandCursor)
        btn_row.addWidget(run_btn)
        btn_row.addWidget(detail_btn)
        layout.addLayout(btn_row)


class ReportChip(QFrame):
    def __init__(self, title, color, parent=None):
        super().__init__(parent)
        self.setObjectName("reportChip")
        self.setProperty("chipColor", color)
        self.setCursor(Qt.PointingHandCursor)
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

        self.setStyleSheet(
            f"#reportChip {{ background-color: {color}; border-radius: 10px; }}"
        )


class ReportsCard(QFrame):
    def __init__(self, parent=None):
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
        chips = [
            ("Concentrado Incidencias\nProfesor de Asignatura", "#e8f0fe"),
            ("Concentrado Incidencias\nAdministrativo y PTC", "#e6f7ec"),
            ("Control Quincenal\nProfesor de Asignatura", "#e8f0fe"),
            ("Control Quincenal\nAdministrativos y PTC", "#fdece0"),
        ]
        for i, (text, color) in enumerate(chips):
            grid.addWidget(ReportChip(text, color), i // 2, i % 2)
        layout.addLayout(grid)

        all_btn = QPushButton("📄  Ver todos los reportes")
        all_btn.setObjectName("secondaryButton")
        all_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(all_btn)


TABLE_DATA = [
    ("01/10/2024", "María González López", "Profesor de Asignatura", "07:05", "14:00", "00:05", "-", "-", "-"),
    ("01/10/2024", "Juan Pérez Ramírez", "Administrativo", "08:00", "16:00", "-", "-", "-", "-"),
    ("01/10/2024", "Ana Laura Martínez", "Profesor de Asignatura", "07:15", "14:05", "00:15", "-", "-", "Llegó tarde por tráfico"),
    ("01/10/2024", "Carlos Hernández Ortiz", "PTC", "08:00", "16:00", "-", "✓", "-", "Permiso personal"),
    ("02/10/2024", "Lucía Fernández Ruiz", "Administrativo", "08:00", "16:00", "-", "-", "-", "-"),
    ("02/10/2024", "Miguel Ángel Torres", "Profesor de Asignatura", "07:00", "14:00", "-", "-", "-", "-"),
    ("02/10/2024", "Sandra Chávez Molina", "PTC", "-", "-", "-", "-", "✓", "Falta injustificada"),
    ("02/10/2024", "Roberto Díaz Sánchez", "Administrativo", "08:10", "16:00", "00:10", "-", "-", "-"),
]

TIPO_COLORS = {
    "Profesor de Asignatura": ("#e8f0fe", "#2563eb"),
    "Administrativo": ("#e6f7ec", "#16a34a"),
    "PTC": ("#f3e8fd", "#7c3aed"),
}


class TypeBadge(QWidget):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        bg, fg = TIPO_COLORS.get(text, ("#eee", "#333"))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"background-color: {bg}; color: {fg}; border-radius: 8px; padding: 3px 10px;"
            f"font-size: 10px; font-weight: 600;"
        )
        layout.addWidget(lbl)
        layout.addStretch()


class RecordsTable(QFrame):
    HEADERS = ["Fecha", "Empleado", "Tipo", "Entrada", "Salida", "Retardo", "Permiso", "Falta", "Observaciones", "Acciones"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 10)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        title = QLabel("📄  Registros de asistencia (vista preliminar)")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px; font-weight: 700;")
        header_row.addWidget(title)
        header_row.addStretch()

        filt_btn = QPushButton("▽  Filtros")
        filt_btn.setObjectName("secondaryButton")
        filt_btn.setCursor(Qt.PointingHandCursor)
        search = QLineEdit()
        search.setPlaceholderText("🔍  Buscar en registros...")
        search.setObjectName("searchBox")
        search.setFixedWidth(200)
        header_row.addWidget(filt_btn)
        header_row.addWidget(search)
        layout.addLayout(header_row)

        table = QTableWidget(len(TABLE_DATA), len(self.HEADERS))
        table.setHorizontalHeaderLabels(self.HEADERS)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setShowGrid(False)
        table.setAlternatingRowColors(False)
        table.horizontalHeader().setStretchLastSection(False)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(8, QHeaderView.Stretch)
        table.verticalHeader().setDefaultSectionSize(40)
        table.setColumnWidth(9, 60)

        for row, record in enumerate(TABLE_DATA):
            fecha, empleado, tipo, entrada, salida, retardo, permiso, falta, obs = record
            table.setItem(row, 0, QTableWidgetItem(fecha))
            table.setItem(row, 1, QTableWidgetItem(empleado))
            table.setCellWidget(row, 2, TypeBadge(tipo))
            table.setItem(row, 3, QTableWidgetItem(entrada))
            table.setItem(row, 4, QTableWidgetItem(salida))

            retardo_item = QTableWidgetItem(retardo)
            if retardo != "-":
                retardo_item.setForeground(QColor(COLORS["orange"]))
                f = QFont()
                f.setBold(True)
                retardo_item.setFont(f)
            table.setItem(row, 5, retardo_item)

            permiso_item = QTableWidgetItem(permiso)
            if permiso == "✓":
                permiso_item.setForeground(QColor(COLORS["blue"]))
            table.setItem(row, 6, permiso_item)

            falta_item = QTableWidgetItem(falta)
            if falta == "✓":
                falta_item.setForeground(QColor(COLORS["red"]))
            table.setItem(row, 7, falta_item)

            table.setItem(row, 8, QTableWidgetItem(obs))
            table.setItem(row, 9, QTableWidgetItem("⋯"))
            table.item(row, 9).setTextAlignment(Qt.AlignCenter)

        layout.addWidget(table)


class DashboardContent(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        # Stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)
        suffix = "vs. quincena anterior"
        cards = [
            StatCard("⏱", "Retardos", 12, "+3%", True, "#fdece0", delta_suffix=suffix),
            StatCard("📄", "Permisos", 8, "-11%", False, "#e8f0fe", delta_suffix=suffix),
            StatCard("✕", "Faltas", 5, "-38%", False, "#fde8e8", delta_suffix=suffix),
            StatCard("👥", "Asistencias", 186, "+6%", True, "#e6f7ec", delta_suffix=suffix),
        ]
        left_col = QVBoxLayout()
        left_col.setSpacing(16)
        top_stats = QHBoxLayout()
        top_stats.setSpacing(16)
        for c in cards:
            top_stats.addWidget(c)
        left_col.addLayout(top_stats)

        stats_row.addLayout(left_col, 2)
        stats_row.addWidget(IncidenciasChartCard(), 2)
        layout.addLayout(stats_row)

        # Middle row: upload / process / reports
        mid_row = QHBoxLayout()
        mid_row.setSpacing(16)
        mid_row.addWidget(UploadCard(), 1)
        mid_row.addWidget(ProcessCard(), 1)
        mid_row.addWidget(ReportsCard(), 1)
        layout.addLayout(mid_row)

        # Table
        layout.addWidget(RecordsTable())


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
        right.addWidget(self.topbar)

        self.pages = QStackedWidget()
        self.page_indices = {}
        page_factories = {
            0: DashboardContent,
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

    def _show_page(self, nav_index):
        self.pages.setCurrentIndex(self.page_indices[nav_index])
        scroll = self.pages.currentWidget()
        page = scroll.widget()
        if hasattr(page, "refresh"):
            page.refresh()


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
    color: {COLORS['text_primary']};
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
