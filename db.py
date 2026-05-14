import sqlite3
import os
from abc import ABC, abstractmethod

DB_PATH = os.path.join(os.path.dirname(__file__), "school.db")

ALLOWED_METRICS = {"COUNT", "AVG", "SUM", "MIN", "MAX"}
ALLOWED_OPERATORS = {"=", "!=", ">", ">=", "<", "<=", "LIKE"}
MAX_ROWS = 100


class ValidationError(Exception):
    """Raised when a request cannot be safely executed."""


# ------------------------------------------------------------------ #
#  Abstract base — shared SQL logic, subclasses supply the driver     #
# ------------------------------------------------------------------ #

class BaseAdapter(ABC):
    PLACEHOLDER = "?"  # override to "%s" for psycopg2

    @abstractmethod
    def connect(self): ...

    @abstractmethod
    def list_tables(self) -> list[str]: ...

    @abstractmethod
    def get_table_schema(self, table: str) -> list[dict]: ...

    @abstractmethod
    def _execute(self, sql: str, params: list) -> list[dict]: ...

    @abstractmethod
    def _execute_write(self, sql: str, params: list) -> int | None: ...

    # ---- validation helpers ----

    def _require_table(self, table: str):
        if table not in self.list_tables():
            raise ValidationError(f"Unknown table: '{table}'")

    def _require_columns(self, table: str, columns: list[str]):
        allowed = {col["name"] for col in self.get_table_schema(table)}
        bad = [c for c in columns if c not in allowed]
        if bad:
            raise ValidationError(f"Unknown column(s) in '{table}': {bad}")

    def _build_where(self, table: str, filters: list[dict]) -> tuple[str, list]:
        if not filters:
            return "", []
        allowed_cols = {col["name"] for col in self.get_table_schema(table)}
        clauses, params = [], []
        for f in filters:
            col = f.get("column", "")
            op  = f.get("op", "=").upper()
            val = f.get("value")
            if col not in allowed_cols:
                raise ValidationError(f"Unknown filter column: '{col}'")
            if op not in ALLOWED_OPERATORS:
                raise ValidationError(f"Unsupported operator: '{op}'")
            clauses.append(f"{col} {op} {self.PLACEHOLDER}")
            params.append(val)
        return "WHERE " + " AND ".join(clauses), params

    # ---- public query methods (engine-agnostic) ----

    def search(
        self,
        table: str,
        columns: list[str] | None = None,
        filters: list[dict] | None = None,
        limit: int = 20,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> dict:
        self._require_table(table)

        select_cols = "*"
        if columns:
            self._require_columns(table, columns)
            select_cols = ", ".join(columns)

        where_sql, params = self._build_where(table, filters or [])

        order_sql = ""
        if order_by:
            self._require_columns(table, [order_by])
            direction = "DESC" if descending else "ASC"
            order_sql = f"ORDER BY {order_by} {direction}"

        limit = min(limit, MAX_ROWS)
        ph = self.PLACEHOLDER
        sql = f"SELECT {select_cols} FROM {table} {where_sql} {order_sql} LIMIT {ph} OFFSET {ph}"
        params += [limit + 1, offset]  # fetch one extra to detect has_more

        rows = self._execute(sql, params)
        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]
        return {"rows": rows, "count": len(rows), "limit": limit, "offset": offset, "has_more": has_more}

    def insert(self, table: str, values: dict) -> dict:
        self._require_table(table)
        if not values:
            raise ValidationError("values must not be empty")
        self._require_columns(table, list(values.keys()))

        cols = ", ".join(values.keys())
        placeholders = ", ".join([self.PLACEHOLDER] * len(values))
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
        last_id = self._execute_write(sql, list(values.values()))
        return {"inserted": True, "id": last_id, "data": values}

    def aggregate(
        self,
        table: str,
        metric: str,
        column: str | None = None,
        filters: list[dict] | None = None,
        group_by: str | None = None,
    ) -> list[dict]:
        metric = metric.upper()
        if metric not in ALLOWED_METRICS:
            raise ValidationError(f"Unsupported metric '{metric}'. Allowed: {ALLOWED_METRICS}")
        self._require_table(table)

        if metric == "COUNT" and not column:
            agg_expr = "COUNT(*)"
        else:
            if not column:
                raise ValidationError(f"'column' is required for metric {metric}")
            self._require_columns(table, [column])
            agg_expr = f"{metric}({column})"

        where_sql, params = self._build_where(table, filters or [])

        group_sql = ""
        if group_by:
            self._require_columns(table, [group_by])
            group_sql = f"GROUP BY {group_by}"
            select_part = f"{group_by}, {agg_expr} AS value"
        else:
            select_part = f"{agg_expr} AS value"

        sql = f"SELECT {select_part} FROM {table} {where_sql} {group_sql}"
        return self._execute(sql, params)


# ------------------------------------------------------------------ #
#  SQLite driver                                                       #
# ------------------------------------------------------------------ #

class SQLiteAdapter(BaseAdapter):
    PLACEHOLDER = "?"

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def list_tables(self) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        return [r["name"] for r in rows]

    def get_table_schema(self, table: str) -> list[dict]:
        self._require_table(table)
        with self.connect() as conn:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return [
            {"name": r["name"], "type": r["type"], "notnull": bool(r["notnull"]), "pk": bool(r["pk"])}
            for r in rows
        ]

    def _execute(self, sql: str, params: list) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def _execute_write(self, sql: str, params: list) -> int | None:
        with self.connect() as conn:
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.lastrowid


# ------------------------------------------------------------------ #
#  PostgreSQL driver (bonus)                                           #
# ------------------------------------------------------------------ #

class PostgreSQLAdapter(BaseAdapter):
    PLACEHOLDER = "%s"

    def __init__(self, dsn: str):
        self.dsn = dsn

    def connect(self):
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(self.dsn)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn

    def list_tables(self) -> list[str]:
        sql = (
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        )
        rows = self._execute(sql, [])
        return [r["table_name"] for r in rows]

    def get_table_schema(self, table: str) -> list[dict]:
        self._require_table(table)
        sql = """
            SELECT
                c.column_name AS name,
                c.data_type   AS type,
                (c.is_nullable = 'NO') AS notnull,
                EXISTS (
                    SELECT 1
                    FROM information_schema.key_column_usage k
                    JOIN information_schema.table_constraints tc
                      ON k.constraint_name = tc.constraint_name
                    WHERE tc.constraint_type = 'PRIMARY KEY'
                      AND k.table_name  = c.table_name
                      AND k.column_name = c.column_name
                ) AS pk
            FROM information_schema.columns c
            WHERE c.table_name = %s AND c.table_schema = 'public'
            ORDER BY c.ordinal_position
        """
        return self._execute(sql, [table])

    def _execute(self, sql: str, params: list) -> list[dict]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return [dict(r) for r in cur.fetchall()]

    def _execute_write(self, sql: str, params: list) -> int | None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql + " RETURNING id", params)
                result = cur.fetchone()
                conn.commit()
                return result["id"] if result else None


# ------------------------------------------------------------------ #
#  Factory                                                             #
# ------------------------------------------------------------------ #

def create_adapter(database_url: str | None = None) -> BaseAdapter:
    """Return the right adapter based on DATABASE_URL env var or explicit url."""
    url = database_url or os.getenv("DATABASE_URL", "")
    if url.startswith(("postgresql://", "postgres://")):
        return PostgreSQLAdapter(url)
    return SQLiteAdapter(DB_PATH)
