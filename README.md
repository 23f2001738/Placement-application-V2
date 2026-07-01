# Placement Portal Application V2

## Overview
This project is a Flask-based placement portal with Vue.js frontend templates and Bootstrap styling. It supports three user roles: Admin, Company, and Student.

## Folder Structure
- `backend/` — Flask application, routes, models, services, and Celery tasks
- `frontend/` — Jinja templates and static assets for the UI
- `submission_metadata.yaml` — project metadata and API documentation reference
- `api_definition.yaml` — YAML definition of the API endpoints
- `requirements.txt` — Python dependencies

## Prerequisites
- Python 3.10+ installed
- Redis running locally on `localhost:6379`
- Recommended: virtual environment

## Setup
1. Open a terminal in the project root.
2. Create a virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
4. Run the application:
   ```powershell
   python backend\app.py
   ```
5. Open the browser at:
   ```
   http://127.0.0.1:5000
   ```

## Default Admin Login
- Username: `admin`
- Password: `admin123`

## Notes
- The SQLite database is created automatically when the app starts.
- Uploaded resumes are stored under `uploads/`.
- Templates are served from `frontend/templates/`.
- Static assets are served from `frontend/static/`.

## API Definition
The API endpoints are described in `api_definition.yaml`.
