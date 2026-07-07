import os
from flask import Flask, render_template, session, redirect, url_for
from flask_cors import CORS
from database import db
from extensions import redis_client, socketio

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
frontend_dir = os.path.join(base_dir, 'frontend')
app = Flask(__name__, template_folder=os.path.join(frontend_dir, 'templates'), static_folder=os.path.join(frontend_dir, 'static'))
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'super_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///placement.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

db.init_app(app)
CORS(app, supports_credentials=True)

try:
    redis_client.ping()
    socketio.init_app(app, message_queue='redis://localhost:6379/3')
except Exception:
    socketio.init_app(app)

os.makedirs('uploads', exist_ok=True)

from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.company import company_bp
from routes.student import student_bp

app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(admin_bp, url_prefix='/api/admin')
app.register_blueprint(company_bp, url_prefix='/api/company')
app.register_blueprint(student_bp, url_prefix='/api/student')

import socket_events  # noqa: E402, F401


def _require_role(role):
    if session.get('role') != role:
        return redirect(url_for('index'))
    return None


@app.route('/')
def index():
    if session.get('user_id'):
        role = session.get('role')
        if role == 'admin':
            return redirect(url_for('admin_dashboard'))
        if role == 'student':
            return redirect(url_for('student_dashboard'))
        if role == 'company':
            return redirect(url_for('company_dashboard'))
    return render_template('login.html')


@app.route('/student/dashboard')
def student_dashboard():
    if err := _require_role('student'):
        return err
    return render_template('student/dashboard.html', name=session.get('name', 'Student'))


@app.route('/admin/dashboard')
def admin_dashboard():
    if err := _require_role('admin'):
        return err
    return render_template('admin_dashboard.html')


@app.route('/company/dashboard')
def company_dashboard():
    if err := _require_role('company'):
        return err
    return render_template('company_dashboard.html')


@app.route('/register/student')
def register_student_page():
    return render_template('register_student.html')


@app.route('/register/company')
def register_company_page():
    return render_template('register_company.html')


def init_db():
    from models.user import User
    from models.company import Company
    from models.student import Student
    from models.drive import PlacementDrive
    from models.application import Application
    from models.interview import InterviewSchedule
    from models.notification import Notification
    from sqlalchemy import inspect, text

    db.create_all()
    _migrate_schema(inspect(db.engine))

    if not User.query.filter_by(role='admin').first():
        admin = User(
            username='admin',
            password='admin123',
            role='admin',
            name='Institute Admin',
            email=os.getenv('ADMIN_EMAIL', 'admin@institute.edu')
        )
        db.session.add(admin)
        db.session.commit()
        print('Default Admin Created -> admin / admin123')


def _migrate_schema(insp):
    """Add new columns to existing SQLite tables without manual DB edits."""
    from sqlalchemy import text
    migrations = {
        'user': [('is_blacklisted', 'BOOLEAN DEFAULT 0')],
        'placement_drive': [
            ('min_cgpa', 'FLOAT DEFAULT 0.0'),
            ('eligible_branches', 'VARCHAR(200)'),
            ('location', 'VARCHAR(200)'),
            ('eligible_year', 'INTEGER'),
            ('created_at', 'DATETIME'),
        ],
        'student': [
            ('resume_path', 'VARCHAR(300)'),
            ('resume_uploaded_at', 'DATETIME'),
            ('bio', 'TEXT'),
            ('skills', 'TEXT'),
            ('is_verified', 'BOOLEAN DEFAULT 0'),
        ],
        'application': [
            ('resume_path', 'VARCHAR(300)'),
            ('resume_uploaded_at', 'DATETIME'),
            ('last_updated', 'DATETIME'),
        ],
        'interview_schedule': [
            ('student_response', 'VARCHAR(20)'),
        ],
    }
    for table, columns in migrations.items():
        if table not in insp.get_table_names():
            continue
        existing = {c['name'] for c in insp.get_columns(table)}
        for col_name, col_type in columns:
            if col_name not in existing:
                db.session.execute(text(f'ALTER TABLE {table} ADD COLUMN {col_name} {col_type}'))
    db.session.commit()


if __name__ == '__main__':
    with app.app_context():
        init_db()
    print('Server started at http://127.0.0.1:5000')
    socketio.run(app, debug=True, host='127.0.0.1', port=5000, allow_unsafe_werkzeug=True, use_reloader=False)
