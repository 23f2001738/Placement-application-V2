from flask import Blueprint, request, jsonify, session, send_file, current_app
from datetime import datetime
import os
from database import db
from models.company import Company
from models.drive import PlacementDrive
from models.application import Application
from models.student import Student
from models.interview import InterviewSchedule
from models.notification import Notification
from utils.auth_helpers import login_required, get_current_user_id
from utils.file_handler import get_resume_path
from services.realtime import emit_to_admin, emit_to_student
from services.notification_service import create_notification
from services.cache_service import invalidate_dashboard_cache

company_bp = Blueprint('company', __name__)


def _get_company():
    user_id = get_current_user_id()
    return Company.query.filter_by(user_id=user_id).first()


@company_bp.route('/profile', methods=['GET'])
@login_required(roles=['company'])
def get_profile():
    company = _get_company()
    if not company:
        return jsonify({'message': 'Company profile not found'}), 404
    return jsonify({
        'id': company.id,
        'name': company.name,
        'hr_contact': company.hr_contact,
        'website': company.website,
        'approval_status': company.approval_status
    })


@company_bp.route('/profile', methods=['PUT'])
@login_required(roles=['company'])
def update_profile():
    company = _get_company()
    if not company:
        return jsonify({'message': 'Company profile not found'}), 404
    data = request.json or {}
    company.name = data.get('name', company.name)
    company.hr_contact = data.get('hr_contact', company.hr_contact)
    company.website = data.get('website', company.website)
    db.session.commit()
    return jsonify({'message': 'Profile updated'})


@company_bp.route('/drives', methods=['GET'])
@login_required(roles=['company'])
def get_drives():
    company = _get_company()
    if not company:
        return jsonify({'message': 'Company not found'}), 404
    drives = PlacementDrive.query.filter_by(company_id=company.id).all()
    return jsonify([{
        'id': d.id,
        'job_title': d.job_title,
        'job_description': d.job_description,
        'location': d.location,
        'status': d.status,
        'deadline': d.application_deadline.isoformat() if d.application_deadline else None,
        'applicants': len(d.applications),
        'eligibility_criteria': d.eligibility_criteria
    } for d in drives])


@company_bp.route('/drives', methods=['POST'])
@login_required(roles=['company'])
def create_drive():
    company = _get_company()
    if not company:
        return jsonify({'message': 'Company not found'}), 404
    if company.approval_status != 'approved':
        return jsonify({'message': 'Company must be approved before creating drives'}), 403

    data = request.json or {}
    deadline = None
    if data.get('application_deadline'):
        deadline = datetime.fromisoformat(data['application_deadline'].replace('Z', ''))

    drive = PlacementDrive(
        company_id=company.id,
        job_title=data['job_title'],
        job_description=data.get('job_description'),
        location=data.get('location'),
        eligibility_criteria=data.get('eligibility_criteria'),
        min_cgpa=data.get('min_cgpa', 0.0),
        eligible_branches=data.get('eligible_branches'),
        eligible_year=data.get('eligible_year'),
        application_deadline=deadline,
        status='pending'
    )
    db.session.add(drive)
    db.session.commit()
    invalidate_dashboard_cache()
    emit_to_admin('drive_created', {
        'id': drive.id,
        'job_title': drive.job_title,
        'company_name': company.name,
        'location': drive.location
    })
    return jsonify({'message': 'Drive created, pending admin approval', 'id': drive.id})


@company_bp.route('/applications', methods=['GET'])
@login_required(roles=['company'])
def get_applications():
    company = _get_company()
    if not company:
        return jsonify({'message': 'Company not found'}), 404

    drive_ids = [d.id for d in company.drives]
    
    status_filter = request.args.get('status', '').strip()
    search = request.args.get('search', '').strip()
    sort_by = request.args.get('sort_by', 'application_date')  # application_date, cgpa, name
    
    query = Application.query.filter(Application.drive_id.in_(drive_ids) if drive_ids else False)
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    if search:
        query = query.join(Application.student).filter(
            db.or_(
                Student.user.name.ilike(f'%{search}%'),
                Student.branch.ilike(f'%{search}%')
            )
        )
    
    # Apply sorting
    if sort_by == 'cgpa':
        query = query.join(Application.student).order_by(Student.cgpa.desc())
    elif sort_by == 'name':
        query = query.join(Application.student).order_by(Student.user.name.asc())
    else:
        query = query.order_by(Application.application_date.desc())
    
    apps = query.all() if drive_ids else []
    
    return jsonify([{
        'id': a.id,
        'student_id': a.student_id,
        'student_name': a.student.user.name if a.student and a.student.user else '',
        'branch': a.student.branch if a.student else '',
        'cgpa': a.student.cgpa if a.student else None,
        'drive_id': a.drive_id,
        'drive_title': a.drive.job_title if a.drive else '',
        'drive_location': a.drive.location if a.drive else '',
        'status': a.status,
        'application_date': a.application_date.isoformat() if a.application_date else None,
        'has_resume': (a.resume_path is not None) or (a.student and a.student.resume_path is not None),
        'interview_count': len(a.interviews) if a.interviews else 0
    } for a in apps])


