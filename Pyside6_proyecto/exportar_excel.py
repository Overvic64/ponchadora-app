"""Exporta F01, F02 y F05 llenando los formatos oficiales de la carpeta `plantillas/`.

Se usa el propio Excel (por COM) en lugar de reescribir el archivo con openpyxl: los
formatos llevan logos en encabezados y dibujos que openpyxl descarta al guardar.
Excel copia la plantilla tal cual (logos, bordes, anchos, impresion) y solo se
escriben los datos; cuando hay mas personas que renglones se insertan renglones
con el formato de la plantilla.

Sin Excel instalado `excel_disponible()` regresa False y la pantalla de Reportes
usa su exportacion simple.
"""
from __future__ import annotations

import contextlib
import re
from collections.abc import Callable
from pathlib import Path

from report_data import MESES, _ultimo_dia_mes, resumen_concentrado

PLANTILLAS = Path(__file__).resolve().parent / "plantillas"
SIN_AREA = "SIN ÁREA ASIGNADA"

# Constantes de Excel
XL_DOWN = -4121
XL_UP = -4162
XL_TO_RIGHT = -4161
XL_CENTER = -4108
XL_PASTE_FORMATS = -4122
XL_UNDERLINE_NONE = -4142
XL_EDGE_LEFT, XL_EDGE_TOP, XL_EDGE_BOTTOM, XL_EDGE_RIGHT = 7, 8, 9, 10
XL_INSIDE_VERTICAL, XL_INSIDE_HORIZONTAL = 11, 12
XL_CONTINUOUS, XL_THIN, XL_MEDIUM = 1, 2, -4138
COLOR_LINEA = 0x8C8C8C  # gris de la rejilla (BGR)
ALTO_ARRIBA = 20  # puntos: renglon de horas y claves
ALTO_ABAJO = 15  # puntos: renglon de minutos de retardo
COLOR_BANDA_RETARDO = 0xDEF1FB  # ambar suave (BGR)
XL_SIN_RELLENO = -4142
XL_OPEN_XML_WORKBOOK = 51

# Pares de columnas (entrada/salida) con que viene cada plantilla.
F01_PARES = 12
F02_PARES_VISIBLES = 10
F02_PARES_PLANTILLA = 11  # el onceavo viene oculto (columnas W:X)

# F05 solo lista a quien tiene incidencias en la quincena (es un "concentrado de incidencias").
F05_SOLO_CON_INCIDENCIAS = True


def excel_disponible() -> bool:
    try:
        import winreg

        import win32com.client  # noqa: F401

        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Excel.Application\CLSID"))
        return True
    except Exception:  # noqa: BLE001
        return False


def quincena_texto(anio: int, mes: int, mitad: str) -> str:
    inicio, fin = (1, 15) if mitad == "primera" else (16, _ultimo_dia_mes(anio, mes))
    return f"{inicio} al {fin} de {MESES[mes]} de {anio}"


def _por_area(maestros) -> dict[str, list]:
    grupos: dict[str, list] = {}
    for maestro in sorted(maestros, key=lambda m: m.nombre.lower()):
        grupos.setdefault((maestro.area_carrera or "").strip() or SIN_AREA, []).append(maestro)
    return dict(sorted(grupos.items(), key=lambda kv: (kv[0] == SIN_AREA, kv[0].lower())))


def corte_entrada() -> str:
    """Hora que separa 'entrada' de 'salida' cuando solo hay una ponchada: el
    punto medio entre la entrada del matutino y la del vespertino (igual que la vista)."""
    from store import store

    def minutos(hora: str) -> int:
        return int(hora[:2]) * 60 + int(hora[3:5])

    try:
        medio = (minutos(store.turnos["matutino"]["hora_entrada"]) + minutos(store.turnos["vespertino"]["hora_entrada"])) // 2
    except (KeyError, ValueError):
        medio = 12 * 60
    return f"{medio // 60:02d}:{medio % 60:02d}"


