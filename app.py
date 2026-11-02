
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

app = Flask(__name__)
app.secret_key = "your-local-development-secret"

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
def dashboard():
    db = get_db()

    total_students = db.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]

    present_today = db.execute("""
        SELECT COUNT(*) FROM attendance
        WHERE date = ?
    """, (date.today().isoformat(),)).fetchone()[0]

    # In this simple version, students without a record today
    # are counted as not yet marked/absent.
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



def generate_frames():
    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        camera.release()
        print("ERROR: Could not open webcam.")
        return

    # Load registered students and their saved face embeddings.
    registered_faces = get_registered_faces()

    status_message = "Looking for a face..."
    status_color = (0, 229, 255)  # Cyan
    frame_count = 0
    last_recognition_time = 0
    last_student_id = None

    try:
        while True:
            success, frame = camera.read()

            if not success:
                break

            frame_count += 1
            current_time = time.time()

            # Run face recognition periodically to reduce CPU usage.
            if (
                frame_count % 15 == 0
                and current_time - last_recognition_time >= 1
            ):
                last_recognition_time = current_time

                try:
                    detected_faces = DeepFace.represent(
                        img_path=frame,
                        model_name="Facenet512",
                        detector_backend="opencv",
                        enforce_detection=False
                    )

                    best_match = None
                    best_distance = float("inf")

                    for detected in detected_faces:
                        # Ignore results where no face was detected.
                        area = detected.get("facial_area", {})
                        if area.get("w", 0) <= 0 or area.get("h", 0) <= 0:
                            continue

                        live_embedding = np.array(
                            detected["embedding"], dtype=np.float32
                        )

                        for student in registered_faces:
                            saved_embedding = np.array(
                                student["embedding"], dtype=np.float32
                            )

                            denominator = (
                                np.linalg.norm(live_embedding)
                                * np.linalg.norm(saved_embedding)
                            )

                            if denominator == 0:
                                continue

                            # Cosine distance: smaller means more similar.
                            distance = 1 - (
                                np.dot(live_embedding, saved_embedding)
                                / denominator
                            )

                            if distance < best_distance:
                                best_distance = distance
                                best_match = student

                    # Initial threshold for testing; calibrate with real photos.
                    if best_match is not None and best_distance < 0.30:
                        student_id = best_match["id"]
                        student_name = best_match["name"]

                        if student_id != last_student_id:
                            marked = mark_attendance(student_id)
                            last_student_id = student_id

                            if marked:
                                status_message = (
                                    f"Attendance recorded: {student_name}"
                                )
                                status_color = (49, 214, 160)
                                print(status_message)
                            else:
                                status_message = (
                                    f"Attendance already recorded: {student_name}"
                                )
                                status_color = (0, 229, 255)

                    else:
                        last_student_id = None
                        status_message = "Face not recognized"
                        status_color = (0, 80, 255)

                except Exception as error:
                    print("Face recognition error:", error)
                    status_message = "Recognition error - check terminal"
                    status_color = (0, 80, 255)

            # Display the current status directly on the camera video.
            cv2.putText(
                frame,
                status_message,
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                status_color,
                2,
                cv2.LINE_AA
            )

            success, buffer = cv2.imencode(".jpg", frame)

            if not success:
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + buffer.tobytes()
                + b"\r\n"
            )

    finally:
        camera.release()


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


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