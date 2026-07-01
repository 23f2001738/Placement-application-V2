from flask import Blueprint, request, jsonify, session, send_file
from datetime import datetime
from database import db
from models.user import User
from models.company import Company
from models.student import Student
from models.drive import PlacementDrive
from models.application import Application
from utils.auth_helpers import login_required
from services.realtime import (
    emit_to_admin, emit_to_company, emit_to_student,
    emit_to_all_students, emit_notification, broadcast_stats
)
from services.cache_service import cache_get, cache_set, invalidate_dashboard_cache
from services.pdf_service import (
    generate_placement_summary_report,
    generate_student_placement_report,
    generate_company_performance_report,
    generate_application_details_report
)

admin_bp = Blueprint('admin', __name__)


def _get_stats():
    return {
        'students': Student.query.count(),
        'companies': Company.query.count(),
        'drives': PlacementDrive.query.count(),
        'applications': Application.query.count(),
        'pending_companies': Company.query.filter_by(approval_status='pending').count(),
        'pending_drives': PlacementDrive.query.filter_by(status='pending').count()
    }


def _refresh_stats():
    invalidate_dashboard_cache()
    stats = _get_stats()
    broadcast_stats(stats)
    return stats


@admin_bp.route('/stats', methods=['GET'])
@login_required(roles=['admin'])
def get_stats():
    cached = cache_get('admin:stats')
    if cached:
        return jsonify(cached)
    stats = _get_stats()
    cache_set('admin:stats', stats, ttl=60)
    return jsonify(stats)


@admin_bp.route('/companies', methods=['GET'])
@login_required(roles=['admin'])
def get_companies():
    search = request.args.get('search', '').strip()
    query = Company.query
    if search:
        query = query.filter(Company.name.ilike(f'%{search}%'))
    companies = query.all()
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'hr_contact': c.hr_contact,
        'website': c.website,
        'status': c.approval_status,
        'user_id': c.user_id,
        'is_active': c.user.is_active if c.user else True
    } for c in companies])


@admin_bp.route('/students', methods=['GET'])
@login_required(roles=['admin'])
def get_students():
    search = request.args.get('search', '').strip()
    query = Student.query.join(User)
    if search:
        query = query.filter(
            db.or_(User.name.ilike(f'%{search}%'), Student.branch.ilike(f'%{search}%'))
        )
    students = query.all()
    return jsonify([{
        'id': s.id,
        'name': s.user.name,
        'email': s.user.email,
        'branch': s.branch,
        'cgpa': s.cgpa,
        'year': s.year,
        'is_active': s.user.is_active,
        'is_blacklisted': s.user.is_blacklisted
    } for s in students])


@admin_bp.route('/drives', methods=['GET'])
@login_required(roles=['admin'])
def get_drives():
    drives = PlacementDrive.query.all()
    return jsonify([{
        'id': d.id,
        'job_title': d.job_title,
        'location': d.location,
        'company_name': d.company.name if d.company else '',
        'status': d.status,
        'deadline': d.application_deadline.isoformat() if d.application_deadline else None,
        'applicants': len(d.applications)
    } for d in drives])


@admin_bp.route('/applications', methods=['GET'])
@login_required(roles=['admin'])
def get_applications():
    apps = Application.query.all()
    return jsonify([{
        'id': a.id,
        'student_name': a.student.user.name if a.student and a.student.user else '',
        'company_name': a.drive.company.name if a.drive and a.drive.company else '',
        'drive_title': a.drive.job_title if a.drive else '',
        'drive_location': a.drive.location if a.drive else '',
        'status': a.status,
        'application_date': a.application_date.isoformat() if a.application_date else None
    } for a in apps])


@admin_bp.route('/approve/company/<int:company_id>', methods=['POST'])
@login_required(roles=['admin'])
def approve_company(company_id):
    data = request.json or {}
    action = data.get('action', 'approve')
    company = Company.query.get(company_id)
    if not company:
        return jsonify({'message': 'Company not found'}), 404

    company.approval_status = 'approved' if action == 'approve' else 'rejected'
    db.session.commit()
    _refresh_stats()
    emit_to_admin('company_updated', {'id': company.id, 'status': company.approval_status})
    emit_to_company(company.id, 'company_status_changed', {
        'status': company.approval_status,
        'name': company.name
    })
    emit_notification(company.user_id, f'Company registration {company.approval_status}', 'success' if action == 'approve' else 'warning')
    return jsonify({'message': f'Company {company.approval_status}'})


