from functools import wraps
from flask import session, jsonify


def login_required(roles=None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user_id = session.get('user_id')
            role = session.get('role')
            if not user_id or not role:
                return jsonify({'message': 'Authentication required'}), 401
            if roles and role not in roles:
                return jsonify({'message': 'Access denied'}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def get_current_user_id():
    return session.get('user_id')

def get_current_role():
    return session.get('role')
