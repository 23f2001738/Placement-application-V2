import csv
import io
import os
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

from tasks.celery_app import celery_app


def _load_env():
    env_path = Path(__file__).resolve().parents[2] / '.env'
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue

        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env()


def _get_app_context():
    from app import app
    return app.app_context()


def _send_email(to_email, subject, html_body, attachment=None, filename='report.csv'):
    mail_user = os.getenv('MAIL_USERNAME', 'your_email@gmail.com')
    mail_pass = os.getenv('MAIL_PASSWORD', 'your_app_password')
    mail_server = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    mail_port = int(os.getenv('MAIL_PORT', '587'))
    use_tls = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'

    if mail_user == 'your_email@gmail.com':
        print(f'[EMAIL DEMO] To: {to_email} | Subject: {subject}')
        print(html_body[:200])
        return

    msg = MIMEMultipart()
    msg['From'] = mail_user
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html'))

    if attachment:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={filename}')
        msg.attach(part)

    try:
        with smtplib.SMTP(mail_server, mail_port, timeout=20) as server:
            server.ehlo()
            if use_tls:
                server.starttls()
            server.login(mail_user, mail_pass)
            server.send_message(msg)
        print(f'[EMAIL SENT] To: {to_email} | Subject: {subject}')
    except Exception as exc:
        print(f'[EMAIL ERROR] To: {to_email} | Subject: {subject} | Error: {exc}')
        raise


@celery_app.task(name='tasks.jobs.export_applications_csv')
def export_applications_csv(student_id, email):
    with _get_app_context():
        from database import db
        from models.application import Application
        from models.student import Student
        from extensions import socketio

        student = Student.query.get(student_id)
        apps = Application.query.filter_by(student_id=student_id).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Student ID', 'Company Name', 'Drive Title', 'Application Status', 'Application Date'])
        for a in apps:
            writer.writerow([
                student_id,
                a.drive.company.name if a.drive and a.drive.company else '',
                a.drive.job_title if a.drive else '',
                a.status,
                a.application_date.strftime('%Y-%m-%d') if a.application_date else ''
            ])

        csv_data = output.getvalue().encode('utf-8')
        _send_email(
            email,
            'Your Placement Application History',
            '<p>Your application export is attached.</p>',
            attachment=csv_data,
            filename=f'applications_{student_id}.csv'
        )

        if student and student.user:
            socketio.emit('export_complete', {
                'message': 'Your application history CSV has been sent to your email.'
            }, room=f'user_{student.user.id}', namespace='/')

        return {'status': 'completed', 'rows': len(apps)}


@celery_app.task(name='tasks.jobs.send_daily_deadline_reminders')
def send_daily_deadline_reminders():
    with _get_app_context():
        from models.drive import PlacementDrive
        from models.application import Application
        from models.student import Student

        tomorrow = datetime.utcnow() + timedelta(days=1)
        drives = PlacementDrive.query.filter(
            PlacementDrive.status == 'approved',
            PlacementDrive.application_deadline <= tomorrow,
            PlacementDrive.application_deadline >= datetime.utcnow()
        ).all()

        for drive in drives:
            applied_student_ids = {a.student_id for a in drive.applications}
            students = Student.query.all()
            for student in students:
                if student.id not in applied_student_ids and student.user and student.user.email:
                    _send_email(
                        student.user.email,
                        f'Reminder: {drive.job_title} deadline approaching',
                        f'<p>Apply before {drive.application_deadline} for {drive.job_title} at {drive.company.name}.</p>'
                    )
        return {'reminders_sent_for_drives': len(drives)}


@celery_app.task(name='tasks.jobs.send_monthly_activity_report')
def send_monthly_activity_report():
    with _get_app_context():
        from models.user import User
        from models.drive import PlacementDrive
        from models.application import Application

        admin = User.query.filter_by(role='admin').first()
        if not admin or not admin.email:
            admin_email = os.getenv('ADMIN_EMAIL', 'admin@institute.edu')
        else:
            admin_email = admin.email

        total_drives = PlacementDrive.query.count()
        total_applications = Application.query.count()
        selected = Application.query.filter_by(status='selected').count()

        html = f'''
        <html><body>
        <h2>Monthly Placement Activity Report</h2>
        <p>Generated on {datetime.utcnow().strftime('%Y-%m-%d')}</p>
        <ul>
            <li>Total Drives: {total_drives}</li>
            <li>Total Applications: {total_applications}</li>
            <li>Students Selected: {selected}</li>
        </ul>
        </body></html>
        '''
        _send_email(admin_email, 'Monthly Placement Activity Report', html)
        return {'report_sent': True}


