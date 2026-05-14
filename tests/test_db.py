import pytest
from db import SQLiteAdapter, ValidationError


SCHEMA = """
CREATE TABLE students (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT    NOT NULL,
    cohort  TEXT    NOT NULL,
    score   REAL    NOT NULL DEFAULT 0.0
);
INSERT INTO students (name, cohort, score) VALUES
    ('Alice',   'A1', 8.5),
    ('Bob',     'A1', 7.0),
    ('Charlie', 'B1', 9.0),
    ('Diana',   'B1', 6.5),
    ('Eve',     'A2', 8.0);
"""


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "test.db")
    adapter = SQLiteAdapter(path)
    with adapter.connect() as conn:
        conn.executescript(SCHEMA)
        conn.commit()
    return adapter


# ---- list_tables ----

def test_list_tables(db):
    assert db.list_tables() == ["students"]


# ---- get_table_schema ----

def test_get_table_schema(db):
    cols = db.get_table_schema("students")
    names = [c["name"] for c in cols]
    assert "id" in names and "name" in names and "score" in names


def test_get_table_schema_unknown(db):
    with pytest.raises(ValidationError):
        db.get_table_schema("nonexistent")


# ---- search ----

def test_search_all(db):
    result = db.search("students")
    assert result["count"] == 5
    assert result["has_more"] is False


def test_search_filter(db):
    result = db.search("students", filters=[{"column": "cohort", "op": "=", "value": "A1"}])
    assert result["count"] == 2
    assert all(r["cohort"] == "A1" for r in result["rows"])


def test_search_columns(db):
    result = db.search("students", columns=["name", "cohort"])
    assert set(result["rows"][0].keys()) == {"name", "cohort"}


def test_search_order(db):
    result = db.search("students", order_by="score", descending=True)
    scores = [r["score"] for r in result["rows"]]
    assert scores == sorted(scores, reverse=True)


def test_search_pagination(db):
    page1 = db.search("students", limit=2, offset=0)
    page2 = db.search("students", limit=2, offset=2)
    assert page1["count"] == 2
    assert page1["has_more"] is True
    assert page1["rows"][0]["id"] != page2["rows"][0]["id"]


def test_search_unknown_table(db):
    with pytest.raises(ValidationError):
        db.search("hackers")


def test_search_unknown_column_in_filter(db):
    with pytest.raises(ValidationError):
        db.search("students", filters=[{"column": "password", "op": "=", "value": "x"}])


def test_search_bad_operator(db):
    with pytest.raises(ValidationError):
        db.search("students", filters=[{"column": "score", "op": "DROP TABLE--", "value": 0}])


def test_search_max_rows_cap(db):
    result = db.search("students", limit=9999)
    assert result["limit"] == 100


# ---- insert ----

def test_insert(db):
    result = db.insert("students", {"name": "Frank", "cohort": "B2", "score": 7.5})
    assert result["inserted"] is True
    assert isinstance(result["id"], int)


def test_insert_verify_persisted(db):
    db.insert("students", {"name": "Grace", "cohort": "A2", "score": 9.1})
    result = db.search("students", filters=[{"column": "name", "op": "=", "value": "Grace"}])
    assert result["count"] == 1


def test_insert_unknown_table(db):
    with pytest.raises(ValidationError):
        db.insert("hackers", {"name": "X"})


def test_insert_unknown_column(db):
    with pytest.raises(ValidationError):
        db.insert("students", {"name": "X", "password": "secret"})


def test_insert_empty_values(db):
    with pytest.raises(ValidationError):
        db.insert("students", {})


# ---- aggregate ----

def test_aggregate_count(db):
    rows = db.aggregate("students", "COUNT")
    assert rows[0]["value"] == 5


def test_aggregate_avg(db):
    rows = db.aggregate("students", "AVG", "score")
    assert isinstance(rows[0]["value"], float)


def test_aggregate_group_by(db):
    rows = db.aggregate("students", "COUNT", group_by="cohort")
    cohorts = {r["cohort"] for r in rows}
    assert cohorts == {"A1", "A2", "B1"}


def test_aggregate_with_filter(db):
    rows = db.aggregate(
        "students", "AVG", "score",
        filters=[{"column": "cohort", "op": "=", "value": "A1"}]
    )
    assert abs(rows[0]["value"] - 7.75) < 0.01


def test_aggregate_bad_metric(db):
    with pytest.raises(ValidationError):
        db.aggregate("students", "DROP")


def test_aggregate_missing_column(db):
    with pytest.raises(ValidationError):
        db.aggregate("students", "AVG")  # column required for AVG
