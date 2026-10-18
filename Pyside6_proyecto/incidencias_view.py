"""Pantalla 'Incidencias': captura manual de permisos, comisiones, incapacidades, etc.,
mas los retardos y faltas de la quincena elegida (calculados solos) con opcion
de justificarlos.

Lo capturado aqui se combina con la vista `reporte_asistencias` de Supabase
para resolver la clave final de cada dia en los reportes F01/F02/F05.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from PySide6.QtCore import QDate, Qt, QTime, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from report_data import business_days, etiqueta_quincena, generar_quincena, quincenas_disponibles
from store import TIPOS_INCIDENCIA, calcular_retardo, store
from iconos import con_icono
from theme import COLORS
from widgets import SectionTitle, size_table_to_contents

# Entrada/Salida Autorizada no aplican a un dia completo sin ponchar.
TIPOS_FALTA_JUSTIFICADA = ["P", "C", "I", "AM", "PS"]

MESES_CORTOS = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
DIAS_CORTOS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


def _fecha_corta(dia: date) -> str:
    return f"{dia.day} {MESES_CORTOS[dia.month]}"


def _rangos(dias: list[date], dias_habiles: list[date]) -> list[tuple[date, date, int]]:
    """Agrupa dias habiles seguidos: (desde, hasta, cuantos dias). "Seguidos" es
    en el calendario de dias habiles: un viernes y el lunes siguiente quedan en
    el mismo rango."""
    posicion = {d: i for i, d in enumerate(dias_habiles)}
    rangos: list[list] = []
    for dia in sorted(dias):
        if rangos and dia in posicion and posicion[dia] == posicion.get(rangos[-1][1], -2) + 1:
            rangos[-1][1] = dia
            rangos[-1][2] += 1
        else:
            rangos.append([dia, dia, 1])
    return [tuple(r) for r in rangos]


def _formato_rango(rango: tuple[date, date, int]) -> str:
    inicio, fin, _ = rango
    if inicio == fin:
        return _fecha_corta(inicio)
    if inicio.month == fin.month:
        return f"{inicio.day}–{fin.day} {MESES_CORTOS[fin.month]}"
    return f"{_fecha_corta(inicio)}–{_fecha_corta(fin)}"


class JustificarDialog(QDialog):
    """Elegir dias uno por uno, el tipo (si aplica) y el motivo."""

    def __init__(self, titulo: str, nombre: str, dias: list[tuple[date, str]],
                 tipos: list[str] | None, motivo_obligatorio: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setMinimumWidth(440)
        self._dias = dias
        self._motivo_obligatorio = motivo_obligatorio

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        encabezado = QLabel(nombre)
        encabezado.setStyleSheet("font-size: 14px; font-weight: 700;")
        layout.addWidget(encabezado)

        self.tipo_combo = None
        if tipos:
            layout.addWidget(QLabel("Tipo de incidencia:"))
            self.tipo_combo = QComboBox()
            for clave in tipos:
                self.tipo_combo.addItem(f"{clave} — {TIPOS_INCIDENCIA[clave]}", clave)
            layout.addWidget(self.tipo_combo)

        layout.addWidget(QLabel("Días a justificar:"))
        self.todos = QCheckBox("Seleccionar todos")
        self.todos.setStyleSheet("font-weight: 600;")
        self.todos.toggled.connect(self._marcar_todos)
        layout.addWidget(self.todos)

        contenedor = QWidget()
        lista = QVBoxLayout(contenedor)
        lista.setContentsMargins(12, 0, 0, 0)
        self.checks = []
        for _, texto in dias:
            check = QCheckBox(texto)
            lista.addWidget(check)
            self.checks.append(check)
        lista.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(contenedor)
        scroll.setMaximumHeight(min(260, 30 * len(dias) + 10))
        layout.addWidget(scroll)

        layout.addWidget(QLabel("Motivo:" if motivo_obligatorio else "Motivo (opcional):"))
        self.motivo = QLineEdit()
        self.motivo.setPlaceholderText("Ej. cita médica, tráfico, comisión de la dirección...")
        layout.addWidget(self.motivo)

        botones = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        botones.button(QDialogButtonBox.Save).setText("Guardar")
        botones.button(QDialogButtonBox.Cancel).setText("Cancelar")
        botones.accepted.connect(self._validar)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def _marcar_todos(self, marcado: bool):
        for check in self.checks:
            check.setChecked(marcado)

    def _validar(self):
        if not any(check.isChecked() for check in self.checks):
            QMessageBox.warning(self, "Sin días", "Marca al menos un día para justificar.")
            return
        if self._motivo_obligatorio and not self.motivo.text().strip():
            QMessageBox.warning(self, "Falta el motivo", "Escribe el motivo de la justificación.")
            return
        self.accept()

    def valores(self) -> tuple[str | None, list[date], str]:
        elegidos = [dia for (dia, _), check in zip(self._dias, self.checks) if check.isChecked()]
        tipo = self.tipo_combo.currentData() if self.tipo_combo else None
        return tipo, elegidos, self.motivo.text().strip()


class CambioTurnoDialog(QDialog):
    """Elegir los dias en que la persona entro a otra hora y cual era esa hora.

    Cada dia muestra en vivo cuantos minutos de retardo quedan con esa hora
    (ya descontada la tolerancia), para decidir despues si se justifican."""

    def __init__(self, nombre: str, dias: list[tuple[date, str, str]], tolerancia: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cambio de turno")
        self.setMinimumWidth(460)
        self._dias = dias  # (fecha, texto, entrada "HH:MM:SS")
        self._tolerancia = tolerancia

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        encabezado = QLabel(nombre)
        encabezado.setStyleSheet("font-size: 14px; font-weight: 700;")
        layout.addWidget(encabezado)

        layout.addWidget(QLabel("Hora de entrada de su nuevo horario:"))
        self.hora = QTimeEdit()
        self.hora.setDisplayFormat("HH:mm")
        primera = min(entrada for _, _, entrada in dias)
        self.hora.setTime(QTime(int(primera[:2]), 0))
        self.hora.timeChanged.connect(self._actualizar_textos)
        layout.addWidget(self.hora)

        ayuda = QLabel(f"Tolerancia: {tolerancia} min. El retardo se cuenta desde esa hora, no desde la de su turno.")
        ayuda.setWordWrap(True)
        ayuda.setStyleSheet("font-size: 11px;")
        layout.addWidget(ayuda)

        layout.addWidget(QLabel("Días con cambio de turno:"))
        self.todos = QCheckBox("Seleccionar todos")
        self.todos.setStyleSheet("font-weight: 600;")
        self.todos.toggled.connect(lambda marcado: [c.setChecked(marcado) for c in self.checks])
        layout.addWidget(self.todos)

        contenedor = QWidget()
        lista = QVBoxLayout(contenedor)
        lista.setContentsMargins(12, 0, 0, 0)
        self.checks = []
        for _ in dias:
            check = QCheckBox()
            lista.addWidget(check)
            self.checks.append(check)
        lista.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(contenedor)
        scroll.setMaximumHeight(min(260, 30 * len(dias) + 10))
        layout.addWidget(scroll)
        self._actualizar_textos()

        botones = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        botones.button(QDialogButtonBox.Save).setText("Guardar")
        botones.button(QDialogButtonBox.Cancel).setText("Cancelar")
        botones.accepted.connect(self._validar)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def _hora_texto(self) -> str:
        return self.hora.time().toString("HH:mm")

    def _actualizar_textos(self):
        hora = self._hora_texto()
        for (_, texto, entrada), check in zip(self._dias, self.checks):
            minutos = calcular_retardo(entrada, hora, self._tolerancia)
            check.setText(f"{texto} — {f'{minutos} min de retardo' if minutos else 'sin retardo'}")

    def _validar(self):
        if not any(check.isChecked() for check in self.checks):
            QMessageBox.warning(self, "Sin días", "Marca al menos un día con cambio de turno.")
            return
        self.accept()

    def valores(self) -> tuple[list[date], str]:
        elegidos = [dia for (dia, _, _), check in zip(self._dias, self.checks) if check.isChecked()]
        return elegidos, self._hora_texto()


class IncidenciasView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._quincena: tuple[int, int, str] | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)


        layout.addWidget(self._build_form_card())

        self.retardos_table, self.retardos_resumen, self.retardos_vacio, card = self._build_quincena_card(
            "retardo", "Retardos de la quincena",
            "Se calculan solos con las ponchadas (solo días hábiles del calendario). Si alguien cambió de horario "
            "esos días (ej. entró a las 10:00), usa \"Cambio de turno\": el retardo se recalcula desde su nueva "
            "hora de entrada, descontando la tolerancia (se marca con *). Con \"Justificar\" eliges qué días y el motivo; se "
            "registran como Entrada Autorizada (EA) y dejan de contar como retardo.",
            ["Empleado", "Turno", "Retardos", "Minutos", "Fechas (minutos)", ""],
            ancho_accion=250,
        )
        layout.addWidget(card)

        self.faltas_table, self.faltas_resumen, self.faltas_vacio, card = self._build_quincena_card(
            "falta", "Faltas de la quincena",
            "Días hábiles sin ninguna ponchada (no cuenta vacaciones, días inhábiles ni profesores de asignatura). "
            "Con \"Justificar\" eliges qué días, el tipo (permiso, comisión, incapacidad...) y el motivo.",
            ["Empleado", "Turno", "Días que faltó", "Fechas", ""],
        )
        layout.addWidget(card)

        layout.addWidget(self._build_cambios_card())
        layout.addWidget(self._build_registradas_card())
        layout.addStretch()

        self._refresh_table()
        self._refresh_cambios()
        self._refresh_quincena()

    # --- construccion -------------------------------------------------------
    def _build_form_card(self):
        form_card = QFrame()
        form_card.setObjectName("statCard")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(18, 16, 18, 16)
        form_layout.setSpacing(12)

        form_layout.addWidget(SectionTitle("agregar", "Nueva incidencia"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)

        self.maestro_combo = QComboBox()
        self._reload_maestros()

        self.tipo_combo = QComboBox()
        for clave, nombre in TIPOS_INCIDENCIA.items():
            self.tipo_combo.addItem(f"{clave} — {nombre}", clave)

        self.fecha_inicio = QDateEdit(QDate.currentDate())
        self.fecha_inicio.setCalendarPopup(True)
        self.fecha_fin = QDateEdit(QDate.currentDate())
        self.fecha_fin.setCalendarPopup(True)

        self.observaciones = QLineEdit()
        self.observaciones.setPlaceholderText("Observaciones (opcional)")

        grid.addWidget(self._label("Empleado"), 0, 0)
        grid.addWidget(self.maestro_combo, 1, 0)
        grid.addWidget(self._label("Tipo de incidencia"), 0, 1)
        grid.addWidget(self.tipo_combo, 1, 1)
        grid.addWidget(self._label("Fecha inicio"), 0, 2)
        grid.addWidget(self.fecha_inicio, 1, 2)
        grid.addWidget(self._label("Fecha fin"), 0, 3)
        grid.addWidget(self.fecha_fin, 1, 3)
        grid.addWidget(self._label("Observaciones"), 2, 0, 1, 4)
        grid.addWidget(self.observaciones, 3, 0, 1, 4)
        form_layout.addLayout(grid)

        save_row = QHBoxLayout()
        save_row.addStretch()
        save_btn = con_icono(QPushButton("Guardar incidencia"), "guardar", "#ffffff")
        save_btn.setObjectName("primaryButton")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self._guardar)
        save_row.addWidget(save_btn)
        form_layout.addLayout(save_row)
        return form_card

    def _build_quincena_card(self, icono_nombre: str, titulo: str, ayuda: str, headers: list[str], ancho_accion: int = 110):
        card = QFrame()
        card.setObjectName("statCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(10)

        header = QHBoxLayout()
        header.addWidget(SectionTitle(icono_nombre, titulo))
        header.addStretch()
        resumen = QLabel("")
        resumen.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; font-weight: 600;")
        header.addWidget(resumen)
        card_layout.addLayout(header)

        hint = QLabel(ayuda)
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px;")
        card_layout.addWidget(hint)

        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setShowGrid(False)
        ultima = len(headers) - 1
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(ultima - 1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(ultima, QHeaderView.Fixed)
        table.setColumnWidth(ultima, ancho_accion)
        table.verticalHeader().setDefaultSectionSize(34)
        # La columna de fechas puede ocupar varios renglones.
        table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        card_layout.addWidget(table)

        vacio = QLabel("")
        vacio.setAlignment(Qt.AlignCenter)
        vacio.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px; padding: 16px;")
        card_layout.addWidget(vacio)
        return table, resumen, vacio, card

    def _build_cambios_card(self):
        card = QFrame()
        card.setObjectName("statCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(10)

        card_layout.addWidget(SectionTitle("turno", "Cambios de turno registrados"))
        hint = QLabel("Días en que alguien entró a otra hora. Elimina uno para volver a contar su retardo con el turno normal.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px;")
        card_layout.addWidget(hint)

        self.cambios_table = QTableWidget(0, 4)
        self.cambios_table.setHorizontalHeaderLabels(["Empleado", "Fecha", "Hora de entrada", ""])
        self.cambios_table.verticalHeader().setVisible(False)
        self.cambios_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.cambios_table.setSelectionMode(QTableWidget.NoSelection)
        self.cambios_table.setShowGrid(False)
        self.cambios_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.cambios_table.verticalHeader().setDefaultSectionSize(34)
        card_layout.addWidget(self.cambios_table)

        self.cambios_vacio = QLabel("")
        self.cambios_vacio.setAlignment(Qt.AlignCenter)
        self.cambios_vacio.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px; padding: 16px;")
        card_layout.addWidget(self.cambios_vacio)
        return card

    def _build_registradas_card(self):
        list_card = QFrame()
        list_card.setObjectName("statCard")
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(18, 16, 18, 16)
        list_layout.setSpacing(10)

        list_layout.addWidget(SectionTitle("lista", "Incidencias registradas"))

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Empleado", "Tipo", "Desde", "Hasta", "Observaciones", ""])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(34)
        list_layout.addWidget(self.table)
        return list_card

    @staticmethod
    def _label(text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px; font-weight: 600;")
        return lbl

    @staticmethod
    def _numero(texto: str, color: str) -> QTableWidgetItem:
        item = QTableWidgetItem(texto)
        item.setTextAlignment(Qt.AlignCenter)
        item.setForeground(QColor(color))
        font = QFont()
        font.setBold(True)
        item.setFont(font)
        return item

    @staticmethod
    def _boton_justificar(callback) -> QPushButton:
        btn = QPushButton("Justificar")
        btn.setObjectName("tableButton")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(callback)
        return btn

    @staticmethod
    def _botones_retardo(cambio_callback, justificar_callback) -> QWidget:
        contenedor = QWidget()
        fila = QHBoxLayout(contenedor)
        fila.setContentsMargins(4, 2, 4, 2)
        fila.setSpacing(6)
        cambio = QPushButton("Cambio de turno")
        cambio.setObjectName("tableButton")
        cambio.setCursor(Qt.PointingHandCursor)
        cambio.clicked.connect(cambio_callback)
        fila.addWidget(cambio)
        fila.addWidget(IncidenciasView._boton_justificar(justificar_callback))
        return contenedor

    # --- quincena -----------------------------------------------------------
    def set_quincena(self, quincena: tuple[int, int, str]):
        self._quincena = quincena
        self._refresh_quincena()

    def _quincena_activa(self) -> tuple[int, int, str] | None:
        quincenas = quincenas_disponibles()
        if self._quincena in quincenas:
            return self._quincena
        return quincenas[-1] if quincenas else None

    def _justificado(self, maestro_id: str, fecha: date) -> bool:
        return any(
            i.maestro_id == maestro_id and i.fecha_inicio <= fecha <= i.fecha_fin for i in store.incidencias
        )

    def _refresh_quincena(self):
        quincena = self._quincena_activa()
        dias_habiles = business_days(*quincena) if quincena else []
        self._refresh_retardos(quincena, dias_habiles)
        self._refresh_faltas(quincena, dias_habiles)

    def _refresh_retardos(self, quincena, dias_habiles: list[date]):
        por_maestro: dict[str, list[dict]] = defaultdict(list)
        if dias_habiles:
            habiles = {d.isoformat() for d in dias_habiles}
            for f in store.reporte_asistencias(dias_habiles[0], dias_habiles[-1]):
                if (
                    f.get("estado") == "completo"
                    and (f.get("retardo_minutos_referencia") or 0) > 0
                    and f["fecha"] in habiles
                    and not self._justificado(f["maestro_id"], date.fromisoformat(f["fecha"]))
                ):
                    por_maestro[f["maestro_id"]].append(f)

        maestros_by_id = {m.id: m for m in store.maestros}
        filas = []
        for maestro_id, retardos in por_maestro.items():
            retardos.sort(key=lambda f: f["fecha"])
            maestro = maestros_by_id.get(maestro_id)
            if maestro:
                filas.append((maestro, retardos))
        filas.sort(key=lambda f: (-sum(r["retardo_minutos_referencia"] for r in f[1]), f[0].nombre.lower()))

        total = sum(len(r) for _, r in filas)
        minutos = sum(x["retardo_minutos_referencia"] for _, r in filas for x in r)
        etiqueta = etiqueta_quincena(*quincena) if quincena else "sin quincena"
        self.retardos_resumen.setText(
            f"{etiqueta}: {total} retardo(s) sin justificar, {minutos} min, {len(filas)} persona(s)"
        )

        self.retardos_table.setRowCount(len(filas))
        for row, (maestro, retardos) in enumerate(filas):
            fechas = ",  ".join(
                f"{_fecha_corta(date.fromisoformat(r['fecha']))} ({r['retardo_minutos_referencia']}"
                f"{'*' if r.get('cambio_turno') else ''})"
                for r in retardos
            )
            self.retardos_table.setItem(row, 0, QTableWidgetItem(maestro.nombre))
            self.retardos_table.setItem(row, 1, QTableWidgetItem((maestro.turno or "-").capitalize()))
            self.retardos_table.setItem(row, 2, self._numero(str(len(retardos)), COLORS["orange"]))
            minutos_persona = sum(r["retardo_minutos_referencia"] for r in retardos)
            self.retardos_table.setItem(row, 3, self._numero(str(minutos_persona), COLORS["orange"]))
            self.retardos_table.setItem(row, 4, QTableWidgetItem(fechas))
            self.retardos_table.setCellWidget(
                row,
                5,
                self._botones_retardo(
                    lambda _, m=maestro, r=retardos: self._cambio_turno(m, r),
                    lambda _, m=maestro, r=retardos: self._justificar_retardos(m, r),
                ),
            )

        self.retardos_table.setVisible(bool(filas))
        self.retardos_vacio.setText(
            "No hay retardos sin justificar en esta quincena." if quincena else "Todavía no hay asistencias importadas."
        )
        self.retardos_vacio.setVisible(not filas)
        size_table_to_contents(self.retardos_table)
        # Las alturas finales de fila se conocen hasta que Qt acomoda el layout.
        QTimer.singleShot(0, lambda: size_table_to_contents(self.retardos_table))

    def _refresh_faltas(self, quincena, dias_habiles: list[date]):
        filas = []
        if quincena and dias_habiles:
            _, celdas_por_maestro = generar_quincena(store.maestros, *quincena)
            maestros_by_id = {m.id: m for m in store.maestros}
            for maestro_id, celdas in celdas_por_maestro.items():
                dias = [c["dia"] for c in celdas if c["tipo"] == "falta"]
                if dias:
                    filas.append((maestros_by_id[maestro_id], dias))
            filas.sort(key=lambda f: (-len(f[1]), f[0].nombre.lower()))

        total = sum(len(dias) for _, dias in filas)
        etiqueta = etiqueta_quincena(*quincena) if quincena else "sin quincena"
        self.faltas_resumen.setText(f"{etiqueta}: {total} falta(s), {len(filas)} persona(s)")

        self.faltas_table.setRowCount(len(filas))
        for row, (maestro, dias) in enumerate(filas):
            fechas = ",  ".join(_formato_rango(r) for r in _rangos(dias, dias_habiles))
            self.faltas_table.setItem(row, 0, QTableWidgetItem(maestro.nombre))
            self.faltas_table.setItem(row, 1, QTableWidgetItem((maestro.turno or "-").capitalize()))
            self.faltas_table.setItem(row, 2, self._numero(str(len(dias)), COLORS["red"]))
            self.faltas_table.setItem(row, 3, QTableWidgetItem(fechas))
            self.faltas_table.setCellWidget(
                row, 4, self._boton_justificar(lambda _, m=maestro, d=dias: self._justificar_faltas(m, d))
            )

        self.faltas_table.setVisible(bool(filas))
        self.faltas_vacio.setText("No hay faltas en esta quincena." if quincena else "Todavía no hay asistencias importadas.")
        self.faltas_vacio.setVisible(not filas)
        size_table_to_contents(self.faltas_table)
        # Las alturas finales de fila se conocen hasta que Qt acomoda el layout.
        QTimer.singleShot(0, lambda: size_table_to_contents(self.faltas_table))

    # --- justificar ---------------------------------------------------------
    def _guardar_justificacion(self, maestro, dias: list[date], tipo: str, observaciones: str):
        """Guarda una incidencia por cada bloque de dias habiles seguidos."""
        dias_habiles = business_days(*self._quincena_activa())
        try:
            for inicio, fin, _ in _rangos(dias, dias_habiles):
                store.add_incidencia(
                    maestro_id=maestro.id,
                    fecha_inicio=inicio,
                    fecha_fin=fin,
                    tipo=tipo,
                    observaciones=observaciones,
                )
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(self, "Error al guardar", str(error))
        self._refresh_table()
        self._refresh_quincena()

    def _justificar_retardos(self, maestro, retardos: list[dict]):
        opciones = []
        for r in retardos:
            dia = date.fromisoformat(r["fecha"])
            opciones.append(
                (dia, f"{DIAS_CORTOS[dia.weekday()]} {_fecha_corta(dia)} — entró {(r.get('entrada') or '')[:8]} "
                      f"({r['retardo_minutos_referencia']} min)")
            )
        dialog = JustificarDialog("Justificar retardo", maestro.nombre, opciones, None, True, self)
        if dialog.exec() != QDialog.Accepted:
            return
        _, dias, motivo = dialog.valores()
        self._guardar_justificacion(maestro, dias, "EA", f"Retardo justificado: {motivo}")

    # --- cambio de turno ----------------------------------------------------
    def _tolerancia(self, maestro) -> int:
        turno = store.turnos.get(maestro.turno or "") or store.turnos.get("matutino") or {}
        return turno.get("tolerancia_minutos", 0)

    def _cambio_turno(self, maestro, retardos: list[dict]):
        if not store.cambios_turno_disponible:
            QMessageBox.warning(
                self,
                "Falta preparar la base de datos",
                "Para usar el cambio de turno corre una vez el archivo cambios_turno.sql en Supabase "
                "(SQL Editor) y vuelve a abrir la aplicación.",
            )
            return
        opciones = []
        for r in retardos:
            dia = date.fromisoformat(r["fecha"])
            entrada = (r.get("entrada") or "")[:8]
            if len(entrada) == 5:
                entrada += ":00"
            opciones.append((dia, f"{DIAS_CORTOS[dia.weekday()]} {_fecha_corta(dia)} — entró {entrada}", entrada))
        dialog = CambioTurnoDialog(maestro.nombre, opciones, self._tolerancia(maestro), self)
        if dialog.exec() != QDialog.Accepted:
            return
        dias, hora = dialog.valores()
        try:
            store.add_cambios_turno(maestro.id, dias, hora)
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(self, "Error al guardar", str(error))
        self._refresh_cambios()
        self._refresh_quincena()

    def _refresh_cambios(self):
        maestros_by_id = {str(m.id): m for m in store.maestros}
        cambios = sorted(store.cambios_turno.values(), key=lambda c: c.fecha, reverse=True)
        self.cambios_table.setRowCount(len(cambios))
        for row, cambio in enumerate(cambios):
            maestro = maestros_by_id.get(cambio.maestro_id)
            self.cambios_table.setItem(row, 0, QTableWidgetItem(maestro.nombre if maestro else "(empleado eliminado)"))
            self.cambios_table.setItem(
                row, 1, QTableWidgetItem(f"{DIAS_CORTOS[cambio.fecha.weekday()]} {cambio.fecha.strftime('%Y-%m-%d')}")
            )
            self.cambios_table.setItem(row, 2, QTableWidgetItem(cambio.hora_entrada))
            delete_btn = con_icono(QPushButton(), "eliminar")
            delete_btn.setObjectName("tableButton")
            delete_btn.setCursor(Qt.PointingHandCursor)
            delete_btn.setFixedSize(34, 28)
            delete_btn.clicked.connect(lambda _, cid=cambio.id: self._eliminar_cambio(cid))
            self.cambios_table.setCellWidget(row, 3, delete_btn)
        self.cambios_table.setVisible(bool(cambios))
        self.cambios_vacio.setText("Todavía no hay cambios de turno registrados.")
        self.cambios_vacio.setVisible(not cambios)
        size_table_to_contents(self.cambios_table)

    def _eliminar_cambio(self, cambio_id):
        confirm = QMessageBox.question(
            self, "Eliminar cambio de turno", "¿Eliminar este cambio de turno? El retardo se volverá a calcular con su turno normal."
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            store.remove_cambio_turno(cambio_id)
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo eliminar", str(error))
            return
        self._refresh_cambios()
        self._refresh_quincena()

    def _justificar_faltas(self, maestro, dias: list[date]):
        opciones = [(dia, f"{DIAS_CORTOS[dia.weekday()]} {_fecha_corta(dia)}") for dia in sorted(dias)]
        dialog = JustificarDialog("Justificar falta", maestro.nombre, opciones, TIPOS_FALTA_JUSTIFICADA, False, self)
        if dialog.exec() != QDialog.Accepted:
            return
        tipo, elegidos, motivo = dialog.valores()
        self._guardar_justificacion(maestro, elegidos, tipo, motivo or "Falta justificada")

    # --- incidencias capturadas ---------------------------------------------
    def _reload_maestros(self):
        self.maestro_combo.clear()
        for maestro in store.maestros:
            self.maestro_combo.addItem(f"{maestro.nombre} ({maestro.edificio})", maestro.id)

    def _guardar(self):
        if self.maestro_combo.count() == 0:
            QMessageBox.warning(self, "Sin empleados", "No hay empleados registrados todavía.")
            return
        maestro_id = self.maestro_combo.currentData()
        fecha_inicio = self.fecha_inicio.date().toPython()
        fecha_fin = self.fecha_fin.date().toPython()
        if fecha_fin < fecha_inicio:
            QMessageBox.warning(self, "Fechas inválidas", "La fecha fin no puede ser anterior a la fecha inicio.")
            return

        try:
            store.add_incidencia(
                maestro_id=maestro_id,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                tipo=self.tipo_combo.currentData(),
                observaciones=self.observaciones.text().strip(),
            )
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(self, "Error al guardar", str(error))
            return
        self.observaciones.clear()
        self._refresh_table()
        self._refresh_quincena()

    def _refresh_table(self):
        maestros_by_id = {m.id: m for m in store.maestros}
        self.table.setRowCount(len(store.incidencias))
        for row, incidencia in enumerate(store.incidencias):
            maestro = maestros_by_id.get(incidencia.maestro_id)
            nombre = maestro.nombre if maestro else "(empleado eliminado)"
            tipo_label = f"{incidencia.tipo} — {TIPOS_INCIDENCIA.get(incidencia.tipo, '')}"
            values = [
                nombre,
                tipo_label,
                incidencia.fecha_inicio.strftime("%Y-%m-%d"),
                incidencia.fecha_fin.strftime("%Y-%m-%d"),
                incidencia.observaciones,
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))

            delete_btn = con_icono(QPushButton(), "eliminar")
            delete_btn.setObjectName("tableButton")
            delete_btn.setCursor(Qt.PointingHandCursor)
            delete_btn.setFixedSize(34, 28)
            delete_btn.clicked.connect(lambda _, inc_id=incidencia.id: self._eliminar(inc_id))
            self.table.setCellWidget(row, 5, delete_btn)
        size_table_to_contents(self.table)

    def _eliminar(self, incidencia_id):
        confirm = QMessageBox.question(
            self, "Eliminar incidencia", "¿Eliminar esta incidencia? Esta acción no se puede deshacer."
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            store.remove_incidencia(incidencia_id)
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(self, "No se pudo eliminar", str(error))
            return
        self._refresh_table()
        self._refresh_quincena()

    def refresh(self):
        self._reload_maestros()
        self._refresh_table()
        self._refresh_cambios()
        self._refresh_quincena()
