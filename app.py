
from datetime import date, timedelta
from flask import *
import os
import uuid
import sqlite3
from flask import request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from database import (
    add_student,
    get_students,
    update_student,
    delete_student,
    get_student_by_id,
    get_db,
    init_db,
    get_registered_faces,
    mark_attendance
)

import numpy as np
import time 
from deepface import DeepFace
import cv2
from flask import Flask, Response
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash,check_password_hash

from database import (
    create_admin,
    get_admin_by_username,
    count_admins
)
import base64
app = Flask(__name__)


app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
app.config["SESSION_COOKIE_SECURE"] = bool(os.environ.get("RENDER"))
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

init_db()

FACES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "faces"
)

os.makedirs(FACES_DIR, exist_ok=True)


def get_face_embedding(image_path):
    result = DeepFace.represent(
        img_path=image_path,
        model_name="Facenet512",
        detector_backend="opencv",
        enforce_detection=True
    )

    if not result:
        raise ValueError("No face detected in the image.")

    # Select the largest detected face
    face = max(
        result,
        key=lambda item:
            item["facial_area"]["w"] *
            item["facial_area"]["h"]
    )

    return face["embedding"], face["facial_area"]


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapper




@app.before_request
def protect_everything():
    ep = request.endpoint
    if ep is None or ep == "static":
        return

    # First run: only the setup page is allowed until an admin exists
    if count_admins() == 0:
        if ep == "setup_admin":
            return
        return redirect(url_for("setup_admin"))

    # Login and setup pages are public
    if ep in ("login", "setup_admin"):
        return

    # Everything else needs a logged-in admin
    if not session.get("admin_id"):
        if request.path == "/recognize":
            return jsonify(status="login_required"), 401
        return redirect(url_for("login"))

@app.route("/setup", methods=["GET", "POST"])
def setup_admin():
    if count_admins() > 0:
        return redirect(url_for("login"))
    if request.method == "POST":
        if request.form.get("setup_code") != os.environ.get("SETUP_CODE", ""):
            flash("Invalid setup code.", "danger")
            return render_template("setup_admin.html")
        ok, msg = _make_admin()
        flash(msg, "success" if ok else "danger")
        if ok:
            return redirect(url_for("login"))
    return render_template("setup_admin.html")

@app.route("/admins/new", methods=["GET", "POST"])
def create_admin_account():
    if request.method == "POST":
        ok, msg = _make_admin()
        flash(msg, "success" if ok else "danger")
        if ok:
            return redirect(url_for("dashboard"))
    return render_template("admin_create.html")

def _make_admin():
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip() or None
    pw, pw2 = request.form.get("password", ""), request.form.get("confirm_password", "")
    if not username or len(pw) < 8:
        return False, "Username required and password must be 8+ characters."
    if pw != pw2:
        return False, "Passwords do not match."
    try:
        create_admin(username, email, generate_password_hash(pw))
    except sqlite3.IntegrityError:
        return False, "Username or email already exists."
    return True, "Admin account created."

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        admin = get_admin_by_username(request.form.get("username", "").strip())
        if admin and check_password_hash(admin["password"], request.form.get("password", "")):
            session.clear()
            session["admin_id"] = admin["id"]
            session["admin_name"] = admin["username"]
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))






@app.route("/register", methods=["POST"])
def register_student():
    name = request.form.get("name", "").strip()
    roll_no = request.form.get("roll_no", "").strip()
    photo = request.files.get("photo")

    if not name or not roll_no or not photo or not photo.filename:
        flash("Enter the student details and choose a photo.")
        return redirect(url_for("students_page"))

    extension = photo.filename.rsplit(".", 1)[-1].lower()
    if extension not in {"jpg", "jpeg", "png", "webp"}:
        flash("Upload a JPG, JPEG, PNG or WEBP photo.")
        return redirect(url_for("students_page"))

    filename = secure_filename(f"{uuid.uuid4().hex}.{extension}")
    photo_path = os.path.join(FACES_DIR, filename)
    photo.save(photo_path)

    try:
        embedding, _ = get_face_embedding(photo_path)
        add_student(roll_no, name, photo_path, embedding)
        flash(f"{name} was registered successfully.")
    except sqlite3.IntegrityError:
        if os.path.exists(photo_path):
            os.remove(photo_path)
        flash("This roll number is already registered.")
    except Exception:
        if os.path.exists(photo_path):
            os.remove(photo_path)
        flash("Registration failed. Try a clear photo with one visible face.")

    return redirect(url_for("students_page"))

