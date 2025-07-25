"""
Cursor-like Agents Platform - Advanced AI Agent Management System
Features: Agent creation, collaboration, real-time execution, team management
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
import queue
from werkzeug.security import generate_password_hash, check_password_hash
from typing import Dict, List, Optional
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cursor-agents-platform-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# In-memory storage (use database in production)
users = {}
teams = {}
agents = {}
agent_sessions = {}
agent_executions = {}
user_preferences = {}

class Agent:
    def __init__(self, agent_id: str, name: str, description: str, creator_id: str, 
                 system_prompt: str = "", capabilities: List[str] = None, model: str = "gpt-4"):
        self.id = agent_id
        self.name = name
        self.description = description
        self.creator_id = creator_id
        self.system_prompt = system_prompt
        self.capabilities = capabilities or []
        self.model = model
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.is_active = True
        self.execution_count = 0
        self.team_id = None
        self.tags = []
        self.version = "1.0.0"
        
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'creator_id': self.creator_id,
            'system_prompt': self.system_prompt,
            'capabilities': self.capabilities,
            'model': self.model,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'is_active': self.is_active,
            'execution_count': self.execution_count,
            'team_id': self.team_id,
            'tags': self.tags,
            'version': self.version
        }

class AgentExecution:
    def __init__(self, execution_id: str, agent_id: str, user_id: str, task: str):
        self.id = execution_id
        self.agent_id = agent_id
        self.user_id = user_id
        self.task = task
        self.status = "pending"  # pending, running, completed, failed
        self.result = None
        self.error = None
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None
        self.logs = []
        
    def add_log(self, message: str, level: str = "info"):
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message
        }
        self.logs.append(log_entry)
        return log_entry
        
    def to_dict(self):
        return {
            'id': self.id,
            'agent_id': self.agent_id,
            'user_id': self.user_id,
            'task': self.task,
            'status': self.status,
            'result': self.result,
            'error': self.error,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'logs': self.logs
        }

class Team:
    def __init__(self, team_id: str, name: str, creator_id: str, description: str = ""):
        self.id = team_id
        self.name = name
        self.creator_id = creator_id
        self.description = description
        self.members = [creator_id]
        self.agents = []
        self.created_at = datetime.now()
        self.settings = {
            'public': False,
            'allow_agent_sharing': True,
            'require_approval': False
        }
        
    def add_member(self, user_id: str):
        if user_id not in self.members:
            self.members.append(user_id)
            
    def remove_member(self, user_id: str):
        if user_id in self.members and user_id != self.creator_id:
            self.members.remove(user_id)
            
    def add_agent(self, agent_id: str):
        if agent_id not in self.agents:
            self.agents.append(agent_id)
            
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'creator_id': self.creator_id,
            'description': self.description,
            'members': self.members,
            'agents': self.agents,
            'created_at': self.created_at.isoformat(),
            'settings': self.settings
        }

@app.route('/')
def index():
    """Main dashboard page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

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
            'created_at': datetime.now().isoformat(),
            'avatar': f"https://api.dicebear.com/7.x/initials/svg?seed={username}"
        }
        
        # Initialize user preferences
        user_preferences[user_id] = {
            'theme': 'dark',
            'default_model': 'gpt-4',
            'notifications': True,
            'auto_save': True,
            'collaboration_mode': 'team'
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

@app.route('/agents')
def agents_page():
    """Agents management page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('agents.html')

@app.route('/agent/<agent_id>')
def agent_detail(agent_id):
    """Individual agent detail page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('agent_detail.html', agent_id=agent_id)

@app.route('/teams')
def teams_page():
    """Teams management page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('teams.html')

@app.route('/executions')
def executions_page():
    """Agent executions monitoring page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('executions.html')

# API Routes

@app.route('/api/agents', methods=['GET'])
def get_agents():
    """Get user's agents"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    user_agents = []
    
    for agent in agents.values():
        if agent.creator_id == user_id or user_id in get_user_team_members(user_id):
            user_agents.append(agent.to_dict())
    
    return jsonify(user_agents)

@app.route('/api/agents', methods=['POST'])
def create_agent():
    """Create new agent"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    agent_id = str(uuid.uuid4())
    user_id = session['user_id']
    
    agent = Agent(
        agent_id=agent_id,
        name=data.get('name', 'Untitled Agent'),
        description=data.get('description', ''),
        creator_id=user_id,
        system_prompt=data.get('system_prompt', ''),
        capabilities=data.get('capabilities', []),
        model=data.get('model', 'gpt-4')
    )
    
    if 'team_id' in data:
        agent.team_id = data['team_id']
        if data['team_id'] in teams:
            teams[data['team_id']].add_agent(agent_id)
    
    agents[agent_id] = agent
    
    return jsonify({'success': True, 'agent': agent.to_dict()})

@app.route('/api/agents/<agent_id>', methods=['GET'])
def get_agent(agent_id):
    """Get specific agent"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if agent_id not in agents:
        return jsonify({'error': 'Agent not found'}), 404
    
    agent = agents[agent_id]
    user_id = session['user_id']
    
    # Check permissions
    if agent.creator_id != user_id and not is_team_member(user_id, agent.team_id):
        return jsonify({'error': 'Unauthorized'}), 403
    
    return jsonify(agent.to_dict())

@app.route('/api/agents/<agent_id>', methods=['PUT'])
def update_agent(agent_id):
    """Update agent"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if agent_id not in agents:
        return jsonify({'error': 'Agent not found'}), 404
    
    agent = agents[agent_id]
    user_id = session['user_id']
    
    # Check permissions
    if agent.creator_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.json
    
    if 'name' in data:
        agent.name = data['name']
    if 'description' in data:
        agent.description = data['description']
    if 'system_prompt' in data:
        agent.system_prompt = data['system_prompt']
    if 'capabilities' in data:
        agent.capabilities = data['capabilities']
    if 'model' in data:
        agent.model = data['model']
    if 'tags' in data:
        agent.tags = data['tags']
    
    agent.updated_at = datetime.now()
    
    return jsonify({'success': True, 'agent': agent.to_dict()})

@app.route('/api/agents/<agent_id>', methods=['DELETE'])
def delete_agent(agent_id):
    """Delete agent"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if agent_id not in agents:
        return jsonify({'error': 'Agent not found'}), 404
    
    agent = agents[agent_id]
    user_id = session['user_id']
    
    # Check permissions
    if agent.creator_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    del agents[agent_id]
    
    return jsonify({'success': True})

@app.route('/api/agents/<agent_id>/execute', methods=['POST'])
def execute_agent(agent_id):
    """Execute agent with task"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if agent_id not in agents:
        return jsonify({'error': 'Agent not found'}), 404
    
    agent = agents[agent_id]
    user_id = session['user_id']
    
    # Check permissions
    if agent.creator_id != user_id and not is_team_member(user_id, agent.team_id):
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.json
    task = data.get('task', '')
    
    if not task:
        return jsonify({'error': 'Task is required'}), 400
    
    execution_id = str(uuid.uuid4())
    execution = AgentExecution(execution_id, agent_id, user_id, task)
    agent_executions[execution_id] = execution
    
    # Start execution in background
    threading.Thread(target=run_agent_execution, args=(execution_id,)).start()
    
    return jsonify({'success': True, 'execution_id': execution_id})

@app.route('/api/executions')
def get_executions():
    """Get user's agent executions"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    user_executions = []
    
    for execution in agent_executions.values():
        if execution.user_id == user_id:
            exec_dict = execution.to_dict()
            if execution.agent_id in agents:
                exec_dict['agent_name'] = agents[execution.agent_id].name
            user_executions.append(exec_dict)
    
    # Sort by creation time, newest first
    user_executions.sort(key=lambda x: x['created_at'], reverse=True)
    
    return jsonify(user_executions)

@app.route('/api/executions/<execution_id>')
def get_execution(execution_id):
    """Get specific execution"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if execution_id not in agent_executions:
        return jsonify({'error': 'Execution not found'}), 404
    
    execution = agent_executions[execution_id]
    user_id = session['user_id']
    
    # Check permissions
    if execution.user_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    return jsonify(execution.to_dict())

@app.route('/api/teams', methods=['GET'])
def get_teams():
    """Get user's teams"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    user_teams = []
    
    for team in teams.values():
        if user_id in team.members:
            user_teams.append(team.to_dict())
    
    return jsonify(user_teams)

@app.route('/api/teams', methods=['POST'])
def create_team():
    """Create new team"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    team_id = str(uuid.uuid4())
    user_id = session['user_id']
    
    team = Team(
        team_id=team_id,
        name=data.get('name', 'Untitled Team'),
        creator_id=user_id,
        description=data.get('description', '')
    )
    
    teams[team_id] = team
    
    return jsonify({'success': True, 'team': team.to_dict()})

def get_user_team_members(user_id: str) -> List[str]:
    """Get all team members for teams the user belongs to"""
    members = set()
    for team in teams.values():
        if user_id in team.members:
            members.update(team.members)
    return list(members)

def is_team_member(user_id: str, team_id: str) -> bool:
    """Check if user is member of specific team"""
    if not team_id or team_id not in teams:
        return False
    return user_id in teams[team_id].members

def run_agent_execution(execution_id: str):
    """Run agent execution in background"""
    if execution_id not in agent_executions:
        return
    
    execution = agent_executions[execution_id]
    agent = agents.get(execution.agent_id)
    
    if not agent:
        execution.status = "failed"
        execution.error = "Agent not found"
        return
    
    try:
        execution.status = "running"
        execution.started_at = datetime.now()
        execution.add_log(f"Starting execution for agent '{agent.name}'")
        
        # Simulate agent execution (replace with actual AI processing)
        time.sleep(2)  # Simulate processing time
        
        # Mock response generation
        mock_responses = [
            f"Task completed: {execution.task}",
            f"Analyzed task '{execution.task}' using {agent.model}",
            f"Generated solution based on system prompt: {agent.system_prompt[:50]}...",
            "Task execution successful with optimal results"
        ]
        
        execution.result = mock_responses[hash(execution.task) % len(mock_responses)]
        execution.status = "completed"
        execution.completed_at = datetime.now()
        execution.add_log("Execution completed successfully")
        
        agent.execution_count += 1
        
        # Notify user via websocket
        socketio.emit('execution_completed', {
            'execution_id': execution_id,
            'status': execution.status,
            'result': execution.result
        }, room=execution.user_id)
        
    except Exception as e:
        execution.status = "failed"
        execution.error = str(e)
        execution.add_log(f"Execution failed: {str(e)}", "error")
        
        socketio.emit('execution_failed', {
            'execution_id': execution_id,
            'error': execution.error
        }, room=execution.user_id)

@socketio.on('connect')
def on_connect():
    """Handle client connection"""
    if 'user_id' not in session:
        return False
    
    user_id = session['user_id']
    join_room(user_id)
    emit('connected', {'message': 'Connected to Cursor Agents Platform'})

@socketio.on('disconnect')
def on_disconnect():
    """Handle client disconnection"""
    if 'user_id' in session:
        leave_room(session['user_id'])

def setup_demo_data():
    """Setup demo data for testing"""
    # Create demo users
    demo_users = [
        {'username': 'admin', 'email': 'admin@cursor.ai', 'password': 'admin123'},
        {'username': 'alice', 'email': 'alice@cursor.ai', 'password': 'alice123'},
        {'username': 'bob', 'email': 'bob@cursor.ai', 'password': 'bob123'}
    ]
    
    for user_data in demo_users:
        if user_data['username'] not in users:
            user_id = str(uuid.uuid4())
            users[user_data['username']] = {
                'id': user_id,
                'username': user_data['username'],
                'email': user_data['email'],
                'password': generate_password_hash(user_data['password']),
                'created_at': datetime.now().isoformat(),
                'avatar': f"https://api.dicebear.com/7.x/initials/svg?seed={user_data['username']}"
            }
            
            user_preferences[user_id] = {
                'theme': 'dark',
                'default_model': 'gpt-4',
                'notifications': True,
                'auto_save': True,
                'collaboration_mode': 'team'
            }
    
    # Create demo team
    admin_id = users['admin']['id']
    team_id = str(uuid.uuid4())
    demo_team = Team(team_id, "Cursor AI Team", admin_id, "Demo team for Cursor Agents Platform")
    demo_team.add_member(users['alice']['id'])
    demo_team.add_member(users['bob']['id'])
    teams[team_id] = demo_team
    
    # Create demo agents
    demo_agents_data = [
        {
            'name': 'Code Assistant',
            'description': 'Helps with code generation, debugging, and optimization',
            'system_prompt': 'You are a senior software engineer assistant. Help users write clean, efficient code.',
            'capabilities': ['code_generation', 'debugging', 'optimization', 'code_review'],
            'model': 'gpt-4'
        },
        {
            'name': 'Data Analyst',
            'description': 'Analyzes data and creates visualizations',
            'system_prompt': 'You are a data analyst. Help users analyze data and create meaningful insights.',
            'capabilities': ['data_analysis', 'visualization', 'statistics', 'reporting'],
            'model': 'gpt-4'
        },
        {
            'name': 'UI Designer',
            'description': 'Creates beautiful user interfaces and UX designs',
            'system_prompt': 'You are a UI/UX designer. Help users create beautiful and functional interfaces.',
            'capabilities': ['ui_design', 'ux_research', 'prototyping', 'design_systems'],
            'model': 'gpt-4'
        }
    ]
    
    for agent_data in demo_agents_data:
        agent_id = str(uuid.uuid4())
        agent = Agent(
            agent_id=agent_id,
            name=agent_data['name'],
            description=agent_data['description'],
            creator_id=admin_id,
            system_prompt=agent_data['system_prompt'],
            capabilities=agent_data['capabilities'],
            model=agent_data['model']
        )
        agent.team_id = team_id
        agents[agent_id] = agent
        demo_team.add_agent(agent_id)

if __name__ == '__main__':
    # Create default demo users and agents
    setup_demo_data()
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)