@company_bp.route('/applications/<int:app_id>/status', methods=['PUT'])
@login_required(roles=['company'])
def update_application_status(app_id):
    company = _get_company()
    application = Application.query.get(app_id)
    if not application or not application.drive or application.drive.company_id != company.id:
        return jsonify({'message': 'Application not found'}), 404

    data = request.json or {}
    new_status = data.get('status')
    valid = {'applied', 'shortlisted', 'selected', 'rejected'}
    if new_status not in valid:
        return jsonify({'message': f'Status must be one of {valid}'}), 400

    application.status = new_status
    db.session.commit()
    invalidate_dashboard_cache()

    emit_to_student(application.student_id, 'application_updated', {
        'id': application.id,
        'status': application.status,
        'drive_title': application.drive.job_title,
        'company_name': company.name
    })
    create_notification(
        application.student.user_id,
        'Application Update',
        f'Application for {application.drive.job_title} updated to {new_status}',
        'application',
        application.id
    )
    return jsonify({'message': 'Application status updated', 'status': new_status})


@company_bp.route('/applications/<int:app_id>/resume/download', methods=['GET'])
@login_required(roles=['company'])
def download_application_resume(app_id):
    """Download student's resume for an application"""
    company = _get_company()
    application = Application.query.get(app_id)
    
    if not application or not application.drive or application.drive.company_id != company.id:
        return jsonify({'message': 'Application not found'}), 404

    student = application.student
    resume_path = application.resume_path or student.resume_path
    
    if not resume_path:
        return jsonify({'message': 'Resume not found for this application'}), 404

    file_path = get_resume_path(current_app.config['UPLOAD_FOLDER'], resume_path)
    if not file_path or not os.path.exists(file_path):
        return jsonify({'message': 'Resume file not found'}), 404

    return send_file(file_path, as_attachment=True)


@company_bp.route('/applications/<int:app_id>/resume/preview', methods=['GET'])
@login_required(roles=['company'])
def preview_application_resume(app_id):
    """Get resume information for preview"""
    company = _get_company()
    application = Application.query.get(app_id)
    
    if not application or not application.drive or application.drive.company_id != company.id:
        return jsonify({'message': 'Application not found'}), 404

    student = application.student
    resume_path = application.resume_path or student.resume_path
    
    if not resume_path:
        return jsonify({'message': 'Resume not found'}), 404

    file_size = 0
    file_ext = 'unknown'
    if resume_path:
        parts = resume_path.rsplit('.', 1)
        file_ext = parts[1].lower() if len(parts) > 1 else 'unknown'
        
        file_path = get_resume_path(current_app.config['UPLOAD_FOLDER'], resume_path)
        if file_path and os.path.exists(file_path):
            file_size = os.path.getsize(file_path)

    return jsonify({
        'student_name': student.user.name,
        'branch': student.branch,
        'cgpa': student.cgpa,
        'resume_path': resume_path,
        'file_type': file_ext,
        'file_size': file_size,
        'uploaded_at': application.resume_uploaded_at.isoformat() if application.resume_uploaded_at else None
    })


@company_bp.route('/applications/<int:app_id>/resume/upload', methods=['POST'])
@login_required(roles=['company'])
def upload_application_resume(app_id):
    """Company uploads resume during application review"""
    from utils.file_handler import save_resume
    
    company = _get_company()
    application = Application.query.get(app_id)
    
    if not application or not application.drive or application.drive.company_id != company.id:
        return jsonify({'message': 'Application not found'}), 404

    if 'resume' not in request.files:
        return jsonify({'message': 'No resume file provided'}), 400

    file = request.files['resume']
    resume_path = save_resume(file, current_app.config['UPLOAD_FOLDER'], application.student.user_id)
    
    if not resume_path:
        return jsonify({'message': 'Invalid file. Only PDF, DOC, DOCX allowed (max 5MB)'}), 400

    application.resume_path = resume_path
    application.resume_uploaded_at = datetime.utcnow()
    db.session.commit()

    create_notification(
        application.student.user_id,
        'Resume Uploaded',
        f'Resume uploaded for {application.drive.job_title} application',
        'document',
        application.id
    )
    
    return jsonify({'message': 'Resume uploaded successfully', 'resume_path': resume_path})