# --- que se escribe en cada par Entrada/Salida --------------------------------
def _par(celda: dict, corte: str) -> tuple[str, str, bool]:
    """(entrada, salida, unido): lo que va en las dos celdas de un dia.

    El reporte solo detalla los dias con algo que reportar:
      * retardo -> entrada y salida de ese dia, y debajo de la entrada los minutos de retardo
        (ya descontada la tolerancia);
      * falta injustificada -> FI, FIE (sin entrada) o FIS (sin salida);
      * incidencia capturada -> su clave (I, AM, P, C, PS, EA, SA).
    Un dia normal queda en blanco. `unido`: la clave ocupa el dia completo (se combinan las dos celdas)."""
    tipo = celda["tipo"]
    if tipo == "completo" and celda["retardo_min"] > 0:
        return f"{celda['entrada']}\n{celda['retardo_min']} m", celda["salida"], False
    if tipo == "falta":
        return "FI", "", True
    if tipo == "incidencia":
        return celda["clave"], "", True
    if tipo == "incompleto":
        entrada = celda.get("entrada", "")
        estado = celda.get("estado")
        if estado == "sin_entrada":
            return "FIE", "", False
        if estado == "sin_salida":
            return "", "FIS", False
        if estado == "horas_iguales_por_revisar" and entrada:
            # Una sola ponchada: antes del corte es una entrada (falta la salida) y despues es una salida.
            return ("", "FIS", False) if entrada < corte else ("FIE", "", False)
    return "", "", False  # dia normal, sin_datos / no_aplica


# --- Excel ---------------------------------------------------------------------
class _Excel:
    """Instancia propia y oculta de Excel (no toca los libros que el usuario tenga abiertos)."""

    def __enter__(self):
        import pythoncom
        import win32com.client

        with contextlib.suppress(Exception):  # ya estaba inicializado en este hilo
            pythoncom.CoInitialize()
        self.app = win32com.client.DispatchEx("Excel.Application")
        self.app.Visible = False
        self.app.DisplayAlerts = False
        self.app.ScreenUpdating = False
        self.app.EnableEvents = False
        return self.app

    def __exit__(self, *_):
        with contextlib.suppress(Exception):
            self.app.Quit()
        return False


def _abrir(app, nombre: str):
    return app.Workbooks.Open(str(PLANTILLAS / nombre), 0, True)  # UpdateLinks=0, ReadOnly=True


def _guardar(wb, ruta) -> None:
    wb.SaveAs(str(Path(ruta).resolve()), XL_OPEN_XML_WORKBOOK)
    wb.Close(False)


def _nombre_hoja(area: str, usados: set[str]) -> str:
    base = re.sub(r"[\[\]:*?/\\]", " ", area).strip()[:29] or "Hoja"
    nombre, n = base, 2
    while nombre.lower() in usados:
        nombre = f"{base} {n}"
        n += 1
    usados.add(nombre.lower())
    return nombre


def _ajustar_filas(ws, primera: int, ultima: int, necesarias: int) -> int:
    """Deja la tabla `primera..ultima` con `necesarias` renglones (minimo 2),
    insertando o quitando renglones de en medio para conservar el formato del
    primero y del ultimo. Regresa la nueva ultima fila."""
    necesarias = max(necesarias, 2)
    actuales = ultima - primera + 1
    if necesarias > actuales:
        extra = necesarias - actuales
        ws.Range(f"{ultima}:{ultima + extra - 1}").Insert(XL_DOWN, 0)
    elif necesarias < actuales:
        quitar = actuales - necesarias
        ws.Range(f"{ultima - quitar}:{ultima - 1}").Delete(XL_UP)
    return primera + necesarias - 1


def _rango(ws, fila1: int, col1: int, fila2: int, col2: int):
    return ws.Range(ws.Cells(fila1, col1), ws.Cells(fila2, col2))


def _guardar_formas(ws, fila_marca: int) -> tuple[float, list]:
    """Posicion de las formas (cuadro de revision, firmas) que estan debajo de `fila_marca`,
    medida desde esa fila. Excel no siempre las mueve cuando se insertan o quitan renglones."""
    arriba = ws.Rows(fila_marca).Top
    return arriba, [(forma, forma.Top - arriba) for forma in ws.Shapes if forma.Top >= arriba - 1]


def _reubicar_formas(ws, guardado: tuple[float, list], nueva_fila_marca: int) -> None:
    _, formas = guardado
    arriba = ws.Rows(nueva_fila_marca).Top
    for forma, distancia in formas:
        forma.Top = arriba + distancia


def _ajustar_pagina(ws, una_hoja: bool = True) -> None:
    """Todo el ancho en una hoja, sin los saltos manuales de la plantilla (dejaban una pagina extra casi
    vacia). Con pocos renglones tambien cabe todo de alto en una sola hoja; con muchos se reparte en varias."""
    ws.ResetAllPageBreaks()
    ws.PageSetup.Zoom = False
    ws.PageSetup.FitToPagesWide = 1
    ws.PageSetup.FitToPagesTall = 1 if una_hoja else False


