"""
Enhanced Manus Web Platform - Cursor.com inspired AI coding assistant
Features:
- Real-time WebSocket communication
- Advanced file management with auto-save
- Multi-user support with authentication
- GitHub integration
- Background task processing
- Multi-API support with rate limiting
"""

import os
import json
import mimetypes
from datetime import datetime
from pathlib import Path
import asyncio
import threading
import uuid
import shutil
from werkzeug.utils import secure_filename

from flask import Flask, render_template, request, jsonify, send_from_directory, Response, redirect, url_for, flash, send_file
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from dotenv import load_dotenv
import git

# Import our models and components
from app.models import db, User, ChatSession, ChatMessage, Task, UserFile, GitHubProject
from app.websocket_manager import init_websocket_manager, get_websocket_manager
from app.tasks import celery, process_file_upload, import_github_project, create_project_download
from app.logger import logger
from app.api_key_manager import APIKeyManager
from app.enhanced_agent import EnhancedManus

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production'),
    SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'sqlite:///manus_enhanced.db'),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    UPLOAD_FOLDER='uploads',
    WORKSPACE_FOLDER='workspaces',
    MAX_CONTENT_LENGTH=100 * 1024 * 1024,  # 100MB max file size
    REDIS_URL=os.getenv('REDIS_URL', 'redis://localhost:6379/0')
)

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['WORKSPACE_FOLDER'], exist_ok=True)
os.makedirs('temp', exist_ok=True)
os.makedirs('logs', exist_ok=True)

# Initialize WebSocket manager
ws_manager = init_websocket_manager(socketio)

# Initialize API key manager
api_manager = APIKeyManager()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

# ========================= AUTHENTICATION ROUTES =========================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            return jsonify({'success': True, 'redirect': '/'})
        else:
            return jsonify({'success': False, 'message': 'Invalid credentials'})
    
    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        # Check if user exists
        if User.query.filter_by(username=username).first():
            return jsonify({'success': False, 'message': 'Username already exists'})
        
        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'message': 'Email already exists'})
        
        # Create new user
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        # Create user workspace
        user_workspace = os.path.join(app.config['WORKSPACE_FOLDER'], user.id)
        os.makedirs(user_workspace, exist_ok=True)
        
        login_user(user)
        return jsonify({'success': True, 'redirect': '/'})
    
    return render_template('auth/register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ========================= MAIN APPLICATION ROUTES =========================

@app.route('/')
@login_required
def index():
    """Main application interface - Cursor-like IDE"""
    # Get user's recent sessions
    recent_sessions = ChatSession.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).order_by(ChatSession.updated_at.desc()).limit(5).all()
    
    # Get user's files
    user_workspace = os.path.join(app.config['WORKSPACE_FOLDER'], current_user.id)
    files = []
    if os.path.exists(user_workspace):
        files = get_files_recursive(user_workspace)
    
    # Get user's GitHub projects
    github_projects = GitHubProject.query.filter_by(
        user_id=current_user.id,
        clone_status='completed'
    ).all()
    
    return render_template('ide/main.html', 
                         recent_sessions=[s.to_dict() for s in recent_sessions],
                         files=files,
                         github_projects=[p.to_dict() for p in github_projects],
                         user=current_user.to_dict())

@app.route('/api/file/save', methods=['POST'])
@login_required
def save_file():
    """Save file with auto-save functionality"""
    try:
        data = request.get_json()
        file_path = data.get('file_path')
        content = data.get('content')
        
        if not file_path or content is None:
            return jsonify({'success': False, 'message': 'Missing file path or content'})
        
        # Ensure file is in user's workspace
        user_workspace = os.path.join(app.config['WORKSPACE_FOLDER'], current_user.id)
        full_path = os.path.join(user_workspace, file_path.lstrip('/'))
        
        # Security check - ensure path is within user workspace
        if not os.path.abspath(full_path).startswith(os.path.abspath(user_workspace)):
            return jsonify({'success': False, 'message': 'Invalid file path'})
        
        # Create directory if needed
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Save file with backup
        backup_path = f"{full_path}.backup"
        if os.path.exists(full_path):
            shutil.copy2(full_path, backup_path)
        
        # Write content
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Update or create file record
        user_file = UserFile.query.filter_by(
            user_id=current_user.id,
            file_path=full_path
        ).first()
        
        if not user_file:
            user_file = UserFile(
                user_id=current_user.id,
                filename=os.path.basename(full_path),
                original_filename=os.path.basename(full_path),
                file_path=full_path,
                file_size=len(content.encode('utf-8')),
                mime_type=mimetypes.guess_type(full_path)[0]
            )
            db.session.add(user_file)
        else:
            user_file.file_size = len(content.encode('utf-8'))
            user_file.upload_time = datetime.utcnow()
        
        db.session.commit()
        
        # Clean up old backup
        if os.path.exists(backup_path):
            os.remove(backup_path)
        
        # Send WebSocket update
        if ws_manager:
            ws_manager.send_user_notification(current_user.id, {
                'type': 'file_saved',
                'file_path': file_path,
                'timestamp': datetime.utcnow().isoformat()
            })
        
        return jsonify({
            'success': True, 
            'message': 'File saved successfully',
            'file_id': user_file.id,
            'size': user_file.file_size
        })
        
    except Exception as e:
        logger.error(f"Error saving file: {e}")
        return jsonify({'success': False, 'message': f'Error saving file: {str(e)}'})

