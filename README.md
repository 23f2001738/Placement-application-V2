# Placement Portal Application V2

## Overview
This project is a Flask-based placement portal with Vue.js frontend templates and Bootstrap styling. It supports three user roles: Admin, Company, and Student.

## Folder Structure
- `backend/` — Flask application, routes, models, services, and Celery tasks
- `frontend/` — Jinja templates and static assets for the UI
- `api.yaml` — YAML definition of the API endpoints
- `requirements.txt` — Python dependencies

## Prerequisites
- Python 3.10+ installed
- Redis running locally on `localhost:6379`

## Setup
1. Open a terminal in the project root.
2. Install dependencies using the system Python interpreter:
   ```powershell
   python -m pip install --user -r requirements.txt
   ```
3. Run the application:
   ```powershell
   python backend\app.py
   ```
4. Open the browser at:
   ```
   http://127.0.0.1:5000
   ```

> If `python` is not recognized on Windows, use `py` instead, for example: `py -m pip install --user -r requirements.txt`.

## Default Admin Login
- Username: `admin`
- Password: `admin123`

## Notes
- The SQLite database is created automatically when the app starts.
- Uploaded resumes are stored under `uploads/`.
- Templates are served from `frontend/templates/`.

## API Definition
The API endpoints are described in `api.yaml`.
