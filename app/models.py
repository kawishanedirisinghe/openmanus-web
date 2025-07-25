"""
Database models for the enhanced chat application
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import json

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """User model for authentication and user management"""
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    workspace_quota = db.Column(db.Integer, default=1000)  # MB
    api_credits = db.Column(db.Integer, default=1000)
    
    # Relationships
    chat_sessions = db.relationship('ChatSession', backref='user', lazy=True, cascade='all, delete-orphan')
    tasks = db.relationship('Task', backref='user', lazy=True, cascade='all, delete-orphan')
    files = db.relationship('UserFile', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat(),
            'workspace_quota': self.workspace_quota,
            'api_credits': self.api_credits
        }


class ChatSession(db.Model):
    """Chat session model to persist conversations"""
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    metadata = db.Column(db.JSON, default=dict)
    
    # Relationships
    messages = db.relationship('ChatMessage', backref='session', lazy=True, cascade='all, delete-orphan')
    tasks = db.relationship('Task', backref='session', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'message_count': len(self.messages),
            'metadata': self.metadata
        }


class ChatMessage(db.Model):
    """Individual chat messages within sessions"""
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = db.Column(db.String(36), db.ForeignKey('chat_session.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    metadata = db.Column(db.JSON, default=dict)  # Store tool calls, status updates, etc.
    
    def to_dict(self):
        return {
            'id': self.id,
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }


class Task(db.Model):
    """Background task tracking"""
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    session_id = db.Column(db.String(36), db.ForeignKey('chat_session.id'), nullable=True)
    task_type = db.Column(db.String(50), nullable=False)  # 'chat', 'file_processing', 'github_import'
    status = db.Column(db.String(20), default='pending')  # 'pending', 'running', 'completed', 'failed'
    progress = db.Column(db.Integer, default=0)  # 0-100
    current_step = db.Column(db.String(200), nullable=True)
    result_data = db.Column(db.JSON, default=dict)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    celery_task_id = db.Column(db.String(255), nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'task_type': self.task_type,
            'status': self.status,
            'progress': self.progress,
            'current_step': self.current_step,
            'result_data': self.result_data,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }


class UserFile(db.Model):
    """User uploaded files and workspace management"""
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    mime_type = db.Column(db.String(100), nullable=True)
    upload_time = db.Column(db.DateTime, default=datetime.utcnow)
    is_processed = db.Column(db.Boolean, default=False)
    processing_result = db.Column(db.JSON, default=dict)
    
    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'upload_time': self.upload_time.isoformat(),
            'is_processed': self.is_processed,
            'processing_result': self.processing_result
        }


class GitHubProject(db.Model):
    """Imported GitHub projects"""
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    repo_url = db.Column(db.String(500), nullable=False)
    repo_name = db.Column(db.String(255), nullable=False)
    local_path = db.Column(db.String(500), nullable=False)
    clone_status = db.Column(db.String(20), default='pending')  # 'pending', 'cloning', 'completed', 'failed'
    imported_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_sync = db.Column(db.DateTime, nullable=True)
    metadata = db.Column(db.JSON, default=dict)
    
    def to_dict(self):
        return {
            'id': self.id,
            'repo_url': self.repo_url,
            'repo_name': self.repo_name,
            'clone_status': self.clone_status,
            'imported_at': self.imported_at.isoformat(),
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'metadata': self.metadata
        }


class APIUsage(db.Model):
    """Track API usage per user"""
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    api_provider = db.Column(db.String(50), nullable=False)
    model_name = db.Column(db.String(100), nullable=False)
    tokens_used = db.Column(db.Integer, nullable=False)
    cost = db.Column(db.Float, nullable=False)
    request_time = db.Column(db.DateTime, default=datetime.utcnow)
    session_id = db.Column(db.String(36), nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'api_provider': self.api_provider,
            'model_name': self.model_name,
            'tokens_used': self.tokens_used,
            'cost': self.cost,
            'request_time': self.request_time.isoformat()
        }