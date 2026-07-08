import os
from flask import Flask, jsonify, render_template, session
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from database import db
from extensions import redis_client, socketio
from dotenv import load_dotenv

load_dotenv()

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
frontend_dir = os.path.join(base_dir, 'frontend')

app = Flask(
    __name__,
    template_folder=os.path.join(frontend_dir, 'templates'),
    static_folder=os.path.join(frontend_dir, 'static'),
    static_url_path='/static'
)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'super_secret_key_change_in_production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///placement.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(base_dir, 'uploads')

# JWT Configuration
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', app.config['SECRET_KEY'])
app.config['JWT_TOKEN_LOCATION'] = ['headers']
app.config['JWT_HEADER_NAME'] = 'Authorization'
app.config['JWT_HEADER_TYPE'] = 'Bearer'

# Initialize extensions
db.init_app(app)
jwt = JWTManager(app)

# CORS Configuration for Vue.js frontend
CORS(app, 
     origins=['http://localhost:5173', 'http://localhost:3000'],
     supports_credentials=True,
     allow_headers=['Content-Type', 'Authorization'],
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH'])


try:
    redis_client.ping()
    socketio.init_app(app, message_queue='redis://localhost:6379/3')
except Exception:
    socketio.init_app(app)

# Create uploads directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Register API blueprints
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.company import company_bp
from routes.student import student_bp

app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(admin_bp, url_prefix='/api/admin')
app.register_blueprint(company_bp, url_prefix='/api/company')
app.register_blueprint(student_bp, url_prefix='/api/student')

# Socket.io events
try:
    import socket_events  # noqa: E402, F401
except ImportError:
    pass


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'message': 'Endpoint not found'}), 404


@app.errorhandler(500)
def server_error(error):
    return jsonify({'message': 'Internal server error'}), 500


@app.errorhandler(401)
def unauthorized(error):
    return jsonify({'message': 'Unauthorized access'}), 401


@app.errorhandler(403)
def forbidden(error):
    return jsonify({'message': 'Forbidden'}), 403


# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'message': 'API is running'}), 200


# Frontend page routes
@app.route('/', methods=['GET'])
def login_page():
    return render_template('login.html')


@app.route('/register/student', methods=['GET'])
def register_student_page():
    return render_template('register_student.html')


@app.route('/register/company', methods=['GET'])
def register_company_page():
    return render_template('register_company.html')


@app.route('/company/dashboard', methods=['GET'])
def company_dashboard_page():
    return render_template('company_dashboard.html')


@app.route('/student/dashboard', methods=['GET'])
def student_dashboard_page():
    return render_template('student/dashboard.html', name=session.get('name', ''))


@app.route('/admin/dashboard', methods=['GET'])
def admin_dashboard_page():
    return render_template('admin_dashboard.html')


# JWT error handlers
@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    """Load user from JWT token."""
    from models.user import User
    identity = jwt_data['sub']
    return User.query.get(identity)


@jwt.invalid_token_loader
def invalid_token_callback(error):
    return jsonify({'message': 'Invalid token'}), 401


@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_data):
    return jsonify({'message': 'Token has expired'}), 401


@jwt.unauthorized_loader
def missing_token_callback(error):
    return jsonify({'message': 'Missing authorization token'}), 401


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    print('🚀 API Server started at http://127.0.0.1:5000')
    socketio.run(app, debug=True, host='127.0.0.1', port=5000, allow_unsafe_werkzeug=True, use_reloader=False)

