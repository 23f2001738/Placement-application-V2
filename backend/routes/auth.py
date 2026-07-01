from flask import Blueprint, request, jsonify, session
from database import db
from models.user import User
from models.company import Company
from models.student import Student
from services.realtime import emit_to_admin, emit_notification
from services.cache_service import invalidate_dashboard_cache

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register/student', methods=['POST'])
def register_student():
    data = request.json or {}
    if User.query.filter_by(username=data.get('username')).first():
        return jsonify({'message': 'Username already exists'}), 400

    user = User(
        username=data['username'],
        password=data['password'],
        role='student',
        name=data.get('name'),
        email=data.get('email')
    )
    db.session.add(user)
    db.session.flush()

    student = Student(
        user_id=user.id,
        branch=data.get('branch'),
        cgpa=data.get('cgpa'),
        year=data.get('year')
    )
    db.session.add(student)
    db.session.commit()
    invalidate_dashboard_cache()
    emit_to_admin('student_registered', {'name': user.name, 'branch': student.branch})
    return jsonify({'message': 'Student registered successfully'})


@auth_bp.route('/register/company', methods=['POST'])
def register_company():
    data = request.json or {}
    if User.query.filter_by(username=data.get('username')).first():
        return jsonify({'message': 'Username already exists'}), 400

    user = User(
        username=data['username'],
        password=data['password'],
        role='company',
        name=data.get('name'),
        email=data.get('email')
    )
    db.session.add(user)
    db.session.flush()

    company = Company(
        user_id=user.id,
        name=data.get('company_name'),
        hr_contact=data.get('hr_contact'),
        website=data.get('website')
    )
    db.session.add(company)
    db.session.commit()
    invalidate_dashboard_cache()
    emit_to_admin('company_registered', {'id': company.id, 'name': company.name})
    return jsonify({'message': 'Company registered, pending admin approval'})


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    user = User.query.filter_by(username=data.get('username'), password=data.get('password')).first()
    if not user or not user.is_active or user.is_blacklisted:
        return jsonify({'message': 'Invalid credentials or account deactivated'}), 401

    session['user_id'] = user.id
    session['role'] = user.role
    session['name'] = user.name

    profile_id = None
    if user.role == 'student' and user.student:
        profile_id = user.student.id
    elif user.role == 'company' and user.company:
        profile_id = user.company.id

    return jsonify({
        'message': 'Login successful',
        'role': user.role,
        'user_id': user.id,
        'profile_id': profile_id,
        'name': user.name
    })


@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out'})


@auth_bp.route('/me', methods=['GET'])
def me():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'message': 'Not authenticated'}), 401
    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404
    profile = {}
    if user.role == 'student' and user.student:
        profile = {
            'student_id': user.student.id,
            'branch': user.student.branch,
            'cgpa': user.student.cgpa,
            'year': user.student.year,
            'resume_path': user.student.resume_path,
            'resume_uploaded_at': user.student.resume_uploaded_at.isoformat() if user.student.resume_uploaded_at else None
        }
    elif user.role == 'company' and user.company:
        profile = {
            'company_id': user.company.id,
            'company_name': user.company.name,
            'approval_status': user.company.approval_status,
            'hr_contact': user.company.hr_contact,
            'website': user.company.website
        }
    return jsonify({
        'user_id': user.id,
        'role': user.role,
        'name': user.name,
        'email': user.email,
        'profile': profile
    })
