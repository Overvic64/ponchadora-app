"""Capa de datos conectada a Supabase.

Los nombres publicos (EDIFICIOS, TURNOS, store, y los metodos de la clase)
son los mismos que tenia el almacen en memoria original, para que las
pantallas no tengan que cambiar: solo cambio lo que hay detras de cada uno,
que ahora lee y escribe contra las tablas reales en Supabase.
"""
from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass
from datetime import date

import pandas as pd

from core.supabase_client import get_client

TIPOS_PERSONAL = ["Administrativo", "Profesor de Tiempo Completo", "Profesor de Asignatura"]

TIPOS_INCIDENCIA = {
    "I": "Incapacidad",
    "AM": "Atención Médica",
    "P": "Permiso",
    "C": "Comisión",
    "PS": "Permiso Sin Goce de Sueldo",
    "EA": "Entrada Autorizada",
    "SA": "Salida Autorizada",
}

@dataclass
class Maestro:
    id: str
    codigo: str  # columna codigo_excel: codigo del lector biometrico
    numero_interno: str
    nombre: str
    tipo_personal: str | None
    edificio: str
    area_carrera: str | None
    turno: str | None
    activo: bool = True


@dataclass
class Incidencia:
    id: int
    maestro_id: str
    fecha_inicio: date
    fecha_fin: date
    tipo: str
    observaciones: str = ""


@dataclass
class CambioTurno:
    """Un dia en que la persona entro a otra hora (hora_entrada 'HH:MM')."""

    id: int
    maestro_id: str
    fecha: date
    hora_entrada: str


def calcular_retardo(entrada: str, hora_referencia: str, tolerancia_minutos: int) -> int:
    """Minutos de retardo: minutos completos despues de la hora de referencia
    (sin redondear segundos) menos la tolerancia. 10:14:28 contra 10:00 con 10
    min de tolerancia -> 14 - 10 = 4. Igual que la vista reporte_asistencias."""

    def segundos(hora: str) -> int:
        partes = [int(p) for p in hora.split(":")] + [0, 0]
        return partes[0] * 3600 + partes[1] * 60 + partes[2]

    tarde = (segundos(entrada) - segundos(hora_referencia)) // 60
    return max(0, tarde - tolerancia_minutos)


@dataclass
class ImportRecord:
    id: str
    archivo: str
    fecha: str
    originales: int
    conservados: int
    descartados: int
    origen: str


def _normalize_name(name: str) -> str:
    return " ".join(name.strip().upper().split())


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


