"""Histórico de posts em SQLite, para não repetir produtos."""

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from .mercadolivre import Product

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id  TEXT    NOT NULL,
    title       TEXT    NOT NULL,
    price       REAL    NOT NULL,
    source      TEXT    NOT NULL,
    posted_at   REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_posts_product ON posts (product_id, posted_at);
"""


@dataclass
class LastPost:
    price: float
    posted_at: float

    @property
    def age_days(self) -> float:
        return (time.time() - self.posted_at) / 86400


class PostHistory:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.executescript(SCHEMA)

    def last_post(self, product_id: str) -> LastPost | None:
        row = self._db.execute(
            "SELECT price, posted_at FROM posts WHERE product_id = ? ORDER BY posted_at DESC LIMIT 1",
            (product_id,),
        ).fetchone()
        return LastPost(*row) if row else None

    def record(self, product: Product, source: str) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO posts (product_id, title, price, source, posted_at) VALUES (?, ?, ?, ?, ?)",
                (product.id, product.title, product.price, source, time.time()),
            )

    def last_posted_at(self) -> float | None:
        return self._db.execute("SELECT MAX(posted_at) FROM posts").fetchone()[0]

    def count_by_source(self, source: str) -> int:
        return self._db.execute("SELECT COUNT(*) FROM posts WHERE source = ?", (source,)).fetchone()[0]

    def recent(self, limit: int = 10) -> list[tuple]:
        return self._db.execute(
            "SELECT title, price, source, posted_at FROM posts ORDER BY posted_at DESC LIMIT ?", (limit,)
        ).fetchall()

    def close(self) -> None:
        self._db.close()
