from extensions import socketio


def emit_to_admin(event, data):
    socketio.emit(event, data, room='admin', namespace='/')

def emit_to_company(company_id, event, data):
    socketio.emit(event, data, room=f'company_{company_id}', namespace='/')

def emit_to_student(student_id, event, data):
    socketio.emit(event, data, room=f'student_{student_id}', namespace='/')

def emit_to_all_students(event, data):
    socketio.emit(event, data, room='students', namespace='/')

def emit_notification(user_id, message, ntype='info'):
    socketio.emit('notification', {
        'message': message,
        'type': ntype
    }, room=f'user_{user_id}', namespace='/')

def broadcast_stats(stats):
    emit_to_admin('stats_updated', stats)
