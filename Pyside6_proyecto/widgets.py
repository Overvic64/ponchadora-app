"""Widgets reutilizables entre pantallas."""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from iconos import etiqueta_icono
from theme import COLORS, TONOS


def con_sombra(widget, desenfoque: int = 18, baja: int = 3, opacidad: int = 16):
    """Sombra muy suave bajo una tarjeta. Solo para tarjetas chicas: con tablas grandes dentro haria lento el dibujo."""
    efecto = QGraphicsDropShadowEffect(widget)
    efecto.setBlurRadius(desenfoque)
    efecto.setOffset(0, baja)
    efecto.setColor(QColor(17, 24, 39, opacidad))
    widget.setGraphicsEffect(efecto)
    return widget


class Sparkline(QWidget):
    """Mini grafica de linea con relleno suave: la tendencia de un vistazo, sin ejes."""

    def __init__(self, valores: list[float], color: str, parent=None):
        super().__init__(parent)
        self._valores = valores
        self._color = QColor(color)
        self.setFixedHeight(46)

    def paintEvent(self, _evento):
        n = len(self._valores)
        if n < 2:
            return
        ancho, alto = self.width(), self.height()
        minimo, maximo = min(self._valores), max(self._valores)
        rango = (maximo - minimo) or 1  # serie plana: linea recta a media altura
        puntos = [
            QPointF(i * ancho / (n - 1), alto - 4 - (v - minimo) / rango * (alto - 10) if maximo != minimo else alto / 2)
            for i, v in enumerate(self._valores)
        ]
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.Antialiasing)
        relleno = QPainterPath(QPointF(0, alto))
        for punto in puntos:
            relleno.lineTo(punto)
        relleno.lineTo(QPointF(ancho, alto))
        degradado = QLinearGradient(0, 0, 0, alto)
        arriba = QColor(self._color)
        arriba.setAlpha(60)
        abajo = QColor(self._color)
        abajo.setAlpha(0)
        degradado.setColorAt(0, arriba)
        degradado.setColorAt(1, abajo)
        pintor.fillPath(relleno, QBrush(degradado))
        linea = QPainterPath(puntos[0])
        for punto in puntos[1:]:
            linea.lineTo(punto)
        pintor.setPen(QPen(self._color, 2))
        pintor.drawPath(linea)


class SectionTitle(QWidget):
    """Titulo de tarjeta: icono de linea + texto (sin emojis)."""

    def __init__(self, icono_nombre: str, texto: str, parent=None):
        super().__init__(parent)
        fila = QHBoxLayout(self)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(8)
        fila.addWidget(etiqueta_icono(icono_nombre, 16, COLORS["text_secondary"]))
        self.label = QLabel(texto)
        self.label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px; font-weight: 600;")
        fila.addWidget(self.label)
        fila.addStretch()

    def setText(self, texto: str):
        self.label.setText(texto)


class StatCard(QFrame):
    """Cifra con su variacion y, si hay historial, su tendencia. `tone` colorea solo el icono y la linea."""

    def __init__(self, icon, title, value, delta=None, delta_up=True, tone="neutral",
                 delta_suffix="", serie=None, parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        con_sombra(self)
        color, _ = TONOS.get(tone, TONOS["neutral"])

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 14)
        outer.setSpacing(6)

        top_row = QHBoxLayout()
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px; font-weight: 500;")
        top_row.addWidget(title_lbl)
        top_row.addStretch()
        top_row.addWidget(etiqueta_icono(icon, 18, color))
        outer.addLayout(top_row)

        fila_valor = QHBoxLayout()
        fila_valor.setSpacing(8)
        value_lbl = QLabel(str(value))
        value_lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 28px; font-weight: 700;")
        fila_valor.addWidget(value_lbl)
        if delta is not None:
            # Solo informa el cambio: subir o bajar no es bueno ni malo por si solo, asi que no lleva verde ni rojo.
            pildora = QLabel(delta)
            pildora.setStyleSheet(
                f"background-color: {COLORS['blue_bg']}; color: {COLORS['blue']}; border-radius: 9px; "
                "padding: 2px 8px; font-size: 11px; font-weight: 600;"
            )
            pildora.setToolTip(f"{delta} {delta_suffix}".strip())
            fila_valor.addWidget(pildora, alignment=Qt.AlignBottom)
        fila_valor.addStretch()
        outer.addLayout(fila_valor)

        if serie:
            outer.addWidget(Sparkline(serie, color))
        else:
            outer.addStretch()


def size_table_to_contents(table, max_visible_rows=None):
    """QTableWidget no crece con el numero de filas dentro de un layout con
    stretch; esto fija su alto minimo segun el contenido real para que se
    vean todas las filas sin necesidad de scroll interno."""
    row_count = table.rowCount()
    visible_rows = min(row_count, max_visible_rows) if max_visible_rows else row_count
    row_height = table.verticalHeader().defaultSectionSize()
    header_height = table.horizontalHeader().height() or 32
    # Altura real de cada fila: algunas tablas ajustan filas de varios renglones.
    filas = sum(table.rowHeight(r) for r in range(visible_rows))
    total = header_height + filas + 6
    table.setMinimumHeight(max(total, header_height + row_height))
