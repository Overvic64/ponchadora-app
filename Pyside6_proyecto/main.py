"""
Sistema de Control de Asistencia y Ponchador
"""
import sys
import tempfile
from pathlib import Path

from PySide6.QtCharts import QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView, QValueAxis
from PySide6.QtCore import QEvent, QObject, QSize, Qt, Signal
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
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    from store import store  # se conecta a Supabase al importarse
except Exception as error:  # noqa: BLE001 - sin .env, sin internet, claves malas...
    _app = QApplication(sys.argv)
    QMessageBox.critical(
        None,
        "No se pudo conectar a Supabase",
        f"{error}\n\nRevisa el archivo .env (SUPABASE_URL y SUPABASE_KEY) y tu conexión a internet.",
    )
    sys.exit(1)

from asistencias_view import AsistenciasView  # noqa: E402
from configuracion_view import ConfiguracionView  # noqa: E402
from iconos import con_icono, etiqueta_icono, icono  # noqa: E402
from importar_view import ImportarExcelView  # noqa: E402
from incidencias_view import IncidenciasView  # noqa: E402
from limpieza_view import LimpiezaView  # noqa: E402
from personas_view import PersonasView  # noqa: E402
from report_data import etiqueta_quincena, quincenas_disponibles, resumen_global  # noqa: E402
from reportes_view import ReportesView  # noqa: E402
from theme import COLORS  # noqa: E402
from widgets import SectionTitle, StatCard, con_sombra  # noqa: E402

NAV_ITEMS = [
    ("inicio", "Inicio"),
    ("importar", "Importar Excel"),
    ("limpieza", "Limpieza de registros"),
    ("asistencias", "Asistencias"),
    ("incidencias", "Incidencias"),
    ("reportes", "Reportes"),
    ("profesores", "Profesores"),
    ("administrativos", "Administrativos"),
    ("configuracion", "Configuración"),
]


# Una linea por pantalla: para que cualquiera entienda para que sirve sin preguntar.
PAGE_HELP = [
    "Resumen de la quincena y por dónde seguir",
    "Sube el Excel del lector y revísalo antes de guardarlo",
    "Historial de archivos importados y registros depurados",
    "Entradas y salidas de cada persona, con filtros",
    "Permisos, comisiones y retardos por justificar",
    "Reportes oficiales F01, F02 y F05 listos para exportar",
    "Profesores de tiempo completo y de asignatura",
    "Personal administrativo",
    "Edificios y horarios de los turnos",
]

