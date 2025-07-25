"""
WebSocket Manager for Real-time Communication
Handles real-time chat updates, progress tracking, and tool execution status
"""
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_login import current_user
import uuid
import threading
import queue

from app.models import db, ChatSession, ChatMessage, Task, User
from app.logger import logger


class WebSocketManager:
    """Manages WebSocket connections and real-time updates"""
    
    def __init__(self, socketio: SocketIO):
        self.socketio = socketio
        self.active_sessions: Dict[str, Dict] = {}
        self.user_rooms: Dict[str, str] = {}  # user_id -> room_id
        self.progress_queues: Dict[str, queue.Queue] = {}  # task_id -> queue
        self._setup_handlers()
        
    def _setup_handlers(self):
        """Setup WebSocket event handlers"""
        
        @self.socketio.on('connect')
        def handle_connect():
            if current_user.is_authenticated:
                user_id = current_user.id
                room_id = f"user_{user_id}"
                join_room(room_id)
                self.user_rooms[user_id] = room_id
                
                logger.info(f"User {current_user.username} connected to room {room_id}")
                
                # Send connection confirmation
                emit('connection_status', {
                    'status': 'connected',
                    'user_id': user_id,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                # Send any pending updates
                self._send_pending_updates(user_id)
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            if current_user.is_authenticated:
                user_id = current_user.id
                if user_id in self.user_rooms:
                    leave_room(self.user_rooms[user_id])
                    del self.user_rooms[user_id]
                logger.info(f"User {current_user.username} disconnected")
        
        @self.socketio.on('join_chat_session')
        def handle_join_session(data):
            if current_user.is_authenticated:
                session_id = data.get('session_id')
                if session_id:
                    room_id = f"chat_{session_id}"
                    join_room(room_id)
                    logger.info(f"User {current_user.username} joined chat session {session_id}")
        
        @self.socketio.on('start_chat')
        def handle_start_chat(data):
            if current_user.is_authenticated:
                message = data.get('message', '')
                session_id = data.get('session_id')
                
                # Create or get chat session
                if not session_id:
                    session = ChatSession(
                        user_id=current_user.id,
                        title=message[:50] + "..." if len(message) > 50 else message
                    )
                    db.session.add(session)
                    db.session.commit()
                    session_id = session.id
                
                # Start processing
                self._handle_chat_message(session_id, message)
        
        @self.socketio.on('request_task_status')
        def handle_task_status_request(data):
            if current_user.is_authenticated:
                task_id = data.get('task_id')
                if task_id:
                    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first()
                    if task:
                        emit('task_status_update', task.to_dict())
    
    def _handle_chat_message(self, session_id: str, message: str):
        """Handle incoming chat message and start processing"""
        try:
            # Save user message
            user_message = ChatMessage(
                session_id=session_id,
                role='user',
                content=message
            )
            db.session.add(user_message)
            db.session.commit()
            
            # Create task for processing
            task = Task(
                user_id=current_user.id,
                session_id=session_id,
                task_type='chat',
                status='pending',
                current_step='Initializing...'
            )
            db.session.add(task)
            db.session.commit()
            
            # Send initial response
            self.send_message_update(session_id, {
                'type': 'user_message',
                'content': message,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Start background processing
            self._start_chat_processing(task.id, session_id, message)
            
        except Exception as e:
            logger.error(f"Error handling chat message: {e}")
            self.send_error(session_id, f"Error processing message: {str(e)}")
    
    def _start_chat_processing(self, task_id: str, session_id: str, message: str):
        """Start background chat processing"""
        from app.tasks import process_chat_message
        
        # Create progress queue for this task
        progress_queue = queue.Queue()
        self.progress_queues[task_id] = progress_queue
        
        # Start background task
        task_thread = threading.Thread(
            target=self._run_chat_task,
            args=(task_id, session_id, message, progress_queue)
        )
        task_thread.daemon = True
        task_thread.start()
        
        # Start progress monitoring
        monitor_thread = threading.Thread(
            target=self._monitor_task_progress,
            args=(task_id, session_id)
        )
        monitor_thread.daemon = True
        monitor_thread.start()
    
    def _run_chat_task(self, task_id: str, session_id: str, message: str, progress_queue: queue.Queue):
        """Run chat processing task"""
        try:
            from app.agent.manus import Manus
            
            # Update task status
            task = Task.query.get(task_id)
            if task:
                task.status = 'running'
                task.started_at = datetime.utcnow()
                task.current_step = 'Starting AI processing...'
                db.session.commit()
            
            # Create enhanced agent with progress callback
            agent = Manus()
            
            # Process message with progress tracking
            result = agent.run_with_progress(message, progress_queue)
            
            # Save assistant response
            assistant_message = ChatMessage(
                session_id=session_id,
                role='assistant',
                content=result.get('content', ''),
                metadata=result.get('metadata', {})
            )
            db.session.add(assistant_message)
            
            # Update task completion
            if task:
                task.status = 'completed'
                task.progress = 100
                task.completed_at = datetime.utcnow()
                task.current_step = 'Completed'
                task.result_data = result
                db.session.commit()
            
            # Send final response
            self.send_message_update(session_id, {
                'type': 'assistant_message',
                'content': result.get('content', ''),
                'metadata': result.get('metadata', {}),
                'timestamp': datetime.utcnow().isoformat(),
                'task_id': task_id
            })
            
        except Exception as e:
            logger.error(f"Error in chat task {task_id}: {e}")
            
            # Update task with error
            task = Task.query.get(task_id)
            if task:
                task.status = 'failed'
                task.error_message = str(e)
                task.completed_at = datetime.utcnow()
                db.session.commit()
            
            self.send_error(session_id, f"Processing failed: {str(e)}")
        
        finally:
            # Clean up progress queue
            if task_id in self.progress_queues:
                del self.progress_queues[task_id]
    
    def _monitor_task_progress(self, task_id: str, session_id: str):
        """Monitor task progress and send updates"""
        progress_queue = self.progress_queues.get(task_id)
        if not progress_queue:
            return
        
        try:
            while True:
                try:
                    # Get progress update with timeout
                    update = progress_queue.get(timeout=1.0)
                    
                    if update is None:  # Sentinel value to stop monitoring
                        break
                    
                    # Update database
                    task = Task.query.get(task_id)
                    if task:
                        task.progress = update.get('progress', task.progress)
                        task.current_step = update.get('step', task.current_step)
                        db.session.commit()
                    
                    # Send progress update via WebSocket
                    self.send_progress_update(session_id, {
                        'task_id': task_id,
                        'progress': update.get('progress', 0),
                        'step': update.get('step', ''),
                        'details': update.get('details', {}),
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    
                except queue.Empty:
                    # Check if task is still running
                    task = Task.query.get(task_id)
                    if task and task.status in ['completed', 'failed']:
                        break
                    continue
                    
        except Exception as e:
            logger.error(f"Error monitoring task progress {task_id}: {e}")
    
    def send_message_update(self, session_id: str, data: Dict[str, Any]):
        """Send message update to chat session"""
        room_id = f"chat_{session_id}"
        self.socketio.emit('message_update', data, room=room_id)
    
    def send_progress_update(self, session_id: str, data: Dict[str, Any]):
        """Send progress update to chat session"""
        room_id = f"chat_{session_id}"
        self.socketio.emit('progress_update', data, room=room_id)
    
    def send_tool_update(self, session_id: str, tool_name: str, status: str, details: Dict[str, Any] = None):
        """Send tool execution update"""
        room_id = f"chat_{session_id}"
        self.socketio.emit('tool_update', {
            'tool_name': tool_name,
            'status': status,
            'details': details or {},
            'timestamp': datetime.utcnow().isoformat()
        }, room=room_id)
    
    def send_error(self, session_id: str, error_message: str):
        """Send error message to chat session"""
        room_id = f"chat_{session_id}"
        self.socketio.emit('error', {
            'message': error_message,
            'timestamp': datetime.utcnow().isoformat()
        }, room=room_id)
    
    def send_user_notification(self, user_id: str, notification: Dict[str, Any]):
        """Send notification to specific user"""
        room_id = self.user_rooms.get(user_id)
        if room_id:
            self.socketio.emit('notification', notification, room=room_id)
    
    def _send_pending_updates(self, user_id: str):
        """Send any pending updates when user connects"""
        # Get pending tasks
        pending_tasks = Task.query.filter_by(
            user_id=user_id,
            status='running'
        ).all()
        
        room_id = self.user_rooms.get(user_id)
        if room_id:
            for task in pending_tasks:
                self.socketio.emit('task_status_update', task.to_dict(), room=room_id)
    
    def get_active_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get active chat sessions for user"""
        sessions = ChatSession.query.filter_by(
            user_id=user_id,
            is_active=True
        ).order_by(ChatSession.updated_at.desc()).all()
        
        return [session.to_dict() for session in sessions]


# Global WebSocket manager instance
ws_manager: Optional[WebSocketManager] = None


def init_websocket_manager(socketio: SocketIO) -> WebSocketManager:
    """Initialize the global WebSocket manager"""
    global ws_manager
    ws_manager = WebSocketManager(socketio)
    return ws_manager


def get_websocket_manager() -> Optional[WebSocketManager]:
    """Get the global WebSocket manager instance"""
    return ws_manager