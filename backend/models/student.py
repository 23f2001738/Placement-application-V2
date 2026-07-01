from database import db
from datetime import datetime


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    branch = db.Column(db.String(50))
    cgpa = db.Column(db.Float)
    year = db.Column(db.Integer)
    resume_path = db.Column(db.String(300))  # Path to resume file
    resume_uploaded_at = db.Column(db.DateTime)  # When resume was uploaded
    bio = db.Column(db.Text)  # Student bio/summary
    skills = db.Column(db.Text)  # Comma-separated skills
    is_verified = db.Column(db.Boolean, default=False)

    user = db.relationship('User', backref=db.backref('student', uselist=False))
