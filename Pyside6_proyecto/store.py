"""Almacen local en memoria compartido por toda la app.

Sirve de reemplazo temporal mientras se conecta Supabase: toda la app lee y
escribe a traves de la instancia `store`, asi que cuando se conecte la base
de datos real, solo hay que cambiar los metodos de esta clase (no cada
pantalla) para que hablen con Supabase en vez de listas en memoria.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

EDIFICIOS = [
    "Docencia 1",
    "Docencia 2",
    "Docencia 3",
    "Laboratorio",
    "Biblioteca",
    "Rectoría",
    "Vinculación",
]

TURNOS = {
    "matutino": {"hora_entrada": "08:00", "hora_salida": "15:00", "tolerancia_minutos": 10},
    "vespertino": {"hora_entrada": "16:00", "hora_salida": "22:00", "tolerancia_minutos": 10},
}

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

CARRERAS = [
    "Ingeniería en Sistemas Computacionales",
    "Ingeniería Industrial",
    "Administración",
    "Contaduría",
    "Gastronomía",
]

_SAMPLE_MAESTROS = [
    ("350", "Vanessa Lorona López", "Profesor de Asignatura", "Docencia 2", "Ingeniería en Sistemas Computacionales", "matutino"),
    ("100", "Alejandra Rendón Fabela", "Administrativo", "Rectoría", "Recursos Humanos", "matutino"),
    ("123", "Ayda Padilla Balmaceda", "Profesor de Tiempo Completo", "Docencia 1", "Administración", "vespertino"),
    ("154", "Lizeth Dorame Torres", "Profesor de Asignatura", "Docencia 3", "Contaduría", "matutino"),
    ("2107", "Alma Luz Oliva Gámez", "Administrativo", "Biblioteca", "Servicios Escolares", "matutino"),
    ("2108", "Christian Robles Moreno", "Profesor de Tiempo Completo", "Laboratorio", "Ingeniería Industrial", "matutino"),
    ("2223", "Manuel Rubén López Félix", "Profesor de Asignatura", "Docencia 2", "Gastronomía", "vespertino"),
    ("2228", "Martín Cuadras López", "Profesor de Asignatura", "Vinculación", "Administración", "vespertino"),
]


@dataclass
class Maestro:
    id: str
    codigo: str
    nombre: str
    tipo_personal: str
    edificio: str
    area_carrera: str
    turno: str
    activo: bool = True


@dataclass
class Incidencia:
    id: str
    maestro_id: str
    fecha_inicio: date
    fecha_fin: date
    tipo: str
    observaciones: str = ""


@dataclass
class ImportRecord:
    id: str
    archivo: str
    fecha: str
    originales: int
    conservados: int
    descartados: int
    origen: str


class LocalStore:
    """Estado en memoria de la sesion actual de la app (no persiste al cerrar)."""

    def __init__(self):
        self.maestros: list[Maestro] = [
            Maestro(id=str(uuid.uuid4()), codigo=c, nombre=n, tipo_personal=t, edificio=e, area_carrera=a, turno=tu)
            for c, n, t, e, a, tu in _SAMPLE_MAESTROS
        ]
        self.incidencias: list[Incidencia] = []
        self.import_history: list[ImportRecord] = []

    # --- maestros ---------------------------------------------------
    def add_maestro(self, **kwargs) -> Maestro:
        maestro = Maestro(id=str(uuid.uuid4()), **kwargs)
        self.maestros.append(maestro)
        return maestro

    def update_maestro(self, maestro_id: str, **kwargs) -> None:
        for maestro in self.maestros:
            if maestro.id == maestro_id:
                for key, value in kwargs.items():
                    setattr(maestro, key, value)
                return

    def remove_maestro(self, maestro_id: str) -> None:
        self.maestros = [m for m in self.maestros if m.id != maestro_id]

    def maestros_por_tipo(self, tipos: list[str]) -> list[Maestro]:
        return [m for m in self.maestros if m.tipo_personal in tipos]

    # --- incidencias --------------------------------------------------
    def add_incidencia(self, **kwargs) -> Incidencia:
        incidencia = Incidencia(id=str(uuid.uuid4()), **kwargs)
        self.incidencias.append(incidencia)
        return incidencia

    def remove_incidencia(self, incidencia_id: str) -> None:
        self.incidencias = [i for i in self.incidencias if i.id != incidencia_id]

    # --- historial de importaciones -----------------------------------
    def add_import(self, **kwargs) -> ImportRecord:
        record = ImportRecord(id=str(uuid.uuid4()), **kwargs)
        self.import_history.insert(0, record)
        return record


store = LocalStore()
