"""Подключение SQLite, схема и справочник статусов."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

STATUSES = (
    ("accepted", "Принята"),
    ("diagnostics", "Диагностика"),
    ("repair", "В ремонте"),
    ("ready", "Готова к выдаче"),
    ("issued", "Выдана"),
    ("cancelled", "Отменена"),
)

TRANSITIONS = {
    "accepted": ("diagnostics", "cancelled"),
    "diagnostics": ("repair", "ready", "cancelled"),
    "repair": ("ready", "cancelled"),
    "ready": ("issued", "repair", "cancelled"),
    "issued": (),
    "cancelled": (),
}


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, timeout=5)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.create_function(
            "casefold", 1, lambda value: str(value or "").casefold(), deterministic=True
        )
        self.connection.executescript(Path(__file__).with_name("schema.sql").read_text())
        with self.transaction() as connection:
            connection.executemany(
                """INSERT OR IGNORE INTO repair_statuses
                   (code, name, sort_order, is_terminal) VALUES (?, ?, ?, ?)""",
                [
                    (code, name, i, int(code in ("issued", "cancelled")))
                    for i, (code, name) in enumerate(STATUSES)
                ],
            )
        self.connection.execute("PRAGMA user_version = 1")
        self.connection.commit()

    @contextmanager
    def transaction(self):
        try:
            with self.connection:
                yield self.connection
        except sqlite3.IntegrityError as error:
            raise ValueError(
                "Операция нарушает целостность данных: запись уже существует "
                "или используется в связанных данных."
            ) from error

    def close(self):
        self.connection.close()
