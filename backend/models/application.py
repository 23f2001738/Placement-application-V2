from database import db
from datetime import datetime


class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    drive_id = db.Column(db.Integer, db.ForeignKey('placement_drive.id'), nullable=False)
    application_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='applied')  # applied, under_review, interview_scheduled, selected, rejected
    resume_path = db.Column(db.String(300))  # Path to submitted resume
    resume_uploaded_at = db.Column(db.DateTime)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = db.relationship('Student', backref=db.backref('applications', lazy=True))
    drive = db.relationship('PlacementDrive', backref=db.backref('applications', lazy=True))

    __table_args__ = (db.UniqueConstraint('student_id', 'drive_id', name='unique_student_drive'),)
