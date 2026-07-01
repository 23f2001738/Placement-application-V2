import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_file(file):
    """Validate uploaded file"""
    if not file or file.filename == '':
        return False, 'No file selected'
    
    if not allowed_file(file.filename):
        return False, f'Only {", ".join(ALLOWED_EXTENSIONS)} files allowed'
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)  # Reset file pointer
    
    if file_size > MAX_FILE_SIZE:
        return False, f'File size exceeds {MAX_FILE_SIZE // (1024*1024)}MB limit'
    
    return True, 'File valid'


def save_resume(file, upload_folder, user_id):
    """Save uploaded resume and return file path"""
    if not file:
        return None
    
    valid, msg = validate_file(file)
    if not valid:
        return None
    
    # Create user-specific folder
    user_folder = os.path.join(upload_folder, 'resumes', str(user_id))
    os.makedirs(user_folder, exist_ok=True)
    
    # Generate unique filename
    ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
    filename = f"resume_{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(user_folder, filename)
    
    # Save file
    file.save(filepath)
    
    # Return relative path for database storage
    return os.path.join('resumes', str(user_id), filename).replace('\\', '/')


def delete_resume(file_path, upload_folder):
    """Delete resume file"""
    if not file_path:
        return True
    
    full_path = os.path.join(upload_folder, file_path)
    try:
        if os.path.exists(full_path):
            os.remove(full_path)
        return True
    except Exception:
        return False


def get_resume_path(upload_folder, file_path):
    """Get full path for resume file"""
    if not file_path:
        return None
    return os.path.join(upload_folder, file_path)