PAGINAS_CON_QUINCENA = {0, 3, 4}  # Inicio, Asistencias, Incidencias


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
        self.setFixedWidth(236)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 22, 14, 16)
        layout.setSpacing(4)

        logo_row = QHBoxLayout()
        logo_row.setContentsMargins(8, 0, 8, 22)
        logo_row.setSpacing(10)
        logo_row.addWidget(etiqueta_icono("logo", 26, COLORS["primary"]))
        logo_text = QLabel("Control de Asistencia")
        logo_text.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 14px; font-weight: 700; background: transparent;"
        )
        logo_row.addWidget(logo_text)
        logo_row.addStretch()
        layout.addLayout(logo_row)

        self.nav_buttons = []
        for i, (nombre_icono, text) in enumerate(NAV_ITEMS):
            btn = QPushButton(f"  {text}")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setObjectName("navButton")
            btn.setIconSize(QSize(18, 18))
            btn.setProperty("icono", nombre_icono)
            btn.clicked.connect(lambda _, b=btn, idx=i: self._select(b, idx))
            layout.addWidget(btn)
            self.nav_buttons.append(btn)
        self._marcar(self.nav_buttons[0])

        layout.addStretch()

        footer = QLabel("Versión 1.0.0")
        footer.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; padding: 0 10px; background: transparent;")
        layout.addWidget(footer)

    def _marcar(self, selected_btn):
        for btn in self.nav_buttons:
            active = btn is selected_btn
            btn.setChecked(active)
            btn.setProperty("active", active)
            btn.setIcon(icono(btn.property("icono"), COLORS["primary"] if active else COLORS["text_secondary"]))
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _select(self, selected_btn, index):
        self._marcar(selected_btn)
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
        layout.setContentsMargins(28, 0, 28, 0)
        layout.setSpacing(14)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar empleado")
        self.search.setObjectName("searchBox")
        self.search.setFixedWidth(340)
        self.search.addAction(icono("buscar"), QLineEdit.LeadingPosition)
        self.search.returnPressed.connect(lambda: self.busqueda.emit(self.search.text().strip()))
        layout.addWidget(self.search)

        layout.addStretch()

        self.quincena_combo = QComboBox()
        self.quincena_combo.setObjectName("quincenaBox")
        self.quincena_combo.setFixedWidth(310)
        self.quincena_combo.setIconSize(QSize(16, 16))
        self.quincena_combo.currentIndexChanged.connect(self._on_index_changed)
        layout.addWidget(self.quincena_combo)

        avatar = QFrame()
        avatar.setFixedSize(36, 36)
        avatar.setStyleSheet(f"background-color: {COLORS['accent_soft']}; border-radius: 18px; border: none;")
        avatar_layout = QHBoxLayout(avatar)
        avatar_layout.setContentsMargins(0, 0, 0, 0)
        avatar_layout.addWidget(etiqueta_icono("usuario", 18, COLORS["primary"]), alignment=Qt.AlignCenter)
        user_box = QVBoxLayout()
        user_box.setSpacing(0)
        user_box.addStretch()
        name = QLabel("Admin")
        name.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px; font-weight: 600;")
        role = QLabel("Administrador")
        role.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        user_box.addWidget(name)
        user_box.addWidget(role)
        user_box.addStretch()

        user_row = QHBoxLayout()
        user_row.setSpacing(10)
        user_row.addWidget(avatar)
        user_row.addLayout(user_box)
        layout.addLayout(user_row)

        self.set_quincenas(quincenas_disponibles())

    def mostrar_selector_quincena(self, visible: bool):
        self.quincena_combo.setVisible(visible)

    def quincena_actual(self) -> tuple[int, int, str] | None:
        index = self.quincena_combo.currentIndex()
        return self._quincenas[index] if 0 <= index < len(self._quincenas) else None

    def set_quincenas(self, quincenas: list[tuple[int, int, str]]):
        """Recarga la lista conservando la quincena elegida. Si esa quincena
        ya no existe, cae en la mas reciente y avisa a las pantallas para que
        no se queden mostrando un periodo distinto al del selector."""
        previa = self.quincena_actual()
        self._quincenas = quincenas
        calendario = icono("calendario")
        self.quincena_combo.blockSignals(True)
        self.quincena_combo.clear()
        if not quincenas:
            self.quincena_combo.addItem(calendario, "Sin asistencias importadas")
        else:
            for anio, mes, mitad in quincenas:
                self.quincena_combo.addItem(calendario, f"Quincena {etiqueta_quincena(anio, mes, mitad)}")
            index = quincenas.index(previa) if previa in quincenas else len(quincenas) - 1
            self.quincena_combo.setCurrentIndex(index)
        self.quincena_combo.blockSignals(False)
        nueva = self.quincena_actual()
        if previa is not None and nueva is not None and nueva != previa:
            self.quincena_changed.emit(nueva)

    def _on_index_changed(self, index):
        if 0 <= index < len(self._quincenas):
            self.quincena_changed.emit(self._quincenas[index])