@company_bp.route('/interviews', methods=['GET'])
@login_required(roles=['company'])
def get_interviews():
    """Get all interviews scheduled by company"""
    company = _get_company()
    if not company:
        return jsonify({'message': 'Company not found'}), 404

    drive_ids = [d.id for d in company.drives]
    interviews = InterviewSchedule.query.join(Application).filter(
        Application.drive_id.in_(drive_ids) if drive_ids else False
    ).all()

    return jsonify([{
        'id': i.id,
        'application_id': i.application_id,
        'student_name': i.application.student.user.name if i.application.student else '',
        'drive_title': i.application.drive.job_title if i.application.drive else '',
        'interview_date': i.interview_date.isoformat() if i.interview_date else None,
        'interview_time': i.interview_time,
        'interview_type': i.interview_type,
        'interview_round': i.interview_round,
        'location_or_link': i.location_or_link,
        'status': i.status,
        'notes': i.notes,
        'feedback': i.feedback
    } for i in interviews])


@company_bp.route('/interviews', methods=['POST'])
@login_required(roles=['company'])
def schedule_interview():
    """Schedule an interview with a student"""
    company = _get_company()
    application = Application.query.get(request.json.get('application_id'))
    
    if not application or not application.drive or application.drive.company_id != company.id:
        return jsonify({'message': 'Application not found'}), 404

    data = request.json or {}
    
    try:
        interview_date = datetime.fromisoformat(data.get('interview_date', '').replace('Z', ''))
    except:
        return jsonify({'message': 'Invalid interview date format'}), 400

    interview = InterviewSchedule(
        application_id=application.id,
        interview_date=interview_date,
        interview_time=data.get('interview_time', ''),
        interview_type=data.get('interview_type', 'technical'),
        interview_round=data.get('interview_round', 1),
        location_or_link=data.get('location_or_link', ''),
        notes=data.get('notes', ''),
        status='scheduled'
    )
    
    db.session.add(interview)
    application.status = 'interview_scheduled'
    db.session.commit()
    
    invalidate_dashboard_cache()
    
    # Notify student
    create_notification(
        application.student.user_id,
        'Interview Scheduled',
        f'Interview scheduled for {application.drive.job_title} on {interview_date.strftime("%Y-%m-%d %H:%M")}',
        'interview',
        interview.id
    )
    emit_to_student(application.student_id, 'interview_scheduled', {
        'id': interview.id,
        'drive_title': application.drive.job_title,
        'interview_date': interview_date.isoformat(),
        'interview_time': interview.interview_time,
        'location_or_link': interview.location_or_link
    })

    return jsonify({'message': 'Interview scheduled successfully', 'interview_id': interview.id})


@company_bp.route('/interviews/<int:interview_id>', methods=['PUT'])
@login_required(roles=['company'])
def update_interview(interview_id):
    """Update interview details"""
    company = _get_company()
    interview = InterviewSchedule.query.get(interview_id)
    
    if not interview or not interview.application.drive or interview.application.drive.company_id != company.id:
        return jsonify({'message': 'Interview not found'}), 404

    data = request.json or {}
    
    if 'interview_date' in data and data['interview_date']:
        try:
            interview.interview_date = datetime.fromisoformat(data['interview_date'].replace('Z', ''))
        except:
            return jsonify({'message': 'Invalid interview date format'}), 400
    
    interview.interview_time = data.get('interview_time', interview.interview_time)
    interview.location_or_link = data.get('location_or_link', interview.location_or_link)
    interview.notes = data.get('notes', interview.notes)
    interview.updated_at = datetime.utcnow()
    
    db.session.commit()
    invalidate_dashboard_cache()
    
    return jsonify({'message': 'Interview updated successfully'})


@company_bp.route('/interviews/<int:interview_id>/complete', methods=['PUT'])
@login_required(roles=['company'])
def complete_interview(interview_id):
    """Mark interview as completed with feedback"""
    company = _get_company()
    interview = InterviewSchedule.query.get(interview_id)
    
    if not interview or not interview.application.drive or interview.application.drive.company_id != company.id:
        return jsonify({'message': 'Interview not found'}), 404

    data = request.json or {}
    interview.status = 'completed'
    interview.feedback = data.get('feedback', '')
    interview.updated_at = datetime.utcnow()
    
    db.session.commit()
    invalidate_dashboard_cache()
    
    return jsonify({'message': 'Interview marked as completed'})


@company_bp.route('/interviews/<int:interview_id>/cancel', methods=['PUT'])
@login_required(roles=['company'])
def cancel_interview(interview_id):
    """Cancel interview"""
    company = _get_company()
    interview = InterviewSchedule.query.get(interview_id)
    
    if not interview or not interview.application.drive or interview.application.drive.company_id != company.id:
        return jsonify({'message': 'Interview not found'}), 404

    interview.status = 'cancelled'
    interview.updated_at = datetime.utcnow()
    
    db.session.commit()
    invalidate_dashboard_cache()
    
    # Notify student
    create_notification(
        interview.application.student.user_id,
        'Interview Cancelled',
        f'Interview for {interview.application.drive.job_title} has been cancelled',
        'interview',
        interview.id
    )
    
    return jsonify({'message': 'Interview cancelled'})