@app.route('/api/file/load', methods=['POST'])
@login_required
def load_file():
    """Load file content"""
    try:
        data = request.get_json()
        file_path = data.get('file_path')
        
        if not file_path:
            return jsonify({'success': False, 'message': 'Missing file path'})
        
        user_workspace = os.path.join(app.config['WORKSPACE_FOLDER'], current_user.id)
        full_path = os.path.join(user_workspace, file_path.lstrip('/'))
        
        # Security check
        if not os.path.abspath(full_path).startswith(os.path.abspath(user_workspace)):
            return jsonify({'success': False, 'message': 'Invalid file path'})
        
        if not os.path.exists(full_path):
            return jsonify({'success': False, 'message': 'File not found'})
        
        # Read file content
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Get file info
        file_info = {
            'content': content,
            'size': os.path.getsize(full_path),
            'modified': datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat(),
            'type': mimetypes.guess_type(full_path)[0]
        }
        
        return jsonify({'success': True, 'file': file_info})
        
    except Exception as e:
        logger.error(f"Error loading file: {e}")
        return jsonify({'success': False, 'message': f'Error loading file: {str(e)}'})

@app.route('/api/file/upload', methods=['POST'])
@login_required
def upload_files():
    """Upload multiple files with progress tracking"""
    try:
        uploaded_files = []
        
        for file_key in request.files:
            files = request.files.getlist(file_key)
            
            for file in files:
                if file.filename:
                    # Secure filename
                    filename = secure_filename(file.filename)
                    file_id = str(uuid.uuid4())
                    
                    # Create user upload directory
                    user_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], current_user.id)
                    os.makedirs(user_upload_dir, exist_ok=True)
                    
                    # Save file
                    file_path = os.path.join(user_upload_dir, f"{file_id}_{filename}")
                    file.save(file_path)
                    
                    # Create file record
                    user_file = UserFile(
                        user_id=current_user.id,
                        filename=f"{file_id}_{filename}",
                        original_filename=filename,
                        file_path=file_path,
                        file_size=os.path.getsize(file_path),
                        mime_type=file.content_type
                    )
                    db.session.add(user_file)
                    db.session.commit()
                    
                    # Create processing task
                    task = Task(
                        user_id=current_user.id,
                        task_type='file_processing',
                        status='pending',
                        current_step='File uploaded, queued for processing'
                    )
                    db.session.add(task)
                    db.session.commit()
                    
                    # Start background processing
                    process_file_upload.delay(task.id, user_file.id, current_user.id)
                    
                    uploaded_files.append({
                        'file_id': user_file.id,
                        'filename': filename,
                        'task_id': task.id,
                        'size': user_file.file_size
                    })
        
        return jsonify({
            'success': True,
            'message': f'Uploaded {len(uploaded_files)} files',
            'files': uploaded_files
        })
        
    except Exception as e:
        logger.error(f"Error uploading files: {e}")
        return jsonify({'success': False, 'message': f'Upload failed: {str(e)}'})

@app.route('/api/github/import', methods=['POST'])
@login_required
def import_github():
    """Import GitHub repository"""
    try:
        data = request.get_json()
        repo_url = data.get('repo_url')
        
        if not repo_url:
            return jsonify({'success': False, 'message': 'Repository URL required'})
        
        # Validate GitHub URL
        if 'github.com' not in repo_url:
            return jsonify({'success': False, 'message': 'Only GitHub repositories are supported'})
        
        # Create import task
        task = Task(
            user_id=current_user.id,
            task_type='github_import',
            status='pending',
            current_step='Preparing to import repository'
        )
        db.session.add(task)
        db.session.commit()
        
        # Start background import
        import_github_project.delay(task.id, repo_url, current_user.id)
        
        return jsonify({
            'success': True,
            'message': 'GitHub import started',
            'task_id': task.id
        })
        
    except Exception as e:
        logger.error(f"Error starting GitHub import: {e}")
        return jsonify({'success': False, 'message': f'Import failed: {str(e)}'})

@app.route('/api/chat/sessions', methods=['GET'])
@login_required
def get_chat_sessions():
    """Get user's chat sessions"""
    sessions = ChatSession.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).order_by(ChatSession.updated_at.desc()).all()
    
    return jsonify({
        'success': True,
        'sessions': [session.to_dict() for session in sessions]
    })