class SupabaseStore:
    """Lee y escribe contra las tablas reales de Supabase (ver grants.sql/policies.sql)."""

    def __init__(self):
        self.client = get_client()
        self._edificio_by_id: dict[int, str] = {}
        self._edificio_id_by_nombre: dict[str, int] = {}
        self._ponchador_id_por_edificio: dict[str, int] = {}
        self.edificios: list[str] = []
        self.turnos: dict[str, dict] = {}
        self.maestros: list[Maestro] = []
        self.incidencias: list[Incidencia] = []
        self.cambios_turno: dict[tuple[str, str], CambioTurno] = {}
        self.cambios_turno_disponible = False
        self.import_history: list[ImportRecord] = []
        self._quincenas_cache: list[tuple[int, int, str]] | None = None
        self._primera_ponchada: dict[str, str] = {}
        self._mediana_diaria: float = 0
        self.reload()

    def reload(self) -> None:
        self._load_edificios()
        self._load_turnos()
        self._load_ponchadores()
        self._load_maestros()
        self._load_incidencias()
        self._load_cambios_turno()
        self._load_import_history()

    def _load_edificios(self) -> None:
        resp = self.client.table("edificios").select("*").order("id").execute()
        self._edificio_by_id = {row["id"]: row["nombre"] for row in resp.data}
        self._edificio_id_by_nombre = {nombre: id_ for id_, nombre in self._edificio_by_id.items()}
        self.edificios = list(self._edificio_by_id.values())

    def _load_turnos(self) -> None:
        resp = self.client.table("turnos").select("*").execute()
        self.turnos.clear()
        for row in resp.data:
            self.turnos[row["id"]] = {
                "hora_entrada": row["hora_entrada"][:5],
                "hora_salida": row["hora_salida"][:5],
                "tolerancia_minutos": row["tolerancia_minutos"],
            }

    def _load_ponchadores(self) -> None:
        resp = self.client.table("ponchadores").select("*").execute()
        self._ponchador_id_por_edificio = {
            self._edificio_by_id.get(row["edificio_id"]): row["id"]
            for row in resp.data
            if row["edificio_id"] in self._edificio_by_id
        }

    def ponchador_id_por_edificio(self, nombre_edificio: str) -> int | None:
        return self._ponchador_id_por_edificio.get(nombre_edificio)

    def _maestro_from_row(self, row: dict) -> Maestro:
        return Maestro(
            id=row["id"],
            codigo=row["codigo_excel"],
            numero_interno=row["numero_interno"],
            nombre=row["nombre"],
            tipo_personal=row["tipo_personal"],
            edificio=self._edificio_by_id.get(row["edificio_id"], ""),
            area_carrera=row["area_carrera"],
            turno=row["turno_id"],
            activo=row["activo"],
        )

    def _load_maestros(self) -> None:
        resp = self.client.table("maestros").select("*").order("nombre").execute()
        self.maestros = [self._maestro_from_row(row) for row in resp.data]

    def _incidencia_from_row(self, row: dict) -> Incidencia:
        return Incidencia(
            id=row["id"],
            maestro_id=row["maestro_id"],
            fecha_inicio=date.fromisoformat(row["fecha_inicio"]),
            fecha_fin=date.fromisoformat(row["fecha_fin"]),
            tipo=row["tipo"],
            observaciones=row.get("observaciones") or "",
        )

    def _load_incidencias(self) -> None:
        resp = (
            self.client.table("incidencias")
            .select("*")
            .order("fecha_inicio", desc=True)
            .execute()
        )
        self.incidencias = [self._incidencia_from_row(row) for row in resp.data]

    # --- maestros ---------------------------------------------------
    def _next_numero_interno(self) -> str:
        resp = (
            self.client.table("maestros")
            .select("numero_interno")
            .order("numero_interno", desc=True)
            .limit(1)
            .execute()
        )
        if not resp.data:
            return "EMP-0001"
        ultimo = int(resp.data[0]["numero_interno"].split("-")[1])
        return f"EMP-{ultimo + 1:04d}"

    def add_maestro(self, *, codigo, nombre, tipo_personal, edificio, area_carrera, turno) -> Maestro:
        payload = {
            "numero_interno": self._next_numero_interno(),
            "codigo_excel": codigo,
            "nombre": nombre,
            "nombre_normalizado": _normalize_name(nombre),
            "edificio_id": self._edificio_id_by_nombre.get(edificio),
            "turno_id": turno or None,
            "turno_confirmado": bool(turno),
            "tipo_personal": tipo_personal,
            "area_carrera": area_carrera or None,
        }
        resp = self.client.table("maestros").insert(payload).execute()
        maestro = self._maestro_from_row(resp.data[0])
        self.maestros.append(maestro)
        return maestro

    def update_maestro(self, maestro_id: str, **kwargs) -> None:
        column_map = {
            "codigo": "codigo_excel",
            "edificio": "edificio_id",
            "turno": "turno_id",
        }
        payload = {}
        for key, value in kwargs.items():
            if key == "edificio":
                payload["edificio_id"] = self._edificio_id_by_nombre.get(value)
            elif key == "nombre":
                payload["nombre"] = value
                payload["nombre_normalizado"] = _normalize_name(value)
            else:
                payload[column_map.get(key, key)] = value
        self.client.table("maestros").update(payload).eq("id", maestro_id).execute()
        for maestro in self.maestros:
            if maestro.id == maestro_id:
                for key, value in kwargs.items():
                    setattr(maestro, key, value)
                return

    def remove_maestro(self, maestro_id: str) -> None:
        self.client.table("maestros").delete().eq("id", maestro_id).execute()
        self.maestros = [m for m in self.maestros if m.id != maestro_id]

    def maestros_por_tipo(self, tipos: list[str]) -> list[Maestro]:
        return [m for m in self.maestros if m.tipo_personal in tipos]

    # --- incidencias --------------------------------------------------
    def add_incidencia(self, *, maestro_id, fecha_inicio, fecha_fin, tipo, observaciones="") -> Incidencia:
        payload = {
            "maestro_id": maestro_id,
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin": fecha_fin.isoformat(),
            "tipo": tipo,
            "observaciones": observaciones,
        }
        resp = self.client.table("incidencias").insert(payload).execute()
        incidencia = self._incidencia_from_row(resp.data[0])
        self.incidencias.insert(0, incidencia)
        return incidencia

    def remove_incidencia(self, incidencia_id) -> None:
        self.client.table("incidencias").delete().eq("id", incidencia_id).execute()
        self.incidencias = [i for i in self.incidencias if i.id != incidencia_id]

    # --- cambios de turno ------------------------------------------------
    @staticmethod
    def _cambio_from_row(row: dict) -> CambioTurno:
        return CambioTurno(
            id=row["id"],
            maestro_id=str(row["maestro_id"]),
            fecha=date.fromisoformat(row["fecha"]),
            hora_entrada=row["hora_entrada"][:5],
        )

    def _load_cambios_turno(self) -> None:
        try:
            resp = self.client.table("cambios_turno").select("*").execute()
        except Exception:  # noqa: BLE001 - falta correr cambios_turno.sql todavia
            self.cambios_turno = {}
            self.cambios_turno_disponible = False
            return
        self.cambios_turno_disponible = True
        cambios = (self._cambio_from_row(row) for row in resp.data)
        self.cambios_turno = {(c.maestro_id, c.fecha.isoformat()): c for c in cambios}

    def add_cambios_turno(self, maestro_id: str, fechas: list[date], hora_entrada: str) -> None:
        """Registra (o reemplaza) la hora de entrada que le tocaba a la persona en cada fecha."""
        payload = [
            {"maestro_id": str(maestro_id), "fecha": f.isoformat(), "hora_entrada": hora_entrada} for f in fechas
        ]
        resp = self.client.table("cambios_turno").upsert(payload, on_conflict="maestro_id,fecha").execute()
        for row in resp.data:
            cambio = self._cambio_from_row(row)
            self.cambios_turno[(cambio.maestro_id, cambio.fecha.isoformat())] = cambio

    def remove_cambio_turno(self, cambio_id: int) -> None:
        self.client.table("cambios_turno").delete().eq("id", cambio_id).execute()
        self.cambios_turno = {k: c for k, c in self.cambios_turno.items() if c.id != cambio_id}

    def _tolerancia(self, fila: dict) -> int:
        turno = self.turnos.get(fila.get("turno_reporte") or "") or self.turnos.get(
            fila.get("turno_sugerido_maestro") or ""
        )
        return turno["tolerancia_minutos"] if turno else 0

    def _aplicar_cambio_turno(self, fila: dict) -> None:
        """Si ese dia hubo cambio de turno, el retardo se calcula contra la
        hora de entrada del cambio (menos la tolerancia) y no contra la normal."""
        cambio = self.cambios_turno.get((str(fila["maestro_id"]), fila["fecha"]))
        if cambio is None or fila.get("estado") != "completo" or not fila.get("entrada"):
            return
        fila["retardo_minutos_original"] = fila.get("retardo_minutos_referencia")
        fila["entrada_referencia"] = cambio.hora_entrada
        fila["cambio_turno"] = True
        fila["retardo_minutos_referencia"] = calcular_retardo(
            fila["entrada"], cambio.hora_entrada, self._tolerancia(fila)
        )

    # --- turnos ---------------------------------------------------------
    def update_turno(self, turno_id: str, *, hora_entrada: str, hora_salida: str, tolerancia_minutos: int) -> None:
        self.client.table("turnos").update(
            {
                "hora_entrada": hora_entrada,
                "hora_salida": hora_salida,
                "tolerancia_minutos": tolerancia_minutos,
            }
        ).eq("id", turno_id).execute()
        self.turnos[turno_id] = {
            "hora_entrada": hora_entrada,
            "hora_salida": hora_salida,
            "tolerancia_minutos": tolerancia_minutos,
        }

    # --- reporte de asistencias ----------------------------------------
    def reporte_asistencias(
        self, fecha_inicio: date | None = None, fecha_fin: date | None = None, limit: int | None = None
    ) -> list[dict]:
        def _query():
            q = self.client.table("reporte_asistencias").select("*")
            if fecha_inicio:
                q = q.gte("fecha", fecha_inicio.isoformat())
            if fecha_fin:
                q = q.lte("fecha", fecha_fin.isoformat())
            # "id" como segundo criterio: "fecha" solo no es unico (muchos
            # maestros comparten fecha), y sin un tiebreaker determinista
            # range() puede repetir o saltarse filas entre paginas.
            return q.order("fecha", desc=True).order("id")

        if limit is not None:
            filas = _query().limit(limit).execute().data
            for fila in filas:
                self._aplicar_cambio_turno(fila)
            return filas

        # Sin limite explicito: PostgREST tope por defecto son 1000 filas por
        # llamada, y una quincena llena (77 maestros x hasta 16 dias) puede
        # pasarse de eso -- se pagina para no truncar en silencio.
        filas: list[dict] = []
        offset = 0
        page_size = 1000
        while True:
            pagina = _query().range(offset, offset + page_size - 1).execute().data
            if not pagina:
                break
            filas.extend(pagina)
            if len(pagina) < page_size:
                break
            offset += page_size
        for fila in filas:
            self._aplicar_cambio_turno(fila)
        return filas

    def historial_ponchadas(self) -> list[dict]:
        """Todas las asistencias (maestro, fecha, entrada, salida), paginando: sirve para
        saber como se comporta cada persona (ver clasificador.py)."""
        filas: list[dict] = []
        offset = 0
        page_size = 1000
        while True:
            pagina = (
                self.client.table("asistencias")
                .select("maestro_id, fecha, entrada, salida")
                .order("id")
                .range(offset, offset + page_size - 1)
                .execute()
                .data
            )
            filas.extend(pagina)
            if len(pagina) < page_size:
                return filas
            offset += page_size

    def _cargar_actividad(self) -> None:
        """Una sola pasada por `asistencias` para saber que quincenas tienen
        datos y desde que fecha poncha cada maestro."""
        claves = set()
        primera: dict[str, str] = {}
        personas_por_dia: Counter = Counter()
        offset = 0
        page_size = 1000
        while True:
            pagina = (
                self.client.table("asistencias")
                .select("maestro_id, fecha")
                .order("id")
                .range(offset, offset + page_size - 1)
                .execute()
                .data
            )
            for row in pagina:
                fecha = row["fecha"]
                claves.add((int(fecha[0:4]), int(fecha[5:7]), "primera" if int(fecha[8:10]) <= 15 else "segunda"))
                if fecha < primera.get(row["maestro_id"], "9999"):
                    primera[row["maestro_id"]] = fecha
                personas_por_dia[fecha] += 1
            if len(pagina) < page_size:
                break
            offset += page_size
        self._quincenas_cache = sorted(claves)
        self._primera_ponchada = primera
        self._mediana_diaria = statistics.median(personas_por_dia.values()) if personas_por_dia else 0

    def mediana_personas_por_dia(self) -> float:
        """Cuantas personas ponchan en un dia tipico, en todo lo importado."""
        if self._quincenas_cache is None:
            self._cargar_actividad()
        return self._mediana_diaria

    def quincenas_disponibles(self) -> list[tuple[int, int, str]]:
        """Solo las quincenas que realmente tienen al menos una ponchada
        importada (no todo el rango entre la primera y la ultima fecha)."""
        if self._quincenas_cache is None:
            self._cargar_actividad()
        return self._quincenas_cache

    def primera_ponchada(self, maestro_id: str) -> str | None:
        """Fecha (YYYY-MM-DD) de la primera ponchada del maestro, o None."""
        if self._quincenas_cache is None:
            self._cargar_actividad()
        return self._primera_ponchada.get(maestro_id)

    def ya_importado(self, archivo: str) -> str | None:
        """Fecha en que ese mismo archivo ya se importo antes, o None."""
        for record in self.import_history:
            if record.archivo == archivo:
                return record.fecha
        return None

    def _indices_maestros(self) -> tuple[dict[str, str], dict[str, str]]:
        por_codigo = {m.codigo: m.id for m in self.maestros if m.codigo}
        conteo = Counter(_normalize_name(m.nombre) for m in self.maestros)
        por_nombre = {
            _normalize_name(m.nombre): m.id for m in self.maestros if conteo[_normalize_name(m.nombre)] == 1
        }
        return por_codigo, por_nombre

    @staticmethod
    def _resolver_maestro(indices, codigo: str, nombre_normalizado: str, compartido: bool) -> str | None:
        """maestro_id para una fila del archivo, o None si no existe.

        Codigos compartidos por varias personas (lector sin huella) solo se
        resuelven por nombre. Un codigo desconocido tambien se intenta por
        nombre: suele ser la misma persona con un segundo gafete. Un nombre
        que coincide con dos maestros se considera ambiguo y no se usa."""
        por_codigo, por_nombre = indices
        if not compartido and codigo in por_codigo:
            return por_codigo[codigo]
        return por_nombre.get(nombre_normalizado)

    def empleados_sin_registrar(self, daily_summary: pd.DataFrame, codigos_compartidos: set[str]) -> list[dict]:
        """Personas del archivo que no corresponden a ningun maestro registrado."""
        indices = self._indices_maestros()
        pendientes: dict[str, dict] = {}
        for record in daily_summary.itertuples(index=False):
            compartido = record.codigo in codigos_compartidos
            if self._resolver_maestro(indices, record.codigo, record.nombre_normalizado, compartido) is None:
                pendientes.setdefault(
                    record.nombre_normalizado,
                    {"codigo": record.codigo, "nombre": record.nombre, "compartido": compartido},
                )
        return sorted(pendientes.values(), key=lambda p: p["nombre"])

    def alta_maestros(self, pendientes: list[dict], edificio: str) -> list[Maestro]:
        """Da de alta personas nuevas sin clasificar (tipo/turno/area en blanco) y regresa
        a las que creo. Un codigo compartido no se guarda tal cual -- se identifican por nombre."""
        if not pendientes:
            return []
        creados: list[Maestro] = []
        siguiente = int(self._next_numero_interno().split("-")[1])
        payloads = []
        for offset, p in enumerate(pendientes):
            numero_interno = f"EMP-{siguiente + offset:04d}"
            codigo = f"SC-{p['codigo']}-{numero_interno}" if p["compartido"] else p["codigo"]
            payloads.append(
                {
                    "numero_interno": numero_interno,
                    "codigo_excel": codigo,
                    "nombre": p["nombre"],
                    "nombre_normalizado": _normalize_name(p["nombre"]),
                    "edificio_id": self._edificio_id_by_nombre.get(edificio),
                    "turno_confirmado": False,
                }
            )
        for lote in _chunks(payloads, 200):
            resp = self.client.table("maestros").insert(lote).execute()
            creados.extend(self._maestro_from_row(row) for row in resp.data)
        self.maestros.extend(creados)
        return creados

    def _asistencias_existentes(self, fecha_min: str, fecha_max: str) -> dict[tuple[str, str], dict]:
        """Todas las asistencias del rango, paginando (PostgREST devuelve
        maximo 1000 filas por consulta)."""
        existentes: dict[tuple[str, str], dict] = {}
        offset = 0
        page_size = 1000
        while True:
            pagina = (
                self.client.table("asistencias")
                .select("id, maestro_id, fecha, entrada, salida, ponchador_entrada_id, ponchador_salida_id")
                .gte("fecha", fecha_min)
                .lte("fecha", fecha_max)
                .order("id")
                .range(offset, offset + page_size - 1)
                .execute()
                .data
            )
            for row in pagina:
                existentes[(row["maestro_id"], row["fecha"])] = row
            if len(pagina) < page_size:
                break
            offset += page_size
        return existentes

    def insertar_asistencias(
        self, daily_summary: pd.DataFrame, ponchador_id: int | None, codigos_compartidos: set[str] | None = None
    ) -> dict:
        """Sube el resumen diario ya depurado a `asistencias`.

        Si hay varias filas para el mismo maestro y fecha (o ya existe un
        registro en la base), los horarios se combinan: entrada = la mas
        temprana, salida = la mas tardia. Asi reimportar un archivo, o subir
        uno que traslapa con otro, nunca pierde marcas ya guardadas.
        """
        codigos_compartidos = codigos_compartidos or set()
        indices = self._indices_maestros()

        combinadas: dict[tuple[str, str], dict] = {}
        sin_match: set[str] = set()
        for record in daily_summary.itertuples(index=False):
            compartido = record.codigo in codigos_compartidos
            maestro_id = self._resolver_maestro(indices, record.codigo, record.nombre_normalizado, compartido)
            if maestro_id is None:
                sin_match.add(f"{record.codigo} ({record.nombre})")
                continue
            fila = combinadas.setdefault(
                (maestro_id, record.fecha),
                {"entrada": None, "salida": None, "ponchador_entrada_id": None, "ponchador_salida_id": None},
            )
            if record.entrada and (fila["entrada"] is None or record.entrada < fila["entrada"]):
                fila["entrada"], fila["ponchador_entrada_id"] = record.entrada, ponchador_id
            if record.salida and (fila["salida"] is None or record.salida > fila["salida"]):
                fila["salida"], fila["ponchador_salida_id"] = record.salida, ponchador_id

        insertados = actualizados = sin_cambios = 0
        if combinadas:
            fechas = [fecha for _, fecha in combinadas]
            existentes = self._asistencias_existentes(min(fechas), max(fechas))

            nuevas, actualizaciones = [], []
            for (maestro_id, fecha), fila in combinadas.items():
                previa = existentes.get((maestro_id, fecha))
                if previa is None:
                    nuevas.append({"maestro_id": maestro_id, "fecha": fecha, **fila})
                    continue
                merged = {
                    "entrada": previa["entrada"],
                    "salida": previa["salida"],
                    "ponchador_entrada_id": previa["ponchador_entrada_id"],
                    "ponchador_salida_id": previa["ponchador_salida_id"],
                }
                if fila["entrada"] and (merged["entrada"] is None or fila["entrada"] < merged["entrada"]):
                    merged["entrada"], merged["ponchador_entrada_id"] = fila["entrada"], fila["ponchador_entrada_id"]
                if fila["salida"] and (merged["salida"] is None or fila["salida"] > merged["salida"]):
                    merged["salida"], merged["ponchador_salida_id"] = fila["salida"], fila["ponchador_salida_id"]
                if merged["entrada"] == previa["entrada"] and merged["salida"] == previa["salida"]:
                    sin_cambios += 1
                else:
                    actualizaciones.append((previa["id"], merged))

            for lote in _chunks(nuevas, 200):
                self.client.table("asistencias").insert(lote, returning="minimal").execute()
            insertados = len(nuevas)
            for row_id, payload in actualizaciones:
                self.client.table("asistencias").update(payload).eq("id", row_id).execute()
            actualizados = len(actualizaciones)
            self._quincenas_cache = None

        return {
            "insertados": insertados,
            "actualizados": actualizados,
            "sin_cambios": sin_cambios,
            "sin_match": sorted(sin_match),
        }

    # --- historial de importaciones -----------------------------------
    def _import_record_from_row(self, row: dict) -> ImportRecord:
        return ImportRecord(
            id=row["id"],
            archivo=row["archivo"],
            fecha=row["fecha"],
            originales=row["originales"],
            conservados=row["conservados"],
            descartados=row["descartados"],
            origen=row["origen"],
        )

    def _load_import_history(self) -> None:
        try:
            resp = (
                self.client.table("import_history")
                .select("*")
                .order("creado_en", desc=True)
                .execute()
            )
        except Exception:  # noqa: BLE001 - falta correr import_history.sql todavia
            self.import_history = []
            return
        self.import_history = [self._import_record_from_row(row) for row in resp.data]

    def add_import(self, **kwargs) -> ImportRecord:
        resp = self.client.table("import_history").insert(kwargs).execute()
        record = self._import_record_from_row(resp.data[0])
        self.import_history.insert(0, record)
        return record


store = SupabaseStore()

# Alias de modulo para las pantallas que hacen `from store import EDIFICIOS, TURNOS`.
# Son el mismo objeto que store.edificios/store.turnos: TURNOS se muta en el
# mismo dict (nunca se reasigna) para que este alias siga viendo los cambios.
EDIFICIOS = store.edificios
TURNOS = store.turnos