class PageHeader(QWidget):
    """Titulo grande de la pantalla y una linea que explica para que sirve (debajo de la barra superior)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        caja = QVBoxLayout(self)
        caja.setContentsMargins(28, 20, 28, 4)
        caja.setSpacing(2)
        self.title = QLabel("")
        self.title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 24px; font-weight: 700;")
        self.subtitle = QLabel("")
        self.subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        caja.addWidget(self.title)
        caja.addWidget(self.subtitle)

    def set_titulo(self, texto: str, ayuda: str = ""):
        self.title.setText(texto)
        self.subtitle.setText(ayuda)


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
    view.setFixedHeight(250)  # sin esto cambia de tamano al redibujarse con la ventana abierta y estira el bloque
    return view


class IncidenciasChartCard(QFrame):
    def __init__(self, datos, parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.setSpacing(8)

        layout.addWidget(SectionTitle("grafica", "Incidencias por quincena"))
        layout.addWidget(_make_chart(datos))


class WorkflowCard(QFrame):
    """Los tres pasos de siempre, como botones: el usuario nuevo sabe por donde empezar."""

    PASOS = [
        ("importar", "Importa las ponchadas", "Sube el Excel del lector biométrico", 1),
        ("incidencias", "Revisa retardos y faltas", "Justifica permisos y cambios de turno", 4),
        ("reportes", "Exporta los reportes", "F01, F02 y F05 listos para imprimir", 5),
    ]

    def __init__(self, navigate, parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        con_sombra(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        layout.addWidget(SectionTitle("lista", "Cómo trabajar cada quincena"))
        for numero, (icono_nombre, titulo, descripcion, destino) in enumerate(self.PASOS, start=1):
            paso = QPushButton()
            paso.setObjectName("pasoButton")
            paso.setMinimumHeight(64)
            paso.setCursor(Qt.PointingHandCursor)
            paso.clicked.connect(lambda _, d=destino: navigate(d))
            fila = QHBoxLayout(paso)
            fila.setContentsMargins(12, 10, 12, 10)
            fila.setSpacing(12)
            numero_lbl = QLabel(str(numero))
            numero_lbl.setFixedSize(30, 30)
            numero_lbl.setAlignment(Qt.AlignCenter)
            numero_lbl.setStyleSheet(
                f"background-color: {COLORS['accent_soft']}; color: {COLORS['primary']}; border-radius: 15px; "
                "font-size: 13px; font-weight: 600;"
            )
            caja = QVBoxLayout()
            caja.setSpacing(0)
            t = QLabel(titulo)
            t.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px; font-weight: 600; background: transparent;")
            d = QLabel(descripcion)
            d.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; background: transparent;")
            caja.addWidget(t)
            caja.addWidget(d)
            fila.addWidget(numero_lbl)
            fila.addLayout(caja, 1)
            fila.addWidget(etiqueta_icono(icono_nombre, 20, COLORS["accent"]))
            layout.addWidget(paso)
        layout.addStretch()


class ProcessCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        con_sombra(self)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(18, 16, 18, 16)
        self._layout.setSpacing(14)

        self._layout.addWidget(SectionTitle("lista", "Pendientes de configuración"))

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

        # Los pasos si son una secuencia (importar, clasificar, asignar turno): hecho = palomita, pendiente = su numero.
        if done:
            badge = QFrame()
            badge.setFixedSize(26, 26)
            badge.setStyleSheet(f"background-color: {COLORS['green_bg']}; border-radius: 13px; border: none;")
            badge_layout = QHBoxLayout(badge)
            badge_layout.setContentsMargins(0, 0, 0, 0)
            badge_layout.addWidget(etiqueta_icono("hecho", 14, COLORS["green"]), alignment=Qt.AlignCenter)
        else:
            badge = QLabel(str(index))
            badge.setFixedSize(26, 26)
            badge.setAlignment(Qt.AlignCenter)
            badge.setStyleSheet(
                f"background-color: {COLORS['hover']}; color: {COLORS['text_secondary']}; "
                f"border: 1px solid {COLORS['border_strong']}; border-radius: 13px; font-size: 12px; font-weight: 600;"
            )
        row_layout.addWidget(badge)

        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        t = QLabel(title)
        t.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px; font-weight: 600;")
        d = QLabel(desc)
        d.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
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
    def __init__(self, title, on_click, parent=None):
        super().__init__(parent)
        self.setObjectName("reportChip")
        self.setCursor(Qt.PointingHandCursor)
        self._on_click = on_click
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)

        icon = etiqueta_icono("archivo", 18, COLORS["text_secondary"])
        label = QLabel(title)
        label.setWordWrap(True)
        label.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 11px; font-weight: 600; background: transparent;"
        )
        arrow = etiqueta_icono("siguiente", 14, COLORS["text_muted"])

        layout.addWidget(icon)
        layout.addWidget(label, 1)
        layout.addWidget(arrow)

        self.setStyleSheet(
            f"#reportChip {{ background-color: {COLORS['card_bg']}; border: 1px solid {COLORS['border']}; "
            f"border-radius: 8px; }} #reportChip:hover {{ background-color: {COLORS['hover']}; }}"
        )

    def mousePressEvent(self, event):
        self._on_click()
        super().mousePressEvent(event)


class ReportsCard(QFrame):
    CHIPS = [
        ("Concentrado Incidencias\nAdministrativo y PTC", "F05"),
        ("Control Quincenal\nProfesor de Asignatura", "F02"),
        ("Control Quincenal\nAdministrativos y PTC", "F01"),
    ]

    def __init__(self, navigate, parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        con_sombra(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        layout.addWidget(SectionTitle("reportes", "Reportes disponibles"))

        grid = QGridLayout()
        grid.setSpacing(10)
        for i, (text, clave) in enumerate(self.CHIPS):
            chip = ReportChip(text, lambda c=clave: navigate(5, c))
            grid.addWidget(chip, i, 0)
        layout.addLayout(grid)

        all_btn = con_icono(QPushButton("Ver todos los reportes"), "reportes")
        all_btn.setObjectName("secondaryButton")
        all_btn.setCursor(Qt.PointingHandCursor)
        all_btn.clicked.connect(lambda: navigate(5))
        layout.addWidget(all_btn)


TIPO_COLORS = {
    "Administrativo": (COLORS["green_bg"], COLORS["green"]),
    "Profesor de Tiempo Completo": (COLORS["purple_bg"], COLORS["purple"]),
    "Profesor de Asignatura": (COLORS["blue_bg"], COLORS["blue"]),
}


class TypeBadge(QWidget):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        bg, fg = TIPO_COLORS.get(text, (COLORS["hover"], COLORS["text_secondary"]))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        lbl = QLabel(text or "Sin clasificar")
        lbl.setStyleSheet(
            f"background-color: {bg}; color: {fg}; border-radius: 10px; padding: 3px 10px;"
            f"font-size: 11px; font-weight: 500;"
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
        header_row.addWidget(SectionTitle("reloj", "Últimas ponchadas registradas"))
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
        self._layout.setContentsMargins(28, 16, 28, 28)
        self._layout.setSpacing(18)

        self._stats_row = QHBoxLayout()  # cuatro cifras con su tendencia
        self._stats_row.setSpacing(16)
        self._layout.addLayout(self._stats_row)

        self._coverage = QFrame()
        self._coverage.setStyleSheet(
            f"background-color: {COLORS['orange_bg']}; border: none; border-radius: 8px;"
        )
        coverage_row = QHBoxLayout(self._coverage)
        coverage_row.setContentsMargins(14, 10, 14, 10)
        coverage_row.setSpacing(10)
        coverage_row.addWidget(etiqueta_icono("aviso", 16, COLORS["orange"]))
        self._coverage_label = QLabel("")
        self._coverage_label.setWordWrap(True)
        self._coverage_label.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 12px; background: transparent;"
        )
        coverage_row.addWidget(self._coverage_label, 1)
        self._coverage.setVisible(False)
        self._layout.addWidget(self._coverage)

        grafica_row = QHBoxLayout()
        grafica_row.setSpacing(16)
        self._chart_container = QVBoxLayout()
        grafica_row.addLayout(self._chart_container, 2)
        grafica_row.addWidget(WorkflowCard(self.navigate), 1)
        self._layout.addLayout(grafica_row)

        mid_row = QHBoxLayout()
        mid_row.setSpacing(16)
        self.process_card = ProcessCard()
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
        _clear_layout(self._chart_container)

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

        ultimas = quincenas[-4:] if quincenas else []
        datos_chart = [(_etiqueta_corta(*q), resumen(q)) for q in ultimas]

        cards_def = [
            ("personas", "Asistencias", "asistencias", "blue"),
            ("retardo", "Retardos", "retardos", "orange"),
            ("falta", "Faltas", "faltas", "red"),
            ("permiso", "Permisos", "permisos", "blue"),
        ]
        for icon, titulo, clave, tono in cards_def:
            delta_text, delta_up = delta(clave)
            serie = [float(r[clave]) for _, r in datos_chart]
            self._stats_row.addWidget(
                StatCard(icon, titulo, actual[clave], delta_text, delta_up, tono, delta_suffix=suffix, serie=serie)
            )

        faltantes = actual["dias_totales"] - actual["dias_con_datos"]
        if actual_q and faltantes > 0:
            self._coverage_label.setText(
                f"{faltantes} de {actual['dias_totales']} días hábiles de esta quincena todavía no tienen "
                "ninguna ponchada importada. No se cuentan como falta; solo se excluyen del total."
            )
            self._coverage.setVisible(True)
        else:
            self._coverage.setVisible(False)

        self._chart_container.addWidget(IncidenciasChartCard(datos_chart))

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

        self.encabezado = PageHeader()
        right.addWidget(self.encabezado)
        self._titular(0)

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
        for i in range(len(NAV_ITEMS)):
            page = page_factories[i]()
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

    def _titular(self, nav_index):
        titulo = "Bienvenido, Admin" if nav_index == 0 else NAV_ITEMS[nav_index][1]
        self.encabezado.set_titulo(titulo, PAGE_HELP[nav_index])

    def _on_quincena_changed(self, quincena):
        self.dashboard.set_quincena(quincena)
        self.asistencias_page.set_quincena(quincena)
        self.incidencias_page.set_quincena(quincena)

    def _buscar_empleado(self, texto):
        self.asistencias_page.search_box.setText(texto)
        self.navigate(3)

    def _show_page(self, nav_index):
        self._titular(nav_index)
        # El selector de arriba solo manda en estas pantallas; en las demas (Reportes tiene el suyo) confunde.
        self.topbar.mostrar_selector_quincena(nav_index in PAGINAS_CON_QUINCENA)
        self.pages.setCurrentIndex(self.page_indices[nav_index])
        scroll = self.pages.currentWidget()
        page = scroll.widget()
        if hasattr(page, "refresh"):
            page.refresh()
        if nav_index == 0:
            self.topbar.set_quincenas(quincenas_disponibles())


def _recursos_estilo() -> dict[str, str]:
    """Imagenes que el QSS necesita por ruta (flecha de los desplegables, palomita de las casillas)."""
    carpeta = Path(tempfile.gettempdir()) / "ponchador_ui"
    carpeta.mkdir(exist_ok=True)
    rutas = {}
    for clave, nombre, color in (
        ("chevron", "caret-down", COLORS["text_secondary"]),
        ("chevron_up", "caret-up", COLORS["text_secondary"]),
        ("check", "check-bold", "#ffffff"),
    ):
        ruta = carpeta / f"{clave}.png"
        icono(nombre, color).pixmap(32, 32).save(str(ruta))
        rutas[clave] = ruta.as_posix()
    return rutas


def construir_estilos() -> str:
    """QSS de toda la aplicacion. Se arma despues de crear QApplication porque usa iconos."""
    img = _recursos_estilo()
    c = COLORS
    return f"""
