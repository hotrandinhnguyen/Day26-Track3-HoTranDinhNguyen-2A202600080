import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "school.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS students (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT    NOT NULL,
    cohort  TEXT    NOT NULL,
    score   REAL    NOT NULL DEFAULT 0.0,
    email   TEXT
);

CREATE TABLE IF NOT EXISTS courses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    credits     INTEGER NOT NULL DEFAULT 3,
    description TEXT
);

CREATE TABLE IF NOT EXISTS enrollments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id),
    course_id  INTEGER NOT NULL REFERENCES courses(id),
    grade      REAL
);
"""

SEED_SQL = """
INSERT OR IGNORE INTO students (id, name, cohort, score, email) VALUES
    (1,  'Nguyen Van A',   'A1', 8.5, 'vana@example.com'),
    (2,  'Tran Thi B',     'A1', 7.2, 'thib@example.com'),
    (3,  'Le Van C',       'A2', 9.0, 'vanc@example.com'),
    (4,  'Pham Thi D',     'A2', 6.8, 'thid@example.com'),
    (5,  'Hoang Van E',    'B1', 8.0, 'vane@example.com'),
    (6,  'Do Thi F',       'B1', 7.5, 'thif@example.com'),
    (7,  'Vu Van G',       'B2', 9.3, 'vang@example.com'),
    (8,  'Bui Thi H',      'B2', 5.5, 'thih@example.com'),
    (9,  'Dang Van I',     'A1', 8.1, 'vani@example.com'),
    (10, 'Nguyen Thi J',   'A2', 7.9, 'thij@example.com');

INSERT OR IGNORE INTO courses (id, name, credits, description) VALUES
    (1, 'Mathematics',       4, 'Calculus and linear algebra'),
    (2, 'Computer Science',  3, 'Introduction to programming'),
    (3, 'English',           2, 'Academic writing and communication'),
    (4, 'Physics',           3, 'Classical mechanics and thermodynamics'),
    (5, 'Data Science',      3, 'Statistics and machine learning basics');

INSERT OR IGNORE INTO enrollments (id, student_id, course_id, grade) VALUES
    (1,  1, 1, 8.5), (2,  1, 2, 9.0), (3,  2, 1, 7.0),
    (4,  2, 3, 7.5), (5,  3, 2, 9.2), (6,  3, 4, 8.8),
    (7,  4, 1, 6.5), (8,  4, 5, 7.0), (9,  5, 2, 8.0),
    (10, 5, 3, 7.8), (11, 6, 4, 7.2), (12, 6, 5, 7.5),
    (13, 7, 1, 9.5), (14, 7, 2, 9.0), (15, 8, 3, 5.5),
    (16, 8, 4, 6.0), (17, 9, 5, 8.3), (18, 10, 1, 7.8);
"""


def create_database():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.executescript(SEED_SQL)
        conn.commit()
    return DB_PATH


if __name__ == "__main__":
    path = create_database()
    print(f"Database created at: {path}")
