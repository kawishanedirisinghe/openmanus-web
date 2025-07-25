"""
Advanced AI Web Platform - Main Flask Application
Similar to Replit AI and Manus.ai with OpenManus multi-API key integration
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import sys
import uuid
import json
from datetime import datetime
import asyncio
import threading
from werkzeug.security import generate_password_hash, check_password_hash

# Add the parent directory to the path to import OpenManus modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api_key_manager import APIKeyManager
from app.llm_client_wrapper import LLMClientWrapper
from app.config import Config

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize OpenManus components
config = Config()
api_key_manager = APIKeyManager(config)
llm_wrapper = LLMClientWrapper(api_key_manager)

# In-memory storage for demo (use database in production)
users = {}
chat_sessions = {}
user_preferences = {}

class ChatSession:
    def __init__(self, user_id, session_id):
        self.user_id = user_id
        self.session_id = session_id
        self.messages = []
        self.created_at = datetime.now()
        self.model = "gpt-4"
        self.temperature = 0.7
        self.max_tokens = 2048

    def add_message(self, role, content, metadata=None):
        message = {
            'id': str(uuid.uuid4()),
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        self.messages.append(message)
        return message

@app.route('/')
def index():
    """Main dashboard page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""
    if request.method == 'POST':
        username = request.json.get('username')
        password = request.json.get('password')
        
        if username in users and check_password_hash(users[username]['password'], password):
            session['user_id'] = users[username]['id']
            session['username'] = username
            return jsonify({'success': True, 'redirect': url_for('index')})
        else:
            return jsonify({'success': False, 'error': 'Invalid credentials'})
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page"""
    if request.method == 'POST':
        username = request.json.get('username')
        password = request.json.get('password')
        email = request.json.get('email')
        
        if username in users:
            return jsonify({'success': False, 'error': 'Username already exists'})
        
        user_id = str(uuid.uuid4())
        users[username] = {
            'id': user_id,
            'username': username,
            'email': email,
            'password': generate_password_hash(password),
            'created_at': datetime.now().isoformat()
        }
        
        # Initialize user preferences
        user_preferences[user_id] = {
            'theme': 'dark',
            'default_model': 'gpt-4',
            'temperature': 0.7,
            'max_tokens': 2048,
            'auto_save': True
        }
        
        session['user_id'] = user_id
        session['username'] = username
        return jsonify({'success': True, 'redirect': url_for('index')})
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    """User logout"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/chat/sessions')
def get_chat_sessions():
    """Get user's chat sessions"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    user_sessions = []
    
    for session_id, chat_session in chat_sessions.items():
        if chat_session.user_id == user_id:
            user_sessions.append({
                'id': session_id,
                'created_at': chat_session.created_at.isoformat(),
                'message_count': len(chat_session.messages),
                'last_message': chat_session.messages[-1]['content'][:50] + '...' if chat_session.messages else 'New chat'
            })
    
    return jsonify(user_sessions)

@app.route('/api/chat/session/<session_id>')
def get_chat_session(session_id):
    """Get specific chat session"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if session_id not in chat_sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    chat_session = chat_sessions[session_id]
    if chat_session.user_id != session['user_id']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    return jsonify({
        'id': session_id,
        'messages': chat_session.messages,
        'model': chat_session.model,
        'temperature': chat_session.temperature,
        'max_tokens': chat_session.max_tokens
    })

@app.route('/api/chat/session', methods=['POST'])
def create_chat_session():
    """Create new chat session"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    session_id = str(uuid.uuid4())
    user_id = session['user_id']
    
    chat_sessions[session_id] = ChatSession(user_id, session_id)
    
    return jsonify({'session_id': session_id})

@app.route('/api/preferences')
def get_preferences():
    """Get user preferences"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    return jsonify(user_preferences.get(user_id, {}))

@app.route('/api/preferences', methods=['POST'])
def update_preferences():
    """Update user preferences"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    preferences = request.json
    
    if user_id not in user_preferences:
        user_preferences[user_id] = {}
    
    user_preferences[user_id].update(preferences)
    return jsonify({'success': True})

@app.route('/api/models')
def get_available_models():
    """Get available AI models"""
    models = [
        {'id': 'gpt-4', 'name': 'GPT-4', 'provider': 'OpenAI', 'description': 'Most capable model'},
        {'id': 'gpt-3.5-turbo', 'name': 'GPT-3.5 Turbo', 'provider': 'OpenAI', 'description': 'Fast and efficient'},
        {'id': 'claude-3-opus', 'name': 'Claude 3 Opus', 'provider': 'Anthropic', 'description': 'Advanced reasoning'},
        {'id': 'claude-3-sonnet', 'name': 'Claude 3 Sonnet', 'provider': 'Anthropic', 'description': 'Balanced performance'},
    ]
    return jsonify(models)

@socketio.on('connect')
def on_connect():
    """Handle client connection"""
    if 'user_id' not in session:
        return False
    
    user_id = session['user_id']
    join_room(user_id)
    emit('connected', {'message': 'Connected to AI platform'})

@socketio.on('disconnect')
def on_disconnect():
    """Handle client disconnection"""
    if 'user_id' in session:
        leave_room(session['user_id'])

@socketio.on('send_message')
def handle_message(data):
    """Handle incoming chat message"""
    if 'user_id' not in session:
        return
    
    user_id = session['user_id']
    session_id = data.get('session_id')
    message_content = data.get('message')
    model = data.get('model', 'gpt-4')
    temperature = data.get('temperature', 0.7)
    max_tokens = data.get('max_tokens', 2048)
    
    if not session_id or session_id not in chat_sessions:
        emit('error', {'message': 'Invalid session'})
        return
    
    chat_session = chat_sessions[session_id]
    if chat_session.user_id != user_id:
        emit('error', {'message': 'Unauthorized'})
        return
    
    # Add user message
    user_message = chat_session.add_message('user', message_content)
    emit('message_added', user_message)
    
    # Process AI response in background
    def process_ai_response():
        try:
            # Prepare conversation history
            messages = []
            for msg in chat_session.messages:
                if msg['role'] in ['user', 'assistant']:
                    messages.append({
                        'role': msg['role'],
                        'content': msg['content']
                    })
            
            # Get AI response using OpenManus
            response = llm_wrapper.generate_response(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Add AI response
            ai_message = chat_session.add_message('assistant', response, {
                'model': model,
                'temperature': temperature,
                'max_tokens': max_tokens
            })
            
            socketio.emit('message_added', ai_message, room=user_id)
            
        except Exception as e:
            error_message = f"Error generating response: {str(e)}"
            error_msg = chat_session.add_message('system', error_message, {'error': True})
            socketio.emit('message_added', error_msg, room=user_id)
    
    # Run in background thread
    threading.Thread(target=process_ai_response).start()

if __name__ == '__main__':
    # Create default admin user
    if 'admin' not in users:
        users['admin'] = {
            'id': 'admin-user-id',
            'username': 'admin',
            'email': 'admin@example.com',
            'password': generate_password_hash('admin123'),
            'created_at': datetime.now().isoformat()
        }
        user_preferences['admin-user-id'] = {
            'theme': 'dark',
            'default_model': 'gpt-4',
            'temperature': 0.7,
            'max_tokens': 2048,
            'auto_save': True
        }
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