def _agregar_texto(ws, celda: str, texto: str) -> None:
    """Escribe `texto` a continuacion de la etiqueta que trae la plantilla ("Área/Dirección:" + area)."""
    etiqueta = str(ws.Range(celda).Value or "").rstrip()
    ws.Range(celda).Value = f"{etiqueta} {texto}"


def _hojas_por_area(wb, base, cantidad: int) -> list:
    """`base` y sus copias (con logos y formato) hasta tener una hoja por area."""
    hojas = [base]
    for _ in range(cantidad - 1):
        base.Copy(None, wb.Worksheets(wb.Worksheets.Count))
        hojas.append(wb.Worksheets(wb.Worksheets.Count))
    return hojas


# --- F01 y F02: control quincenal ----------------------------------------------
def _llenar_control(ws, *, maestros, dias, celdas_por_maestro, corte, primera, ultima, col_dia1, fila_dias,
                    pares, totales: dict[int, Callable], fila_marca: int, max_personas_una_hoja: int,
                    col_ultima: int, col_turno: int | None = None, formato_total: str | None = None,
                    columnas_unidas: tuple[int, ...] = ()) -> None:
    """Cada persona ocupa dos renglones: arriba las horas (solo dias con retardo) y claves, abajo los
    minutos de retardo, para que no se vea todo junto."""
    n = len(maestros)
    renglones = max(2 * n, 2)
    formas = _guardar_formas(ws, fila_marca)
    _ajustar_filas(ws, primera, ultima, renglones)
    for i in range(renglones):
        ws.Rows(primera + i).RowHeight = ALTO_ARRIBA if i % 2 == 0 else ALTO_ABAJO
    _reubicar_formas(ws, formas, fila_marca + renglones - (ultima - primera + 1))
    _ajustar_pagina(ws, una_hoja=n <= max_personas_una_hoja)

    for k in range(pares):  # numeros de dia en el encabezado
        ws.Cells(fila_dias, col_dia1 + 2 * k).Value = dias[k].day if k < len(dias) else None
    if n == 0:
        return

    fin = primera + renglones - 1
    col_fin = col_dia1 + 2 * pares - 1
    zona = _rango(ws, primera, col_dia1, fin, col_fin)
    zona.NumberFormat = "@"  # que "08:05" se quede como texto y no la convierta en hora
    zona.HorizontalAlignment = XL_CENTER
    zona.VerticalAlignment = XL_CENTER
    zona.Font.Bold = False  # la plantilla trae negritas sueltas: solo van las claves y los retardos
    zona.Font.Underline = XL_UNDERLINE_NONE
    zona.Interior.ColorIndex = XL_SIN_RELLENO
    nombres = _rango(ws, primera, 1, fin, 1)
    nombres.Font.Bold = False
    nombres.VerticalAlignment = XL_CENTER
    nombres.ShrinkToFit = True
    for col in totales:
        destino = _rango(ws, primera, col, fin, col)
        destino.HorizontalAlignment = XL_CENTER
        destino.VerticalAlignment = XL_CENTER
        if formato_total:
            destino.NumberFormat = formato_total

    for i, maestro in enumerate(maestros):
        arriba, abajo = primera + 2 * i, primera + 2 * i + 1
        fila_horas = [""] * (2 * pares)
        dias_con = []  # (columna de entrada, entrada, salida, unido)
        for k, celda in enumerate(celdas_por_maestro.get(maestro.id, [])[:pares]):
            entrada, salida, unido = _par(celda, corte)
            fila_horas[2 * k], fila_horas[2 * k + 1] = entrada.split("\n")[0], salida
            dias_con.append((col_dia1 + 2 * k, entrada, salida, unido))
        # los dias sin celda (quincena con menos dias que columnas) tambien quedan como cuadro vacio
        for k in range(len(dias_con), pares):
            dias_con.append((col_dia1 + 2 * k, "", "", False))
        _rango(ws, arriba, col_dia1, arriba, col_fin).Value = (tuple(fila_horas),)

        for col, entrada, salida, unido in dias_con:
            izq, der = ws.Cells(arriba, col), ws.Cells(arriba, col + 1)
            if "\n" in entrada:  # retardo: horas arriba, minutos abajo
                izq.Font.Bold = True
                der.Font.Bold = True
                minutos = _rango(ws, abajo, col, abajo, col + 1)
                minutos.Merge()
                minutos.Value = entrada.split("\n")[1].replace(" m", " min")
                minutos.Font.Bold = True
                minutos.Font.Size = 7
                minutos.Interior.Color = COLOR_BANDA_RETARDO
            elif unido:  # clave de dia completo (FI, P, C, I...): ocupa los dos renglones y los dos lados
                bloque = _rango(ws, arriba, col, abajo, col + 1)
                bloque.Merge()
                izq.Font.Bold = True
            elif entrada or salida:  # FIE o FIS: la clave ocupa los dos renglones de su lado
                for celda_lado, texto in ((izq, entrada), (der, salida)):
                    ws.Range(celda_lado, ws.Cells(abajo, celda_lado.Column)).Merge()
                    if texto:
                        celda_lado.Font.Bold = True
            else:  # dia sin nada
                _rango(ws, arriba, col, abajo, col + 1).Merge()

        ws.Range(ws.Cells(arriba, 1), ws.Cells(abajo, 1)).Merge()
        ws.Cells(arriba, 1).Value = maestro.nombre.upper()
        if col_turno:
            ws.Range(ws.Cells(arriba, col_turno), ws.Cells(abajo, col_turno)).Merge()
            ws.Cells(arriba, col_turno).Value = (maestro.turno or "")[:1].upper()
        for col, calcular in totales.items():
            ws.Range(ws.Cells(arriba, col), ws.Cells(abajo, col)).Merge()
            ws.Cells(arriba, col).Value = calcular(maestro, celdas_por_maestro.get(maestro.id, []))
        for col in columnas_unidas:  # columnas vacias de la plantilla (ej. HORAS en F02): sin linea a medio renglon
            ws.Range(ws.Cells(arriba, col), ws.Cells(abajo, col)).Merge()

    _lineas(ws, primera, fin, col_ultima, [col_dia1 + 2 * k for k in range(pares)], grupo=2)


