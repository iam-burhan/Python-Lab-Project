# Python-Lab-Project
Web platform for scheduling, auto-grading and tracking student practical lab work, built with Python and Flask.
# LabPulse – Lab Assessment Platform

LabPulse removes the need for professors to visit every student's PC during
practical labs. Students submit work online, Python code is graded
automatically, and professors track progress from one dashboard.

## Features
- Role-based login (Professor / Student)
- Weekly, monthly and yearly assessment scheduling
- Auto-grading of Python code against input → output test cases
- Manual review with marks and feedback (can override auto-grades)
- Daily lab session logs with professor verification
- Progress monitor: roster, averages, lab hours, leaderboard
- CSV grade export
- Animated, responsive landing page with four dark themes

## Tech Stack
Python · Flask · SQLite · Jinja2 · HTML/CSS/JavaScript

## Getting Started
    pip install -r requirements.txt
    python app.py
Open http://127.0.0.1:5000

Demo logins (password `demo123`):
- Professor: prof@lab.edu
- Student: student@lab.edu

## Auto-grade test format
One test per line as `input => expected output`, with `;` for new lines:

    2;3 => 5

## Security note
The auto-grader runs submitted code on the host machine. Run it inside a
Docker sandbox before any public deployment, and set the `SECRET_KEY`
environment variable.

## Roadmap
Batches/courses, email reminders, calendar view, plagiarism check,
PostgreSQL support.
