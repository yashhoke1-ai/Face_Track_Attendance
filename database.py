
import sqlite3
import json
from datetime import datetime

DB_NAME = "students.db"


def get_db():
    db = sqlite3.connect(DB_NAME)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    db = get_db()

    db.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_no TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            photo_path TEXT NOT NULL,
            embedding TEXT NOT NULL
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            UNIQUE(student_id, date),
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
    """)

    db.commit()
    db.close()


def add_student(roll_no, name, photo_path, embedding):
    db = get_db()

    db.execute("""
        INSERT INTO students
        (roll_no, name, photo_path, embedding)
        VALUES (?, ?, ?, ?)
    """, (
        roll_no,
        name,
        photo_path,
        json.dumps(embedding)
    ))

    db.commit()
    db.close()


def get_students():
    db = get_db()
    students = db.execute("""
        SELECT id, roll_no, name, photo_path
        FROM students ORDER BY name
    """).fetchall()
    db.close()
    return students


def get_registered_faces():
    db = get_db()
    rows = db.execute("""
        SELECT id, roll_no, name, embedding
        FROM students
    """).fetchall()
    db.close()

    faces = []

    for row in rows:
        faces.append({
            "id": row["id"],
            "roll_no": row["roll_no"],
            "name": row["name"],
            "embedding": json.loads(row["embedding"])
        })

    return faces


def mark_attendance(student_id):
    now = datetime.now()
    db = get_db()

    cursor = db.execute("""
        INSERT OR IGNORE INTO attendance
        (student_id, date, time)
        VALUES (?, ?, ?)
    """, (
        student_id,
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M:%S")
    ))

    db.commit()
    marked = cursor.rowcount == 1
    db.close()

    return marked


def get_today_attendance():
    today = datetime.now().strftime("%Y-%m-%d")
    db = get_db()

    records = db.execute("""
        SELECT students.roll_no, students.name,
               attendance.date, attendance.time
        FROM attendance
        JOIN students ON students.id = attendance.student_id
        WHERE attendance.date = ?
        ORDER BY attendance.time DESC
    """, (today,)).fetchall()

    db.close()
    return records


def update_student(student_id, roll_no, name):
    db = get_db()
    try:
        db.execute(
            """
            UPDATE students
            SET roll_no = ?, name = ?
            WHERE id = ?
            """,
            (roll_no, name, student_id)
        )
        db.commit()
    finally:
        db.close()


def delete_student(student_id):
    db = get_db()
    try:
        db.execute(
            "DELETE FROM attendance WHERE student_id = ?",
            (student_id,)
        )
        db.execute(
            "DELETE FROM students WHERE id = ?",
            (student_id,)
        )
        db.commit()
    finally:
        db.close()


def get_student_by_id(student_id):
    db = get_db()
    try:
        return db.execute(
            "SELECT * FROM students WHERE id = ?",
            (student_id,)
        ).fetchone()
    finally:
        db.close()
