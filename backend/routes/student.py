from flask import Blueprint, request, jsonify, current_app, send_file
from datetime import datetime
import os
from database import db
from models.application import Application
from models.company import Company
from models.drive import PlacementDrive
from models.student import Student
from models.interview import InterviewSchedule
from models.notification import Notification
from utils.auth_helpers import login_required, get_current_user_id
from utils.file_handler import save_resume, delete_resume, get_resume_path
from services.realtime import emit_to_admin, emit_to_company
from services.notification_service import create_notification
from services.cache_service import cache_get, cache_set, invalidate_dashboard_cache

student_bp = Blueprint('student', __name__)


def _get_student():
    user_id = get_current_user_id()
    return Student.query.filter_by(user_id=user_id).first()


def _student_eligible(student, drive):
    if drive.min_cgpa and student.cgpa and student.cgpa < drive.min_cgpa:
        return False, f'Minimum CGPA required: {drive.min_cgpa}'
    if drive.eligible_year and student.year and student.year != drive.eligible_year:
        return False, f'Only year {drive.eligible_year} students eligible'
    if drive.eligible_branches and student.branch:
        branches = [b.strip().upper() for b in drive.eligible_branches.split(',')]
        if student.branch.upper() not in branches:
            return False, f'Branch {student.branch} not eligible'
    if drive.application_deadline and drive.application_deadline < datetime.utcnow():
        return False, 'Application deadline has passed'
    return True, 'Eligible'


@student_bp.route('/drives', methods=['GET'])
@login_required(roles=['student'])
def get_drives():
    search = request.args.get('search', '').strip()
    min_cgpa = request.args.get('min_cgpa', type=float)
    branch = request.args.get('branch', '').strip()
    year = request.args.get('year', type=int)
    sort_by = request.args.get('sort_by', 'created_at')  # created_at, deadline, company
    
    cache_key = f'student:drives:{search}:{min_cgpa}:{branch}:{year}:{sort_by}'
    cached = cache_get(cache_key) if not search else None
    if cached:
        return jsonify(cached)

    query = PlacementDrive.query.filter_by(status='approved')
    
    # Apply filters
    if search:
        query = query.filter(
            db.or_(
                PlacementDrive.job_title.ilike(f'%{search}%'),
                PlacementDrive.job_description.ilike(f'%{search}%'),
                PlacementDrive.eligibility_criteria.ilike(f'%{search}%')
            )
        )
    
    if min_cgpa is not None:
        query = query.filter(
            db.or_(PlacementDrive.min_cgpa <= min_cgpa, PlacementDrive.min_cgpa.is_(None))
        )
    
    if branch:
        query = query.filter(
            db.or_(
                PlacementDrive.eligible_branches.contains(branch),
                PlacementDrive.eligible_branches.is_(None)
            )
        )
    
    if year:
        query = query.filter(
            db.or_(PlacementDrive.eligible_year == year, PlacementDrive.eligible_year.is_(None))
        )
    
    # Apply sorting
    if sort_by == 'deadline':
        query = query.order_by(PlacementDrive.application_deadline.asc())
    elif sort_by == 'company':
        query = query.join(PlacementDrive.company).order_by(Company.name.asc())
    else:
        query = query.order_by(PlacementDrive.created_at.desc())

    student = _get_student()
    drives = query.all()
    applied_ids = set()
    if student:
        applied_ids = {a.drive_id for a in Application.query.filter_by(student_id=student.id).all()}

    result = []
    for d in drives:
        eligible, reason = _student_eligible(student, d) if student else (True, '')
        result.append({
            'id': d.id,
            'job_title': d.job_title,
            'location': d.location,
            'job_description': d.job_description,
            'company_name': d.company.name if d.company else '',
            'eligibility_criteria': d.eligibility_criteria,
            'min_cgpa': d.min_cgpa,
            'eligible_branches': d.eligible_branches,
            'eligible_year': d.eligible_year,
            'deadline': d.application_deadline.isoformat() if d.application_deadline else None,
            'eligible': eligible,
            'eligibility_reason': reason,
            'already_applied': d.id in applied_ids
        })

    if not search:
        cache_set(cache_key, result, ttl=120)
    return jsonify(result)