@app.route('/api/chat/session/<session_id>/messages', methods=['GET'])
@login_required
def get_chat_messages(session_id):
    """Get messages for a chat session"""
    session = ChatSession.query.filter_by(
        id=session_id,
        user_id=current_user.id
    ).first()
    
    if not session:
        return jsonify({'success': False, 'message': 'Session not found'})
    
    messages = ChatMessage.query.filter_by(
        session_id=session_id
    ).order_by(ChatMessage.timestamp.asc()).all()
    
    return jsonify({
        'success': True,
        'messages': [message.to_dict() for message in messages]
    })

@app.route('/api/tasks', methods=['GET'])
@login_required
def get_user_tasks():
    """Get user's tasks with status"""
    tasks = Task.query.filter_by(
        user_id=current_user.id
    ).order_by(Task.created_at.desc()).limit(20).all()
    
    return jsonify({
        'success': True,
        'tasks': [task.to_dict() for task in tasks]
    })

@app.route('/api/download/<task_id>')
@login_required
def download_package(task_id):
    """Download task result package"""
    task = Task.query.filter_by(
        id=task_id,
        user_id=current_user.id,
        status='completed'
    ).first()
    
    if not task:
        return jsonify({'success': False, 'message': 'Task not found or not completed'})
    
    download_path = task.result_data.get('download_path')
    if not download_path or not os.path.exists(download_path):
        return jsonify({'success': False, 'message': 'Download file not found'})
    
    return send_file(download_path, as_attachment=True, 
                    download_name=f"project_{task_id}.zip")

@app.route('/api/workspace/files')
@login_required
def get_workspace_files():
    """Get user's workspace file tree"""
    user_workspace = os.path.join(app.config['WORKSPACE_FOLDER'], current_user.id)
    
    if not os.path.exists(user_workspace):
        os.makedirs(user_workspace, exist_ok=True)
    
    files = get_files_recursive(user_workspace)
    return jsonify({'success': True, 'files': files})

def get_files_recursive(directory):
    """Get recursive file listing with metadata"""
    files = []
    
    try:
        for root, dirs, file_list in os.walk(directory):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in file_list:
                if file.startswith('.'):
                    continue
                
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, directory)
                
                try:
                    stat = os.stat(file_path)
                    files.append({
                        'path': relative_path.replace('\\', '/'),
                        'name': file,
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        'type': mimetypes.guess_type(file_path)[0] or 'unknown'
                    })
                except OSError:
                    continue
                    
    except Exception as e:
        logger.error(f"Error reading directory {directory}: {e}")
    
    return files

# ========================= WebSocket Events =========================

@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        join_room(f"user_{current_user.id}")
        emit('connection_status', {
            'status': 'connected',
            'user': current_user.to_dict(),
            'timestamp': datetime.utcnow().isoformat()
        })
        logger.info(f"User {current_user.username} connected via WebSocket")

@socketio.on('join_session')
def handle_join_session(data):
    if current_user.is_authenticated:
        session_id = data.get('session_id')
        if session_id:
            join_room(f"chat_{session_id}")
            emit('joined_session', {'session_id': session_id})

@socketio.on('send_message')
def handle_send_message(data):
    if current_user.is_authenticated:
        message = data.get('message', '').strip()
        session_id = data.get('session_id')
        
        if not message:
            emit('error', {'message': 'Empty message not allowed'})
            return
        
        # Create or get session
        if not session_id:
            session = ChatSession(
                user_id=current_user.id,
                title=message[:50] + "..." if len(message) > 50 else message
            )
            db.session.add(session)
            db.session.commit()
            session_id = session.id
            
            emit('session_created', {'session_id': session_id})
        
        # Process message
        if ws_manager:
            ws_manager._handle_chat_message(session_id, message)

# ========================= Error Handlers =========================

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

# ========================= Application Initialization =========================

def create_app():
    """Application factory"""
    with app.app_context():
        # Create database tables
        db.create_all()
        
        # Create default admin user if not exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@localhost',
                workspace_quota=10000,  # 10GB
                api_credits=10000
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            
            # Create admin workspace
            admin_workspace = os.path.join(app.config['WORKSPACE_FOLDER'], admin.id)
            os.makedirs(admin_workspace, exist_ok=True)
            
            logger.info("Created default admin user: admin/admin123")
    
    return app

if __name__ == '__main__':
    app = create_app()
    
    # Start Celery worker in separate thread
    import threading
    from app.tasks import start_celery_worker
    
    celery_thread = threading.Thread(target=start_celery_worker, daemon=True)
    celery_thread.start()
    
    # Run the application
    socketio.run(app, 
                host='0.0.0.0', 
                port=5000, 
                debug=True, 
                allow_unsafe_werkzeug=True)