@app.route("/")
def index():
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
def dashboard():

    db = get_db()

    total_students = db.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]

    present_today = db.execute("""
        SELECT COUNT(*) FROM attendance
        WHERE date = ?
    """, (date.today().isoformat(),)).fetchone()[0]

    absent_today = max(0, total_students - present_today)

    attendance_rate = round(
        present_today / total_students * 100
    ) if total_students else 0

    recent = db.execute("""
        SELECT students.name, students.roll_no,
               attendance.date, attendance.time
        FROM attendance
        JOIN students ON students.id = attendance.student_id
        ORDER BY attendance.id DESC
        LIMIT 6
    """).fetchall()

    labels = []
    daily_counts = []

    for offset in range(6, -1, -1):
        day = date.today() - timedelta(days=offset)
        labels.append(day.strftime("%a"))

        count = db.execute("""
            SELECT COUNT(*) FROM attendance
            WHERE date = ?
        """, (day.isoformat(),)).fetchone()[0]

        daily_counts.append(count)

    db.close()
    return render_template(
        "dashboard.html",
        total_students=total_students,
        present_today=present_today,
        absent_today=absent_today,
        attendance_rate=attendance_rate,
        recent=recent,
        chart_labels=labels,
        chart_values=daily_counts
    )

@app.route("/faces/<path:filename>")
def face_image(filename):
    return send_from_directory(FACES_DIR, filename)


@app.route("/students")
def students_page():
    return render_template("students.html", students=get_students())


@app.route("/camera")
def camera_page():
    return render_template("camera.html")


@app.route("/reports")
def reports_page():
    db = get_db()

    records = db.execute("""
        SELECT students.name, students.roll_no,
               attendance.date, attendance.time
        FROM attendance
        JOIN students ON students.id = attendance.student_id
        ORDER BY attendance.date DESC, attendance.time DESC
        LIMIT 200
    """).fetchall()

    db.close()

    return render_template("reports.html", records=records)


@app.route("/recognize", methods=["POST"])
def recognize():
    
    data = request.get_json(silent=True) or {}
    try:
        raw = base64.b64decode(data["image"].split(",", 1)[1])
        frame = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        faces = DeepFace.represent(
            img_path=frame, model_name="Facenet512",
            detector_backend="opencv", enforce_detection=True
        )
    except Exception:
        return jsonify(status="no_face")

    face = max(faces, key=lambda f: f["facial_area"]["w"] * f["facial_area"]["h"])
    emb = np.array(face["embedding"])

    best, best_dist = None, 1.0
    for s in get_registered_faces():
        ref = np.array(s["embedding"])
        dist = 1 - emb @ ref / (np.linalg.norm(emb) * np.linalg.norm(ref))
        if dist < best_dist:
            best, best_dist = s, dist

    if best is None or best_dist > 0.30:   # Facenet512 cosine threshold
        return jsonify(status="unknown")

    new = mark_attendance(best["id"])
    return jsonify(status="marked" if new else "already",
                   name=best["name"], roll_no=best["roll_no"])





@app.route("/students/<int:student_id>")
def student_profile(student_id):
    student = get_student_by_id(student_id)

    if student is None:
        flash("Student not found.", "error")
        return redirect(url_for("students_page"))

    return render_template(
        "student_profile.html",
        student=student
    )


@app.route("/students/<int:student_id>/update", methods=["POST"])
def edit_student(student_id):
    student = get_student_by_id(student_id)

    if student is None:
        flash("Student not found.", "error")
        return redirect(url_for("students_page"))

    roll_no = request.form.get("roll_no", "").strip()
    name = request.form.get("name", "").strip()

    if not roll_no or not name:
        flash("Name and roll number are required.", "error")
        return redirect(
            url_for("student_profile", student_id=student_id)
        )

    try:
        update_student(student_id, roll_no, name)
        flash("Student details updated successfully.", "success")
    except sqlite3.IntegrityError:
        flash("That roll number is already registered.", "error")

    return redirect(
        url_for("student_profile", student_id=student_id)
    )


@app.route("/students/<int:student_id>/delete", methods=["POST"])
def remove_student(student_id):
    student = get_student_by_id(student_id)

    if student is None:
        flash("Student not found.", "error")
    else:
        delete_student(student_id)
        flash("Student deleted successfully.", "success")

    return redirect(url_for("students_page"))

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)