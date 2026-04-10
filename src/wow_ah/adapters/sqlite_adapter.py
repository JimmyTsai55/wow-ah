import sqlite3

from wow_ah.schemas.prices import PriceSnapshot

_SCHEMA = """
CREATE TABLE IF NOT EXISTS price_snapshots (
    id INTEGER PRIMARY KEY,
    item_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    min_price INTEGER NOT NULL,
    median_price INTEGER,
    mean_price INTEGER,
    total_quantity INTEGER,
    num_auctions INTEGER
);
CREATE INDEX IF NOT EXISTS idx_snapshots_item_ts ON price_snapshots(item_id, timestamp);

CREATE TABLE IF NOT EXISTS items (
    item_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    quality TEXT,
    item_class TEXT,
    item_subclass TEXT,
    last_updated TEXT
);

CREATE TABLE IF NOT EXISTS recipes (
    recipe_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    profession TEXT NOT NULL DEFAULT 'Alchemy',
    output_item_id INTEGER NOT NULL,
    output_quantity INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS recipe_reagents (
    recipe_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    PRIMARY KEY (recipe_id, item_id)
);
"""


class SQLiteAdapter:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._connect()
        conn.executescript(_SCHEMA)
        conn.close()

    def save_snapshots(self, snapshots: list[PriceSnapshot]) -> None:
        conn = self._connect()
        conn.executemany(
            """INSERT INTO price_snapshots
               (item_id, timestamp, min_price, median_price, mean_price, total_quantity, num_auctions)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (s.item_id, s.timestamp, s.min_price, s.median_price, s.mean_price, s.total_quantity, s.num_auctions)
                for s in snapshots
            ],
        )
        conn.commit()
        conn.close()

    def get_price_history(
        self, item_id: int, start: str, end: str
    ) -> list[PriceSnapshot]:
        conn = self._connect()
        rows = conn.execute(
            """SELECT item_id, timestamp, min_price, median_price, mean_price, total_quantity, num_auctions
               FROM price_snapshots
               WHERE item_id = ? AND timestamp >= ? AND timestamp <= ?
               ORDER BY timestamp""",
            (item_id, start, end),
        ).fetchall()
        conn.close()
        return [
            PriceSnapshot(
                item_id=r["item_id"],
                timestamp=r["timestamp"],
                min_price=r["min_price"],
                median_price=r["median_price"],
                mean_price=r["mean_price"],
                total_quantity=r["total_quantity"],
                num_auctions=r["num_auctions"],
            )
            for r in rows
        ]

    def get_latest_prices(self, item_ids: list[int]) -> dict[int, PriceSnapshot]:
        if not item_ids:
            return {}
        conn = self._connect()
        placeholders = ",".join("?" for _ in item_ids)
        rows = conn.execute(
            f"""SELECT p.item_id, p.timestamp, p.min_price, p.median_price,
                       p.mean_price, p.total_quantity, p.num_auctions
                FROM price_snapshots p
                INNER JOIN (
                    SELECT item_id, MAX(timestamp) as max_ts
                    FROM price_snapshots
                    WHERE item_id IN ({placeholders})
                    GROUP BY item_id
                ) latest ON p.item_id = latest.item_id AND p.timestamp = latest.max_ts""",
            item_ids,
        ).fetchall()
        conn.close()
        return {
            r["item_id"]: PriceSnapshot(
                item_id=r["item_id"],
                timestamp=r["timestamp"],
                min_price=r["min_price"],
                median_price=r["median_price"],
                mean_price=r["mean_price"],
                total_quantity=r["total_quantity"],
                num_auctions=r["num_auctions"],
            )
            for r in rows
        }

    def get_last_fetch_timestamp(self) -> str | None:
        conn = self._connect()
        row = conn.execute(
            "SELECT MAX(timestamp) as ts FROM price_snapshots"
        ).fetchone()
        conn.close()
        return row["ts"] if row and row["ts"] else None
