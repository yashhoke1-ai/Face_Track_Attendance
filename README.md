# Face_Track_Attendance
A Face Recognition-Based Attendance Management System built using Python, Flask, OpenCV, DeepFace (FaceNet512), and SQLite. Automates student attendance through facial recognition, with student registration, attendance tracking, duplicate prevention, and dashboard-based monitoring.


# FaceTrack

## Project Overview

FaceTrack is a face recognition-based attendance management system developed using Python, Flask, OpenCV, DeepFace (FaceNet512), and SQLite. The main objective of this project is to simplify and automate the traditional attendance process using facial recognition technology.

The system uses a webcam to capture a person's face and compares it with the registered student's facial information to identify the individual. Once a registered student is successfully recognized, the system automatically records their attendance in the SQLite database.

## Key Features

- **Student Registration:** Register students by providing their details and uploading their photographs.
- **Face Recognition:** Uses DeepFace with the FaceNet512 model to recognize registered faces.
- **Webcam Integration:** Uses OpenCV to access the laptop webcam and capture live video frames.
- **Automatic Attendance:** Records attendance when a registered student is successfully identified.
- **Duplicate Prevention:** Prevents multiple attendance entries for the same student on the same day.
- **Student Management:** View registered student profiles and update or delete student information.
- **Attendance Dashboard:** Provides an organized interface to monitor student records and attendance information.
- **Attendance Reports:** Helps view and manage attendance records.

## Technologies Used

- **Programming Language:** Python
- **Backend Framework:** Flask
- **Face Recognition:** DeepFace (FaceNet512)
- **Computer Vision:** OpenCV
- **Database:** SQLite
- **Frontend:** HTML, CSS, JavaScript, Bootstrap 5
- **Templating Engine:** Jinja2

## Project Workflow

First, student details and photographs are registered in the system. When the webcam starts, OpenCV captures video frames, and DeepFace processes the detected face for recognition. The recognized identity is checked against the registered student records. If a match is found, attendance is recorded in the database while preventing duplicate entries for the same day.

## Project Objective

The purpose of FaceTrack is to demonstrate how computer vision and facial recognition can be integrated into a web application to automate attendance management. This project also helped me gain practical experience in Flask development, database operations, webcam integration, and AI-based face recognition.

## Future Improvements

- Real-time attendance notifications.
- Export attendance reports to Excel or PDF.
- Improved recognition performance and security.
- Cloud database integration.

**FaceTrack demonstrates the practical implementation of Python, web development, database management, and AI-based facial recognition in a real-world application.**