def _lineas(ws, primera: int, ultima: int, col_ultima: int, columnas_de_dia: list[int], grupo: int = 1) -> None:
    """Rejilla fina en toda la tabla, marco y separador de dia mas marcados, y una linea marcada entre
    personas cuando cada una ocupa varios renglones (`grupo`), para que no se vea todo junto."""
    tabla = _rango(ws, primera, 1, ultima, col_ultima)
    tabla.VerticalAlignment = XL_CENTER
    for borde in (XL_EDGE_LEFT, XL_EDGE_TOP, XL_EDGE_BOTTOM, XL_EDGE_RIGHT, XL_INSIDE_VERTICAL, XL_INSIDE_HORIZONTAL):
        linea = tabla.Borders(borde)
        linea.LineStyle = XL_CONTINUOUS
        linea.Weight = XL_THIN
        linea.Color = COLOR_LINEA
    for borde in (XL_EDGE_LEFT, XL_EDGE_TOP, XL_EDGE_BOTTOM, XL_EDGE_RIGHT):
        tabla.Borders(borde).Weight = XL_MEDIUM
        tabla.Borders(borde).Color = 0
    for col in columnas_de_dia:
        separador = _rango(ws, primera, col, ultima, col).Borders(XL_EDGE_LEFT)
        separador.Weight = XL_MEDIUM
        separador.Color = 0
    if grupo > 1:
        for fila in range(primera + grupo - 1, ultima, grupo):
            linea = _rango(ws, fila, 1, fila, col_ultima).Borders(XL_EDGE_BOTTOM)
            linea.LineStyle = XL_CONTINUOUS
            linea.Weight = XL_MEDIUM
            linea.Color = 0


def _total_retardo(_maestro, celdas) -> float | None:
    """TOTAL de F01: la plantilla lo muestra como hora (hh:mm), asi que va como fraccion de dia."""
    minutos = sum(c.get("retardo_min", 0) for c in celdas if c["tipo"] == "completo")
    return minutos / 1440 if minutos else None


def _total_faltas(_maestro, celdas) -> int | None:
    return sum(1 for c in celdas if c["tipo"] == "falta") or None


