from flask import session
from flask_socketio import join_room, leave_room
from extensions import socketio
from models.user import User
from models.student import Student
from models.company import Company


@socketio.on('connect')
def on_connect():
    user_id = session.get('user_id')
    role = session.get('role')
    if not user_id:
        return False

    join_room(f'user_{user_id}')

    if role == 'admin':
        join_room('admin')
    elif role == 'student':
        student = Student.query.filter_by(user_id=user_id).first()
        if student:
            join_room(f'student_{student.id}')
        join_room('students')
    elif role == 'company':
        company = Company.query.filter_by(user_id=user_id).first()
        if company:
            join_room(f'company_{company.id}')

    socketio.emit('connected', {'message': 'Real-time connection established', 'role': role})


@socketio.on('disconnect')
def on_disconnect():
    user_id = session.get('user_id')
    role = session.get('role')
    if user_id:
        leave_room(f'user_{user_id}')
    if role == 'admin':
        leave_room('admin')
    elif role == 'student':
        student = Student.query.filter_by(user_id=user_id).first() if user_id else None
        if student:
            leave_room(f'student_{student.id}')
        leave_room('students')
    elif role == 'company':
        company = Company.query.filter_by(user_id=user_id).first() if user_id else None
        if company:
            leave_room(f'company_{company.id}')
