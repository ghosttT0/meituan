import sqlite3
from pathlib import Path


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=MEMORY;")
        return connection

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS eval_spec (
                    spec_id TEXT PRIMARY KEY,
                    instruction_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    payload TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS evaluation_run (
                    run_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                """
            )