@celery_app.task(name='tasks.jobs.process_resume')
def process_resume(application_id):
    """Process uploaded resume"""
    with _get_app_context():
        from models.application import Application
        from extensions import socketio

        application = Application.query.get(application_id)
        if not application or not application.resume_path:
            return {'status': 'failed', 'reason': 'Application or resume not found'}

        # Resume validation/processing can be added here
        # For now, just mark as processed
        application.last_updated = datetime.utcnow()

        from database import db
        db.session.commit()

        # Notify company about processed resume
        if application.drive and application.drive.company:
            socketio.emit('resume_processed', {
                'application_id': application_id,
                'student_name': application.student.user.name if application.student else ''
            }, room=f'company_{application.drive.company_id}', namespace='/')

        return {'status': 'completed', 'application_id': application_id}


@celery_app.task(name='tasks.jobs.send_interview_reminders')
def send_interview_reminders():
    """Send interview reminders to students"""
    with _get_app_context():
        from models.interview import InterviewSchedule
        from models.notification import Notification
        from database import db

        # Get interviews scheduled for next 24 hours
        now = datetime.utcnow()
        tomorrow = now + timedelta(hours=24)

        interviews = InterviewSchedule.query.filter(
            InterviewSchedule.interview_date >= now,
            InterviewSchedule.interview_date <= tomorrow,
            InterviewSchedule.status == 'scheduled'
        ).all()

        for interview in interviews:
            student = interview.application.student
            if student and student.user:
                # Create notification
                notification = Notification(
                    user_id=student.user_id,
                    title=f'Interview Reminder: {interview.application.drive.job_title}',
                    message=f'Your interview is scheduled for {interview.interview_date.strftime("%Y-%m-%d %H:%M")}',
                    notification_type='interview',
                    related_id=interview.id
                )
                db.session.add(notification)

                # Send email
                _send_email(
                    student.user.email,
                    f'Interview Reminder: {interview.application.drive.job_title}',
                    f'''
                    <html><body>
                    <h3>Interview Reminder</h3>
                    <p>Dear {student.user.name},</p>
                    <p>You have an interview scheduled for <strong>{interview.interview_date.strftime("%Y-%m-%d %H:%M")}</strong></p>
                    <p><strong>Interview Type:</strong> {interview.interview_type}</p>
                    <p><strong>Location/Link:</strong> {interview.location_or_link}</p>
                    <p>Best of luck!</p>
                    </body></html>
                    '''
                )

        db.session.commit()
        return {'reminders_sent': len(interviews)}


@celery_app.task(name='tasks.jobs.send_application_status_update')
def send_application_status_update(application_id):
    """Send application status update to student"""
    with _get_app_context():
        from models.application import Application
        from models.notification import Notification
        from database import db

        application = Application.query.get(application_id)
        if not application or not application.student:
            return {'status': 'failed', 'reason': 'Application not found'}

        student = application.student
        if not student.user or not student.user.email:
            return {'status': 'failed', 'reason': 'Student email not found'}

        # Create notification
        status_message = {
            'applied': 'Your application has been received',
            'shortlisted': 'Congratulations! You have been shortlisted',
            'selected': 'Congratulations! You have been selected',
            'rejected': 'Unfortunately, your application was not successful',
            'interview_scheduled': 'Your interview has been scheduled'
        }

        message = status_message.get(application.status, f'Your application status is now {application.status}')

        notification = Notification(
            user_id=student.user_id,
            title=f'Application Status Update: {application.drive.job_title}',
            message=message,
            notification_type='application',
            related_id=application_id
        )
        db.session.add(notification)
        db.session.commit()

        # Send email
        _send_email(
            student.user.email,
            f'Application Status Update: {application.drive.job_title}',
            f'''
            <html><body>
            <h3>Application Status Update</h3>
            <p>Dear {student.user.name},</p>
            <p>{message}</p>
            <p><strong>Company:</strong> {application.drive.company.name if application.drive.company else 'N/A'}</p>
            <p><strong>Position:</strong> {application.drive.job_title}</p>
            </body></html>
            '''
        )

        return {'status': 'completed', 'application_id': application_id}


@celery_app.task(name='tasks.jobs.cleanup_old_notifications')
def cleanup_old_notifications():
    """Clean up old notifications older than 30 days"""
    with _get_app_context():
        from models.notification import Notification
        from database import db

        cutoff_date = datetime.utcnow() - timedelta(days=30)

        deleted_count = Notification.query.filter(
            Notification.created_at < cutoff_date,
            Notification.is_read == True
        ).delete()

        db.session.commit()
        return {'deleted_notifications': deleted_count}


@celery_app.task(name='tasks.jobs.send_bulk_notifications')
def send_bulk_notifications(notification_ids):
    """Send notifications to multiple users"""
    with _get_app_context():
        from models.notification import Notification
        from models.user import User

        for notif_id in notification_ids:
            notification = Notification.query.get(notif_id)
            if notification:
                user = User.query.get(notification.user_id)
                if user and user.email:
                    _send_email(
                        user.email,
                        notification.title,
                        f'<html><body><p>{notification.message}</p></body></html>'
                    )

        return {'notifications_sent': len(notification_ids)}