QWidget {{
    font-family: 'Segoe UI';
    font-size: 12px;
    color: {c['text_primary']};
}}
QMainWindow {{
    background-color: {c['page_bg']};
}}
QScrollArea {{
    background-color: {c['page_bg']};
    border: none;
}}
DashboardContent, ImportarExcelView, LimpiezaView, AsistenciasView,
IncidenciasView, ReportesView, PersonasView, ConfiguracionView {{
    background-color: {c['page_bg']};
}}
QToolTip {{
    background-color: {c['primary']};
    color: white;
    border: none;
    padding: 5px 8px;
}}

/* Barra lateral */
#sidebar {{
    background-color: {c['sidebar_bg']};
    border: none;
    border-right: 1px solid {c['border']};
}}
QPushButton#navButton {{
    text-align: left;
    color: {c['sidebar_text']};
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 9px 12px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#navButton:hover {{
    background-color: {c['sidebar_bg_hover']};
    color: {c['sidebar_text_active']};
}}
QPushButton#navButton[active="true"] {{
    background-color: {c['sidebar_active']};
    color: {c['sidebar_text_active']};
    border-left: 3px solid {c['primary']};
    font-weight: 600;
}}

/* Pasos del Inicio */
QPushButton#pasoButton {{
    background-color: white;
    border: 1px solid {c['border']};
    border-radius: 10px;
    text-align: left;
}}
QPushButton#pasoButton:hover {{
    background-color: {c['accent_soft']};
    border-color: {c['accent']};
}}

