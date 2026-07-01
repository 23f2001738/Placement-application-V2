from database import db
from datetime import datetime


class PlacementDrive(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    job_title = db.Column(db.String(100), nullable=False)
    job_description = db.Column(db.Text)
    location = db.Column(db.String(200))
    eligibility_criteria = db.Column(db.String(200))
    min_cgpa = db.Column(db.Float, default=0.0)
    eligible_branches = db.Column(db.String(200))
    eligible_year = db.Column(db.Integer)
    application_deadline = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    company = db.relationship('Company', backref=db.backref('drives', lazy=True))