@admin_bp.route('/approve/drive/<int:drive_id>', methods=['POST'])
@login_required(roles=['admin'])
def approve_drive(drive_id):
    data = request.json or {}
    action = data.get('action', 'approve')
    drive = PlacementDrive.query.get(drive_id)
    if not drive:
        return jsonify({'message': 'Drive not found'}), 404

    drive.status = 'approved' if action == 'approve' else 'rejected'
    db.session.commit()
    _refresh_stats()
    emit_to_admin('drive_updated', {'id': drive.id, 'status': drive.status})
    emit_to_company(drive.company_id, 'drive_status_changed', {
        'id': drive.id,
        'status': drive.status,
        'job_title': drive.job_title
    })
    if drive.status == 'approved':
        emit_to_all_students('new_drive', {
            'id': drive.id,
            'job_title': drive.job_title,
            'company_name': drive.company.name if drive.company else '',
            'location': drive.location
        })
    return jsonify({'message': f'Drive {drive.status}'})


@admin_bp.route('/deactivate/<role>/<int:profile_id>', methods=['POST'])
@login_required(roles=['admin'])
def deactivate_user(role, profile_id):
    data = request.json or {}
    blacklist = data.get('blacklist', False)

    if role == 'student':
        profile = Student.query.get(profile_id)
    elif role == 'company':
        profile = Company.query.get(profile_id)
    else:
        return jsonify({'message': 'Invalid role'}), 400

    if not profile:
        return jsonify({'message': 'Not found'}), 404

    user = profile.user
    user.is_active = not user.is_active
    user.is_blacklisted = blacklist and not user.is_active
    db.session.commit()
    _refresh_stats()
    emit_to_admin(f'{role}_updated', {'id': profile_id, 'is_active': user.is_active})
    return jsonify({'message': 'User status updated', 'is_active': user.is_active})


@admin_bp.route('/reports/placement-summary', methods=['GET'])
@login_required(roles=['admin'])
def report_placement_summary():
    """Generate placement summary PDF report"""
    try:
        pdf_buffer = generate_placement_summary_report()
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'placement_summary_{datetime.utcnow().strftime("%Y%m%d")}.pdf'
        )
    except Exception as e:
        return jsonify({'message': f'Error generating report: {str(e)}'}), 500


@admin_bp.route('/reports/student-placement', methods=['GET'])
@login_required(roles=['admin'])
def report_student_placement():
    """Generate student placement PDF report"""
    try:
        pdf_buffer = generate_student_placement_report()
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'student_placement_{datetime.utcnow().strftime("%Y%m%d")}.pdf'
        )
    except Exception as e:
        return jsonify({'message': f'Error generating report: {str(e)}'}), 500


@admin_bp.route('/reports/company-performance', methods=['GET'])
@login_required(roles=['admin'])
def report_company_performance():
    """Generate company performance PDF report"""
    try:
        pdf_buffer = generate_company_performance_report()
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'company_performance_{datetime.utcnow().strftime("%Y%m%d")}.pdf'
        )
    except Exception as e:
        return jsonify({'message': f'Error generating report: {str(e)}'}), 500


@admin_bp.route('/reports/applications', methods=['GET'])
@login_required(roles=['admin'])
def report_applications():
    """Generate applications detail PDF report"""
    try:
        drive_id = request.args.get('drive_id', type=int)
        company_id = request.args.get('company_id', type=int)
        
        pdf_buffer = generate_application_details_report(drive_id=drive_id, company_id=company_id)
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'applications_report_{datetime.utcnow().strftime("%Y%m%d")}.pdf'
        )
    except Exception as e:
        return jsonify({'message': f'Error generating report: {str(e)}'}), 500
