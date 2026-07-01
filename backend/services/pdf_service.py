"""
PDF Report Generation Service
Generates various reports in PDF format
"""
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO
from database import db
from models.application import Application
from models.student import Student
from models.company import Company
from models.drive import PlacementDrive


def generate_placement_summary_report(start_date=None, end_date=None):
    """Generate overall placement summary report"""
    if end_date is None:
        end_date = datetime.utcnow()
    if start_date is None:
        start_date = datetime(end_date.year, 1, 1)
    
    # Fetch data
    total_students = Student.query.count()
    total_companies = Company.query.count()
    total_drives = PlacementDrive.query.count()
    total_applications = Application.query.count()
    selected_applications = Application.query.filter_by(status='selected').count()
    rejected_applications = Application.query.filter_by(status='rejected').count()
    
    placement_rate = (selected_applications / total_applications * 100) if total_applications > 0 else 0
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    elements.append(Paragraph("Placement Summary Report", title_style))
    elements.append(Spacer(1, 0.3*inch))
    
    # Report date
    date_text = f"Report Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
    elements.append(Paragraph(date_text, styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Summary statistics table
    summary_data = [
        ['Metric', 'Count'],
        ['Total Students', str(total_students)],
        ['Total Companies', str(total_companies)],
        ['Total Drives', str(total_drives)],
        ['Total Applications', str(total_applications)],
        ['Selected Candidates', str(selected_applications)],
        ['Rejected Applications', str(rejected_applications)],
        ['Overall Placement Rate', f'{placement_rate:.2f}%']
    ]
    
    summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 0.5*inch))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_student_placement_report():
    """Generate student-wise placement report"""
    # Fetch all students with their placement status
    students = Student.query.all()
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=0.5*inch, leftMargin=0.5*inch)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=20,
        alignment=TA_CENTER
    )
    elements.append(Paragraph("Student Placement Report", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Student data table
    student_data = [
        ['Roll No', 'Name', 'Branch', 'CGPA', 'Applications', 'Selected']
    ]
    
    for student in students:
        total_apps = Application.query.filter_by(student_id=student.id).count()
        selected_apps = Application.query.filter_by(student_id=student.id, status='selected').count()
        
        student_data.append([
            str(student.id),
            student.user.name[:20] if student.user else 'N/A',
            student.branch or 'N/A',
            str(student.cgpa or 'N/A'),
            str(total_apps),
            str(selected_apps)
        ])
    
    # Create table
    student_table = Table(student_data, colWidths=[0.8*inch, 1.5*inch, 1*inch, 0.8*inch, 1*inch, 0.8*inch])
    student_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))
    
    elements.append(student_table)
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_company_performance_report():
    """Generate company performance report"""
    companies = Company.query.all()
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=0.5*inch, leftMargin=0.5*inch)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=20,
        alignment=TA_CENTER
    )
    elements.append(Paragraph("Company Performance Report", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Company data table
    company_data = [
        ['Company Name', 'Drives', 'Applications', 'Selected', 'Selection Rate']
    ]
    
    for company in companies:
        total_drives = PlacementDrive.query.filter_by(company_id=company.id).count()
        drive_ids = [d.id for d in company.drives]
        total_apps = Application.query.filter(Application.drive_id.in_(drive_ids)).count() if drive_ids else 0
        selected_apps = Application.query.filter(
            Application.drive_id.in_(drive_ids),
            Application.status == 'selected'
        ).count() if drive_ids else 0
        
        selection_rate = (selected_apps / total_apps * 100) if total_apps > 0 else 0
        
        company_data.append([
            company.name[:30],
            str(total_drives),
            str(total_apps),
            str(selected_apps),
            f'{selection_rate:.1f}%'
        ])
    
    # Create table
    company_table = Table(company_data, colWidths=[2*inch, 0.8*inch, 1.2*inch, 0.8*inch, 1.2*inch])
    company_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))
    
    elements.append(company_table)
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_application_details_report(drive_id=None, company_id=None):
    """Generate detailed application report"""
    query = Application.query
    
    if company_id:
        query = query.join(PlacementDrive).filter(PlacementDrive.company_id == company_id)
    elif drive_id:
        query = query.filter(Application.drive_id == drive_id)
    
    applications = query.all()
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=0.4*inch, leftMargin=0.4*inch)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=15,
        alignment=TA_CENTER
    )
    elements.append(Paragraph("Application Details Report", title_style))
    elements.append(Spacer(1, 0.15*inch))
    
    # Applications table
    app_data = [
        ['Student', 'Drive', 'Company', 'Date', 'Status']
    ]
    
    for app in applications:
        app_data.append([
            app.student.user.name[:20] if app.student and app.student.user else 'N/A',
            app.drive.job_title[:25] if app.drive else 'N/A',
            app.drive.company.name[:20] if app.drive and app.drive.company else 'N/A',
            app.application_date.strftime('%Y-%m-%d') if app.application_date else 'N/A',
            app.status
        ])
    
    # Create table
    app_table = Table(app_data, colWidths=[1.3*inch, 1.5*inch, 1.3*inch, 1*inch, 1.2*inch])
    app_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
    ]))
    
    elements.append(app_table)
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer
