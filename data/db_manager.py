import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


class DBManager:
    """Persistencia SQLite para profesores, ponchadas e importaciones."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with closing(self.connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS profesores (
                    codigo TEXT PRIMARY KEY,
                    nombre TEXT NOT NULL,
                    area TEXT NOT NULL DEFAULT 'General',
                    activo INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS imports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_name TEXT NOT NULL,
                    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    input_count INTEGER NOT NULL,
                    cleaned_count INTEGER NOT NULL,
                    discarded_count INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ponchadas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    import_id INTEGER REFERENCES imports(id),
                    codigo TEXT NOT NULL REFERENCES profesores(codigo),
                    nombre TEXT NOT NULL,
                    area TEXT NOT NULL DEFAULT 'General',
                    punched_at TEXT NOT NULL,
                    UNIQUE(codigo, punched_at)
                );
                CREATE INDEX IF NOT EXISTS idx_ponchadas_punched_at
                    ON ponchadas(punched_at);
                """
            )
            connection.commit()

    def save_import(self, source_name: str, result: Any) -> int:
        frame = result.cleaned
        with closing(self.connect()) as connection:
            cursor = connection.execute(
                "INSERT INTO imports(source_name, input_count, cleaned_count, discarded_count) VALUES (?, ?, ?, ?)",
                (source_name, result.input_count, len(frame), result.duplicate_count + result.window_discard_count),
            )
            import_id = int(cursor.lastrowid)
            for row in frame.itertuples(index=False):
                code = str(row.codigo).strip()
                name = str(row.nombre).strip()
                area = str(getattr(row, "area", "General")).strip() or "General"
                connection.execute(
                    "INSERT INTO profesores(codigo, nombre, area) VALUES (?, ?, ?) "
                    "ON CONFLICT(codigo) DO UPDATE SET nombre=excluded.nombre, area=excluded.area",
                    (code, name, area),
                )
                connection.execute(
                    "INSERT OR IGNORE INTO ponchadas(import_id, codigo, nombre, area, punched_at) VALUES (?, ?, ?, ?, ?)",
                    (import_id, code, name, area, row.fecha_hora_dt.isoformat(sep=" ")),
                )
            connection.commit()
            return import_id

    def attendance_between(self, fecha_inicio: str, fecha_fin: str) -> list[sqlite3.Row]:
        with closing(self.connect()) as connection:
            return list(connection.execute(
                """
                SELECT p.codigo, p.nombre, p.area, p.punched_at
                FROM ponchadas p
                WHERE date(p.punched_at) BETWEEN date(?) AND date(?)
                ORDER BY p.punched_at, p.codigo
                """,
                (fecha_inicio, fecha_fin),
            ))

    def professors(self) -> list[sqlite3.Row]:
        with closing(self.connect()) as connection:
            return list(connection.execute(
                "SELECT codigo, nombre, area FROM profesores WHERE activo = 1 ORDER BY nombre"
            ))

    def recent_imports(self, limit: int = 20) -> list[sqlite3.Row]:
        with closing(self.connect()) as connection:
            return list(connection.execute(
                "SELECT * FROM imports ORDER BY imported_at DESC, id DESC LIMIT ?", (limit,)
            ))