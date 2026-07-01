from database import db
from datetime import datetime


class InterviewSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    interview_date = db.Column(db.DateTime, nullable=False)
    interview_time = db.Column(db.String(10))  # HH:MM format
    interview_type = db.Column(db.String(50), default='technical')  # technical, hr, group_discussion, etc.
    interview_round = db.Column(db.Integer, default=1)
    location_or_link = db.Column(db.String(500))  # Physical location or Zoom/Meet link
    status = db.Column(db.String(20), default='scheduled')  # scheduled, completed, cancelled
    student_response = db.Column(db.String(20))  # accepted, declined
    notes = db.Column(db.Text)
    feedback = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    application = db.relationship('Application', backref=db.backref('interviews', lazy=True, cascade='all, delete-orphan'))
