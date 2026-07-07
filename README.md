# Placement Portal Application

A comprehensive campus placement management system built with **Flask**, **Vue.js** (via Jinja templates), **SQLite**, **Redis**, and **Celery**.

## Features

### Admin
- Dashboard with real-time statistics
- Approve/reject companies and placement drives
- Manage students and companies (activate/deactivate/blacklist)
- Generate PDF reports (Placement Summary, Student-wise, Company Performance, Applications)

### Company
- Register and get approved by admin
- Post placement drives with eligibility criteria
- View and manage applications
- Download student resumes
- Schedule and manage interviews
- Real-time notifications

### Student
- Browse and filter placement drives
- Apply to eligible drives
- Upload and manage resume (PDF/DOC/DOCX)
- Track application status
- View and respond to interview schedules
- Export application history via email
- Real-time notifications

### General
- Real-time updates using Flask-SocketIO + Redis
- Background jobs with Celery + Redis
- Secure file upload with validation
- Responsive Bootstrap UI

## Tech Stack

- **Backend**: Flask, Flask-SQLAlchemy, Flask-SocketIO
- **Database**: SQLite
- **Cache & Real-time**: Redis
- **Background Tasks**: Celery + Redis
- **Frontend**: Jinja2 Templates + Vue.js (CDN) + Bootstrap 5
- **PDF Generation**: ReportLab
- **Others**: Flask-CORS, Werkzeug

## Prerequisites

- Python 3.10+
- Redis server running on `localhost:6379`

## Setup Instructions

1. **Clone / Extract** the project

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start Redis** (Make sure Redis is running)
   ```bash
   # Windows
   redis-server

   # Linux/Mac
   sudo systemctl start redis-server
   ```

4. **Run the Application**
   ```bash
   python backend/app.py
   ```

5. **Access the Application**
   Open your browser and go to: **http://127.0.0.1:5000**

## Default Credentials

- **Admin**
  - Username: `admin`
  - Password: `admin123`

## Project Structure

```
placement_portal/
├── backend/
│   ├── app.py
│   ├── models/
│   ├── routes/
│   ├── services/
│   ├── tasks/
│   ├── utils/
│   └── instance/placement.db
├── frontend/
│   └── templates/
├── uploads/
│   └── resumes/
├── requirements.txt
├── README.md
└── api.yaml
```

## Key Features Implemented

- Role-based authentication (Admin, Company, Student)
- Resume upload & download
- Real-time notifications & live updates
- Advanced filtering and search
- PDF report generation
- Background email exports and reminders

---

**Note**: Detailed API documentation is available in [`api.yaml`](./api.yaml).