/* Barra superior */
#topbar {{
    background-color: {c['topbar_bg']};
    border: none;
    border-bottom: 1px solid {c['border']};
}}

QLineEdit#searchBox {{
    background-color: {c['hover']};
    border: 2px solid transparent;
    border-radius: 10px;
    padding: 6px 10px;
}}
QLineEdit#searchBox:focus {{
    background-color: white;
    border: 2px solid {c['accent']};
}}

/* Campos */
QLineEdit, QComboBox, QDateEdit, QTimeEdit, QSpinBox {{
    background-color: white;
    color: {c['text_primary']};
    border: 1px solid {c['border_strong']};
    border-radius: 8px;
    padding: 7px 10px;
    font-size: 12px;
    selection-background-color: {c['accent_soft']};
    selection-color: {c['text_primary']};
}}
QDateEdit, QTimeEdit, QSpinBox {{
    padding: 5px 10px;
}}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTimeEdit:focus, QSpinBox:focus {{
    border: 2px solid {c['accent']};
    padding: 6px 9px;
}}
QDateEdit QLineEdit, QTimeEdit QLineEdit, QSpinBox QLineEdit, QComboBox QLineEdit {{
    border: none;
    padding: 0;
    background: transparent;
}}
QLineEdit::placeholder {{
    color: {c['text_muted']};
}}
QComboBox::drop-down, QDateEdit::drop-down {{
    border: none;
    width: 26px;
}}
QComboBox::down-arrow, QDateEdit::down-arrow {{
    image: url({img['chevron']});
    width: 12px;
    height: 12px;
}}
QTimeEdit::up-button, QSpinBox::up-button, QDateEdit::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    border: none;
    background: transparent;
}}
QTimeEdit::down-button, QSpinBox::down-button, QDateEdit::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    border: none;
    background: transparent;
}}
QTimeEdit::up-arrow, QSpinBox::up-arrow {{
    image: url({img['chevron_up']});
    width: 10px;
    height: 10px;
}}
QTimeEdit::down-arrow, QSpinBox::down-arrow {{
    image: url({img['chevron']});
    width: 10px;
    height: 10px;
}}
QComboBox QAbstractItemView {{
    background-color: white;
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    selection-background-color: {c['accent_soft']};
    selection-color: {c['text_primary']};
    outline: none;
    padding: 4px;
}}
QCalendarWidget QWidget {{
    background-color: white;
    color: {c['text_primary']};
}}
QCalendarWidget QToolButton {{
    color: {c['text_primary']};
}}
QCheckBox {{
    spacing: 8px;
    background: transparent;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {c['border_strong']};
    border-radius: 4px;
    background-color: white;
}}
QCheckBox::indicator:hover {{
    border-color: {c['accent']};
}}
QCheckBox::indicator:checked {{
    background-color: {c['accent']};
    border-color: {c['accent']};
    image: url({img['check']});
}}

/* Tarjetas */
QFrame#statCard {{
    background-color: {c['card_bg']};
    border: 1px solid {c['border']};
    border-radius: 10px;
}}
QFrame#dropZone {{
    border: 1px dashed {c['border_strong']};
    border-radius: 10px;
    background-color: #fafafa;
    padding: 22px;
}}

/* Botones */
QPushButton {{
    font-size: 12px;
}}
QPushButton#primaryButton {{
    background-color: {c['primary']};
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 12px;
    font-weight: 500;
}}
QPushButton#primaryButton:hover {{
    background-color: {c['primary_hover']};
}}
QPushButton#primaryButton:disabled {{
    background-color: {c['border_strong']};
}}
QPushButton#secondaryButton {{
    background-color: white;
    color: {c['text_primary']};
    border: 1px solid {c['border_strong']};
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 12px;
    font-weight: 500;
}}
QPushButton#secondaryButton:hover {{
    background-color: {c['hover']};
}}
QPushButton#secondaryButton:disabled {{
    color: {c['text_muted']};
    background-color: {c['page_bg']};
}}
QPushButton#tableButton {{
    background-color: white;
    color: {c['text_primary']};
    border: 1px solid {c['border_strong']};
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11px;
}}
QPushButton#tableButton:hover {{
    background-color: {c['hover']};
}}