def exportar_f01(ruta, maestros, dias, celdas_por_maestro, anio, mes, mitad, corte: str | None = None) -> None:
    corte = corte or corte_entrada()
    grupos = _por_area(maestros)
    with _Excel() as app:
        wb = _abrir(app, "F01.xlsx")
        base = wb.Worksheets(1)
        wb.Worksheets(3).Delete()  # F16: formatos aparte que no se usan aqui
        wb.Worksheets(2).Delete()
        hojas = _hojas_por_area(wb, base, len(grupos))

        usados: set[str] = set()
        for ws, (area, personas) in zip(hojas, grupos.items()):
            ws.Name = _nombre_hoja(area, usados)
            _agregar_texto(ws, "A3", "" if area == SIN_AREA else area)
            _agregar_texto(ws, "A5", quincena_texto(anio, mes, mitad))
            ws.Range("A13").Value = (
                "Aparecen la entrada y salida de los días con retardo, con los minutos de retardo debajo, "
                "y las incidencias de cada día."
            )
            ws.Range("A20").Value = ""  # "Horas Subrayadas": ya no se imprimen las salidas
            _llenar_control(
                ws, maestros=personas, dias=dias, celdas_por_maestro=celdas_por_maestro, corte=corte,
                primera=11, ultima=12, col_dia1=2, fila_dias=8, pares=F01_PARES, totales={26: _total_retardo},
                fila_marca=13, max_personas_una_hoja=12, formato_total="[hh]:mm", col_ultima=26,
            )
        wb.Worksheets(1).Activate()
        _guardar(wb, ruta)


def _preparar_f02(ws, dias_necesarios: int) -> int:
    """Uniforma los renglones de la plantilla y agrega columnas de dia si hacen falta.
    Regresa cuantos pares Entrada/Salida quedan disponibles."""
    # La plantilla trae renglones fusionados a media tabla: se deshacen y todos toman un formato comun.
    ws.Range("A19:AA36").UnMerge()
    ws.Range("A24:AA24").Copy()
    ws.Range("A20:AA35").PasteSpecial(XL_PASTE_FORMATS)
    alto = ws.Rows(24).RowHeight
    for fila in range(20, 36):
        ws.Rows(fila).RowHeight = alto
    ws.Application.CutCopyMode = False

    pares = F02_PARES_VISIBLES
    if dias_necesarios >= F02_PARES_PLANTILLA:
        ws.Columns("W:X").ColumnWidth = ws.Columns("U").ColumnWidth
        pares = F02_PARES_PLANTILLA
    extra = dias_necesarios - F02_PARES_PLANTILLA
    if extra > 0:  # mas dias que columnas: se copian pares ya formateados antes de TOTAL
        ws.Range("C16:X16").UnMerge()
        for _ in range(extra):
            ws.Range("W:X").Copy()
            ws.Range("Y:Z").Insert(XL_TO_RIGHT)
            ws.Application.CutCopyMode = False
            pares += 1
        ultima_col = 3 + 2 * pares - 1
        ws.Range(ws.Cells(16, 3), ws.Cells(16, ultima_col)).Merge()
        ws.Cells(16, 3).HorizontalAlignment = XL_CENTER
    return pares


def exportar_f02(ruta, maestros, dias, celdas_por_maestro, anio, mes, mitad, corte: str | None = None) -> None:
    corte = corte or corte_entrada()
    grupos = _por_area(maestros)
    with _Excel() as app:
        wb = _abrir(app, "F02.xls")
        base = wb.Worksheets(1)
        pares = _preparar_f02(base, len(dias))
        hojas = _hojas_por_area(wb, base, len(grupos))

        usados: set[str] = set()
        for ws, (carrera, personas) in zip(hojas, grupos.items()):
            ws.Name = _nombre_hoja(carrera, usados)
            _agregar_texto(ws, "A10", "" if carrera == SIN_AREA else carrera)
            _agregar_texto(ws, "A12", quincena_texto(anio, mes, mitad))
            col_total = 26 + 2 * max(0, pares - F02_PARES_PLANTILLA)
            _llenar_control(
                ws, maestros=personas, dias=dias, celdas_por_maestro=celdas_por_maestro, corte=corte,
                primera=19, ultima=36, col_dia1=3, fila_dias=17, pares=pares, col_turno=2,
                totales={col_total: _total_faltas}, fila_marca=40, max_personas_una_hoja=9,
                col_ultima=col_total + 1, columnas_unidas=(col_total - 1, col_total + 1),
            )
        wb.Worksheets(1).Activate()
        _guardar(wb, ruta)