@student_bp.route('/applications', methods=['GET'])
@login_required(roles=['student'])
def get_applications():
    student = _get_student()
    if not student:
        return jsonify({'message': 'Student profile not found'}), 404

    status_filter = request.args.get('status', '').strip()
    
    query = Application.query.filter_by(student_id=student.id)
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    apps = query.order_by(Application.application_date.desc()).all()
    
    return jsonify([{
        'id': a.id,
        'drive_id': a.drive_id,
        'drive_title': a.drive.job_title if a.drive else '',
        'drive_location': a.drive.location if a.drive else '',
        'company_name': a.drive.company.name if a.drive and a.drive.company else '',
        'status': a.status,
        'application_date': a.application_date.isoformat() if a.application_date else None,
        'resume_uploaded': a.resume_path is not None or student.resume_path is not None,
        'interview_count': len(a.interviews) if a.interviews else 0
    } for a in apps])


@student_bp.route('/apply/<int:drive_id>', methods=['POST'])
@login_required(roles=['student'])
def apply_to_drive(drive_id):
    student = _get_student()
    if not student:
        return jsonify({'message': 'Student profile not found'}), 404

    drive = PlacementDrive.query.get(drive_id)
    if not drive or drive.status != 'approved':
        return jsonify({'message': 'Drive not available'}), 404

    existing = Application.query.filter_by(student_id=student.id, drive_id=drive_id).first()
    if existing:
        return jsonify({'message': 'You have already applied to this drive'}), 400

    eligible, reason = _student_eligible(student, drive)
    if not eligible:
        return jsonify({'message': reason}), 400

    application = Application(student_id=student.id, drive_id=drive_id, status='applied')
    
    # Auto-link student's resume if they have one
    if student.resume_path:
        application.resume_path = student.resume_path
        application.resume_uploaded_at = student.resume_uploaded_at
    
    db.session.add(application)
    db.session.commit()
    invalidate_dashboard_cache()

    emit_to_company(drive.company_id, 'new_application', {
        'id': application.id,
        'student_name': student.user.name,
        'drive_title': drive.job_title
    })
    emit_to_admin('application_submitted', {
        'student_name': student.user.name,
        'drive_title': drive.job_title,
        'company_name': drive.company.name if drive.company else ''
    })
    create_notification(
        student.user_id,
        'Application Submitted',
        f'Your application for {drive.job_title} at {drive.company.name if drive.company else "company"} was submitted.',
        'application',
        application.id
    )
    return jsonify({'message': 'Application submitted successfully!'})


@student_bp.route('/profile', methods=['GET', 'PUT'])
@login_required(roles=['student'])
def profile():
    student = _get_student()
    if not student:
        return jsonify({'message': 'Student profile not found'}), 404

    if request.method == 'GET':
        return jsonify({
            'id': student.id,
            'name': student.user.name,
            'email': student.user.email,
            'branch': student.branch,
            'cgpa': student.cgpa,
            'year': student.year,
            'bio': student.bio,
            'skills': student.skills,
            'resume_path': student.resume_path,
            'resume_uploaded_at': student.resume_uploaded_at.isoformat() if student.resume_uploaded_at else None,
            'is_verified': student.is_verified
        })

    data = request.json or {}
    student.branch = data.get('branch', student.branch)
    student.cgpa = data.get('cgpa', student.cgpa)
    student.year = data.get('year', student.year)
    student.bio = data.get('bio', student.bio)
    student.skills = data.get('skills', student.skills)
    if student.user:
        student.user.name = data.get('name', student.user.name)
        student.user.email = data.get('email', student.user.email)
    db.session.commit()
    invalidate_dashboard_cache()
    return jsonify({'message': 'Profile updated'})


@student_bp.route('/export-applications', methods=['POST'])
@login_required(roles=['student'])
def export_applications():
    from tasks.jobs import export_applications_csv
    student = _get_student()
    if not student:
        return jsonify({'message': 'Student profile not found'}), 404

    task = export_applications_csv.delay(student.id, student.user.email)
    return jsonify({'message': 'Export started. You will be notified when ready.', 'task_id': task.id})


@student_bp.route('/resume/upload', methods=['POST'])
@login_required(roles=['student'])
def upload_resume():
    """Upload or update student resume"""
    student = _get_student()
    if not student:
        return jsonify({'message': 'Student profile not found'}), 404

    if 'resume' not in request.files:
        return jsonify({'message': 'No resume file provided'}), 400

    file = request.files['resume']
    
    # Save new resume
    resume_path = save_resume(file, current_app.config['UPLOAD_FOLDER'], student.user_id)
    if not resume_path:
        return jsonify({'message': 'Invalid file. Only PDF, DOC, DOCX allowed (max 5MB)'}), 400

    # Delete old resume if exists
    if student.resume_path:
        delete_resume(student.resume_path, current_app.config['UPLOAD_FOLDER'])

    # Update student record
    student.resume_path = resume_path
    student.resume_uploaded_at = datetime.utcnow()
    db.session.commit()
    
    invalidate_dashboard_cache()
    emit_to_admin('student_resume_uploaded', {
        'student_name': student.user.name,
        'student_id': student.id
    })

    return jsonify({
        'message': 'Resume uploaded successfully',
        'resume_path': resume_path
    })