/* Tablas */
QTableWidget {{
    border: none;
    background-color: white;
    color: {c['text_primary']};
    gridline-color: {c['border']};
    font-size: 12px;
    outline: none;
}}
QHeaderView::section {{
    background-color: #f1f5fa;
    color: {c['text_secondary']};
    border: none;
    border-bottom: 1px solid {c['border']};
    padding: 9px 10px;
    font-size: 11px;
    font-weight: 600;
    text-align: left;
}}
QTableWidget::item:hover {{
    background-color: #f8fafc;
}}
QTableWidget::item {{
    border-bottom: 1px solid #eef2f7;
    padding-left: 10px;
}}

/* Cuadros de dialogo */
QDialog, QMessageBox {{
    background-color: white;
}}
QDialog QLabel, QDialog QCheckBox {{
    color: {c['text_primary']};
    font-size: 12px;
    background: transparent;
}}
QDialog QScrollArea, QDialog QScrollArea > QWidget > QWidget {{
    background-color: white;
}}
QDialog QPushButton, QMessageBox QPushButton {{
    background-color: white;
    color: {c['text_primary']};
    border: 1px solid {c['border_strong']};
    border-radius: 8px;
    padding: 7px 18px;
    font-size: 12px;
    min-width: 64px;
}}
QDialog QPushButton:hover, QMessageBox QPushButton:hover {{
    background-color: {c['hover']};
}}
QDialog QPushButton:default, QMessageBox QPushButton:default {{
    background-color: {c['primary']};
    color: white;
    border: none;
}}

/* Barras de desplazamiento */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {c['border_strong']};
    border-radius: 3px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{
    background: {c['text_muted']};
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {c['border_strong']};
    border-radius: 3px;
    min-width: 32px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0;
    height: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}
"""


class AjusteTablas(QObject):
    """Los encabezados de las tablas quedan alineados a la izquierda, como su contenido (QSS no lo permite)."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Polish and isinstance(obj, QHeaderView):
            obj.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        return False


def main():
    app = QApplication(sys.argv)
    ajuste = AjusteTablas()
    app.installEventFilter(ajuste)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(construir_estilos())
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