# --- F05: concentrado de incidencias -------------------------------------------
# Renglones de datos con que viene cada bloque de la plantilla: 5, 5 y 15; los bloques
# que se agregan son copias del segundo (5).
F05_RENGLONES = [5, 5, 15]


def _bloques_f05(ws) -> list[int]:
    """Filas del encabezado 'DÍAS' de cada bloque, de arriba hacia abajo."""
    filas = []
    for fila in range(1, 200):
        valor = ws.Cells(fila, 2).Value
        if isinstance(valor, str) and valor.strip().upper().startswith("D") and valor.strip().upper().endswith("AS"):
            filas.append(fila)
    return filas


def exportar_f05(ruta, maestros, celdas_por_maestro, anio, mes, mitad) -> None:
    filas_por_area: dict[str, list[tuple]] = {}
    for area, personas in _por_area(maestros).items():
        filas = []
        for maestro in personas:
            r = resumen_concentrado(celdas_por_maestro.get(maestro.id, []))
            if F05_SOLO_CON_INCIDENCIAS and not (r["dias"] or r["horas"] or r["minutos"]):
                continue
            filas.append((maestro.nombre.upper(), r["dias"], r["horas"], r["minutos"]))
        if filas or not F05_SOLO_CON_INCIDENCIAS:
            filas_por_area[area] = filas
    if not filas_por_area:
        filas_por_area = {"Sin incidencias en la quincena": []}

    bloques = len(filas_por_area)
    with _Excel() as app:
        wb = _abrir(app, "F05.xls")
        ws = wb.Worksheets(1)
        formas = _guardar_formas(ws, 63)  # firmas, recuadro de revision
        # Estructura: B1 = filas 14-24, B2 = 26-37, B3 = 39-60, firmas desde la 63.
        if bloques == 1:
            ws.Range("25:60").Delete(XL_UP)
        elif bloques == 2:
            ws.Range("38:60").Delete(XL_UP)
        else:
            for _ in range(bloques - 3):
                ws.Range("25:37").Copy()
                ws.Range("61:61").Insert(XL_DOWN)
            ws.Application.CutCopyMode = False

        encabezados = _bloques_f05(ws)
        renglones = F05_RENGLONES + [5] * max(0, len(encabezados) - len(F05_RENGLONES))
        texto_quincena = f"Quincena del: {quincena_texto(anio, mes, mitad)}"
        # De abajo hacia arriba: agregar o quitar renglones no mueve los bloques de arriba.
        for indice in reversed(range(bloques)):
            area, filas = list(filas_por_area.items())[indice]
            encabezado = encabezados[indice]
            primera = encabezado + 1
            ultima = primera + renglones[indice] - 1
            ultima = _ajustar_filas(ws, primera, ultima, len(filas))
            ws.Range(f"{primera}:{ultima}").RowHeight = 16
            fila_area = next(
                f for f in range(encabezado - 1, encabezado - 9, -1)
                if str(ws.Cells(f, 1).Value or "").strip().lower().startswith("area")
            )
            etiqueta_area = "" if area == SIN_AREA else area
            ws.Cells(fila_area, 1).Value = f"Area/Carrera: {etiqueta_area}".rstrip()
            ws.Cells(encabezado - 4, 1).Value = texto_quincena
            if filas:
                datos = _rango(ws, primera, 1, primera + len(filas) - 1, 4)
                datos.Value = tuple(filas)
                _rango(ws, primera, 2, primera + len(filas) - 1, 4).HorizontalAlignment = XL_CENTER
            # El ultimo renglon de cada bloque de la plantilla trae otra letra: todos toman la del primero.
            for col in range(1, 5):
                modelo = ws.Cells(primera, col).Font
                fuente = _rango(ws, primera, col, max(primera + len(filas) - 1, primera + 1), col).Font
                fuente.Name, fuente.Size, fuente.Bold = modelo.Name, modelo.Size, modelo.Bold
            _lineas(ws, primera, ultima, 4, [])
        fila_firmas = next(f for f in range(1, 300) if "elabor" in str(ws.Cells(f, 1).Value or "").lower())
        _reubicar_formas(ws, formas, fila_firmas)
        _ajustar_pagina(ws, una_hoja=sum(max(len(f), 2) for f in filas_por_area.values()) <= 40)
        ws.Cells(1, 1).Select()
        _guardar(wb, ruta)