@student_bp.route('/resume/download', methods=['GET'])
@login_required(roles=['student'])
def download_own_resume():
    """Download own resume"""
    student = _get_student()
    if not student or not student.resume_path:
        return jsonify({'message': 'Resume not found'}), 404

    file_path = get_resume_path(current_app.config['UPLOAD_FOLDER'], student.resume_path)
    if not file_path or not os.path.exists(file_path):
        return jsonify({'message': 'Resume file not found'}), 404

    return send_file(file_path, as_attachment=True)


@student_bp.route('/notifications', methods=['GET'])
@login_required(roles=['student'])
def get_notifications():
    """Get student notifications"""
    user_id = get_current_user_id()
    limit = request.args.get('limit', 20, type=int)
    
    notifications = Notification.query.filter_by(user_id=user_id).order_by(
        Notification.created_at.desc()
    ).limit(limit).all()
    
    return jsonify([{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'type': n.notification_type,
        'is_read': n.is_read,
        'created_at': n.created_at.isoformat()
    } for n in notifications])


@student_bp.route('/notifications/<int:notification_id>/read', methods=['PUT'])
@login_required(roles=['student'])
def mark_notification_read(notification_id):
    """Mark notification as read"""
    user_id = get_current_user_id()
    notification = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
    
    if not notification:
        return jsonify({'message': 'Notification not found'}), 404

    notification.is_read = True
    notification.read_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'message': 'Notification marked as read'})


@student_bp.route('/interviews', methods=['GET'])
@login_required(roles=['student'])
def get_interviews():
    """Get all interviews for student"""
    student = _get_student()
    if not student:
        return jsonify({'message': 'Student profile not found'}), 404

    interviews = InterviewSchedule.query.join(Application).filter(
        Application.student_id == student.id
    ).all()

    return jsonify([{
        'id': i.id,
        'application_id': i.application_id,
        'company_name': i.application.drive.company.name if i.application.drive and i.application.drive.company else '',
        'drive_title': i.application.drive.job_title if i.application.drive else '',
        'interview_date': i.interview_date.isoformat() if i.interview_date else None,
        'interview_time': i.interview_time,
        'interview_type': i.interview_type,
        'interview_round': i.interview_round,
        'location_or_link': i.location_or_link,
        'status': i.status,
        'student_response': i.student_response,
        'feedback': i.feedback,
        'notes': i.notes
    } for i in interviews])


@student_bp.route('/interviews/<int:interview_id>', methods=['GET'])
@login_required(roles=['student'])
def get_interview_detail(interview_id):
    """Get interview details"""
    student = _get_student()
    interview = InterviewSchedule.query.get(interview_id)

    if not interview or interview.application.student_id != student.id:
        return jsonify({'message': 'Interview not found'}), 404

    return jsonify({
        'id': interview.id,
        'application_id': interview.application_id,
        'company_name': interview.application.drive.company.name if interview.application.drive and interview.application.drive.company else '',
        'drive_title': interview.application.drive.job_title if interview.application.drive else '',
        'interview_date': interview.interview_date.isoformat() if interview.interview_date else None,
        'interview_time': interview.interview_time,
        'interview_type': interview.interview_type,
        'interview_round': interview.interview_round,
        'location_or_link': interview.location_or_link,
        'status': interview.status,
        'student_response': interview.student_response,
        'feedback': interview.feedback,
        'notes': interview.notes,
        'created_at': interview.created_at.isoformat() if interview.created_at else None,
        'updated_at': interview.updated_at.isoformat() if interview.updated_at else None
    })


@student_bp.route('/interviews/<int:interview_id>/response', methods=['PUT'])
@login_required(roles=['student'])
def submit_interview_response(interview_id):
    """Student can acknowledge/respond to interview"""
    student = _get_student()
    interview = InterviewSchedule.query.get(interview_id)

    if not interview or not interview.application or interview.application.student_id != student.id:
        return jsonify({'message': 'Interview not found'}), 404

    data = request.json or {}
    response = data.get('response')  # accepted/declined

    if response not in ['accepted', 'declined']:
        return jsonify({'message': 'Invalid response'}), 400

    interview.student_response = response
    if response == 'declined':
        interview.status = 'declined_by_student'

    db.session.commit()
    invalidate_dashboard_cache()

    return jsonify({'message': f'Interview response recorded: {response}'})
