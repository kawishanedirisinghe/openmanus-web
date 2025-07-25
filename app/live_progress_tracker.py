"""
Advanced Live Progress Tracking System
Provides real-time step-by-step progress tracking for AI operations
"""

import time
import json
import asyncio
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import uuid
from collections import deque

from app.websocket_manager import get_websocket_manager
from app.logger import logger


class ProgressStatus(Enum):
    """Progress status types"""
    PENDING = "pending"
    STARTING = "starting"
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    PROCESSING = "processing"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    COMPLETING = "completing"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class LogLevel(Enum):
    """Log level types"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ProgressStep:
    """Individual progress step"""
    id: str
    title: str
    status: ProgressStatus
    progress: int  # 0-100
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)
    sub_steps: List['ProgressStep'] = field(default_factory=list)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'status': self.status.value,
            'progress': self.progress,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration': self.duration,
            'details': self.details,
            'sub_steps': [sub.to_dict() for sub in self.sub_steps],
            'logs': self.logs,
            'metadata': self.metadata
        }


@dataclass
class ThinkingProcess:
    """AI thinking process tracking"""
    thought_id: str
    content: str
    reasoning_type: str  # 'analysis', 'planning', 'decision', 'reflection'
    confidence: float  # 0.0-1.0
    timestamp: datetime
    related_steps: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'thought_id': self.thought_id,
            'content': self.content,
            'reasoning_type': self.reasoning_type,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat(),
            'related_steps': self.related_steps
        }


class LiveProgressTracker:
    """Advanced live progress tracking with real-time updates"""
    
    def __init__(self, session_id: str, user_id: str, task_name: str = "AI Task"):
        self.session_id = session_id
        self.user_id = user_id
        self.task_name = task_name
        self.task_id = str(uuid.uuid4())
        
        # Progress tracking
        self.overall_progress = 0
        self.current_step_index = 0
        self.steps: List[ProgressStep] = []
        self.current_step: Optional[ProgressStep] = None
        
        # Thinking process
        self.thinking_log: List[ThinkingProcess] = []
        self.current_reasoning = None
        
        # Tool usage tracking
        self.tool_calls: List[Dict[str, Any]] = []
        self.active_tools: Dict[str, Dict[str, Any]] = {}
        
        # Real-time logs
        self.live_logs: deque = deque(maxlen=1000)
        
        # Status and timing
        self.start_time = datetime.utcnow()
        self.last_update = datetime.utcnow()
        self.is_active = True
        self.total_steps = 0
        
        # WebSocket manager for real-time updates
        self.ws_manager = get_websocket_manager()
        
        # Callbacks
        self.update_callbacks: List[Callable] = []
        
        # Debug mode
        self.debug_mode = True
        
        logger.info(f"Created progress tracker for session {session_id}, task: {task_name}")
    
    def set_total_steps(self, total: int):
        """Set expected total number of steps"""
        self.total_steps = total
        self._send_update('total_steps_set', {'total_steps': total})
    
    def start_step(self, title: str, details: Dict[str, Any] = None) -> str:
        """Start a new progress step"""
        step_id = str(uuid.uuid4())
        
        # Complete current step if exists
        if self.current_step and self.current_step.status not in [ProgressStatus.COMPLETED, ProgressStatus.ERROR]:
            self.complete_current_step()
        
        # Create new step
        step = ProgressStep(
            id=step_id,
            title=title,
            status=ProgressStatus.STARTING,
            progress=0,
            start_time=datetime.utcnow(),
            details=details or {},
            metadata={'step_index': len(self.steps)}
        )
        
        self.steps.append(step)
        self.current_step = step
        self.current_step_index = len(self.steps) - 1
        
        # Update overall progress
        if self.total_steps > 0:
            self.overall_progress = min(int((len(self.steps) / self.total_steps) * 100), 100)
        
        self._log(LogLevel.INFO, f"Started step: {title}", {'step_id': step_id})
        self._send_step_update(step, 'step_started')
        
        return step_id
    
    def update_step_progress(self, progress: int, details: Dict[str, Any] = None):
        """Update current step progress"""
        if not self.current_step:
            return
        
        self.current_step.progress = max(0, min(100, progress))
        if details:
            self.current_step.details.update(details)
        
        self.current_step.status = ProgressStatus.PROCESSING
        self._send_step_update(self.current_step, 'step_progress')
    
    def update_step_status(self, status: ProgressStatus, details: Dict[str, Any] = None):
        """Update current step status"""
        if not self.current_step:
            return
        
        self.current_step.status = status
        if details:
            self.current_step.details.update(details)
        
        self._send_step_update(self.current_step, 'step_status')
    
    def complete_current_step(self, final_details: Dict[str, Any] = None):
        """Complete the current step"""
        if not self.current_step:
            return
        
        self.current_step.end_time = datetime.utcnow()
        self.current_step.duration = (
            self.current_step.end_time - self.current_step.start_time
        ).total_seconds()
        self.current_step.progress = 100
        self.current_step.status = ProgressStatus.COMPLETED
        
        if final_details:
            self.current_step.details.update(final_details)
        
        self._log(LogLevel.INFO, f"Completed step: {self.current_step.title}", {
            'step_id': self.current_step.id,
            'duration': self.current_step.duration
        })
        
        self._send_step_update(self.current_step, 'step_completed')
    
    def add_sub_step(self, title: str, progress: int = 0, details: Dict[str, Any] = None) -> str:
        """Add a sub-step to current step"""
        if not self.current_step:
            return None
        
        sub_step_id = str(uuid.uuid4())
        sub_step = ProgressStep(
            id=sub_step_id,
            title=title,
            status=ProgressStatus.PROCESSING,
            progress=progress,
            start_time=datetime.utcnow(),
            details=details or {}
        )
        
        self.current_step.sub_steps.append(sub_step)
        self._send_step_update(self.current_step, 'sub_step_added')
        
        return sub_step_id
    
    def start_thinking(self, thought: str, reasoning_type: str = 'analysis', 
                      confidence: float = 0.8) -> str:
        """Start AI thinking process"""
        thought_id = str(uuid.uuid4())
        
        thinking = ThinkingProcess(
            thought_id=thought_id,
            content=thought,
            reasoning_type=reasoning_type,
            confidence=confidence,
            timestamp=datetime.utcnow(),
            related_steps=[self.current_step.id] if self.current_step else []
        )
        
        self.thinking_log.append(thinking)
        self.current_reasoning = thinking
        
        self._log(LogLevel.DEBUG, f"AI Thinking: {thought[:100]}...", {
            'thought_id': thought_id,
            'reasoning_type': reasoning_type,
            'confidence': confidence
        })
        
        # Send thinking update
        self._send_update('thinking_started', {
            'thinking': thinking.to_dict(),
            'is_reasoning': True
        })
        
        return thought_id
    
    def update_thinking(self, additional_thought: str):
        """Update current thinking process"""
        if self.current_reasoning:
            self.current_reasoning.content += f" {additional_thought}"
            
            self._send_update('thinking_updated', {
                'thinking': self.current_reasoning.to_dict()
            })
    
    def complete_thinking(self, final_thought: str = None):
        """Complete current thinking process"""
        if self.current_reasoning:
            if final_thought:
                self.current_reasoning.content += f" {final_thought}"
            
            self._send_update('thinking_completed', {
                'thinking': self.current_reasoning.to_dict()
            })
            
            self.current_reasoning = None
    
    def start_tool_call(self, tool_name: str, parameters: Dict[str, Any] = None) -> str:
        """Start tool execution tracking"""
        call_id = str(uuid.uuid4())
        
        tool_call = {
            'call_id': call_id,
            'tool_name': tool_name,
            'parameters': parameters or {},
            'status': 'starting',
            'start_time': datetime.utcnow().isoformat(),
            'end_time': None,
            'result': None,
            'error': None,
            'duration': None
        }
        
        self.tool_calls.append(tool_call)
        self.active_tools[call_id] = tool_call
        
        self._log(LogLevel.INFO, f"Started tool call: {tool_name}", {
            'call_id': call_id,
            'tool_name': tool_name,
            'parameters': parameters
        })
        
        # Send tool update
        if self.ws_manager:
            self.ws_manager.send_tool_update(
                self.session_id, 
                tool_name, 
                'starting', 
                {'call_id': call_id, 'parameters': parameters}
            )
        
        return call_id
    
    def update_tool_progress(self, call_id: str, progress: int, details: Dict[str, Any] = None):
        """Update tool execution progress"""
        if call_id in self.active_tools:
            tool_call = self.active_tools[call_id]
            tool_call['status'] = 'running'
            tool_call['progress'] = progress
            if details:
                tool_call['details'] = details
            
            if self.ws_manager:
                self.ws_manager.send_tool_update(
                    self.session_id,
                    tool_call['tool_name'],
                    'running',
                    {'call_id': call_id, 'progress': progress, 'details': details}
                )
    
    def complete_tool_call(self, call_id: str, result: Any = None, error: str = None):
        """Complete tool execution"""
        if call_id in self.active_tools:
            tool_call = self.active_tools[call_id]
            tool_call['end_time'] = datetime.utcnow().isoformat()
            tool_call['status'] = 'failed' if error else 'completed'
            tool_call['result'] = result
            tool_call['error'] = error
            
            # Calculate duration
            start_time = datetime.fromisoformat(tool_call['start_time'])
            end_time = datetime.fromisoformat(tool_call['end_time'])
            tool_call['duration'] = (end_time - start_time).total_seconds()
            
            self._log(
                LogLevel.ERROR if error else LogLevel.INFO,
                f"Tool call {'failed' if error else 'completed'}: {tool_call['tool_name']}",
                {
                    'call_id': call_id,
                    'duration': tool_call['duration'],
                    'result': result,
                    'error': error
                }
            )
            
            if self.ws_manager:
                self.ws_manager.send_tool_update(
                    self.session_id,
                    tool_call['tool_name'],
                    'failed' if error else 'completed',
                    {
                        'call_id': call_id,
                        'result': result,
                        'error': error,
                        'duration': tool_call['duration']
                    }
                )
            
            # Remove from active tools
            del self.active_tools[call_id]
    
    def log_debug_info(self, message: str, data: Dict[str, Any] = None):
        """Log debug information"""
        self._log(LogLevel.DEBUG, message, data)
    
    def log_warning(self, message: str, data: Dict[str, Any] = None):
        """Log warning"""
        self._log(LogLevel.WARNING, message, data)
    
    def log_error(self, message: str, error: Exception = None, data: Dict[str, Any] = None):
        """Log error"""
        log_data = data or {}
        if error:
            log_data['error'] = str(error)
            log_data['error_type'] = type(error).__name__
        
        self._log(LogLevel.ERROR, message, log_data)
    
    def _log(self, level: LogLevel, message: str, data: Dict[str, Any] = None):
        """Internal logging method"""
        log_entry = {
            'id': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat(),
            'level': level.value,
            'message': message,
            'data': data or {},
            'step_id': self.current_step.id if self.current_step else None
        }
        
        self.live_logs.append(log_entry)
        
        # Add to current step logs
        if self.current_step:
            self.current_step.logs.append(log_entry)
        
        # Send real-time log update
        if self.debug_mode:
            self._send_update('live_log', log_entry)
        
        # Also log to standard logger
        if level == LogLevel.DEBUG:
            logger.debug(f"[{self.task_name}] {message}", extra=data)
        elif level == LogLevel.INFO:
            logger.info(f"[{self.task_name}] {message}", extra=data)
        elif level == LogLevel.WARNING:
            logger.warning(f"[{self.task_name}] {message}", extra=data)
        elif level == LogLevel.ERROR:
            logger.error(f"[{self.task_name}] {message}", extra=data)
        elif level == LogLevel.CRITICAL:
            logger.critical(f"[{self.task_name}] {message}", extra=data)
    
    def _send_step_update(self, step: ProgressStep, update_type: str):
        """Send step update via WebSocket"""
        self._send_update(update_type, {
            'step': step.to_dict(),
            'overall_progress': self.overall_progress,
            'current_step_index': self.current_step_index,
            'total_steps': self.total_steps
        })
    
    def _send_update(self, update_type: str, data: Dict[str, Any]):
        """Send update via WebSocket"""
        update_data = {
            'task_id': self.task_id,
            'session_id': self.session_id,
            'update_type': update_type,
            'timestamp': datetime.utcnow().isoformat(),
            'data': data
        }
        
        if self.ws_manager:
            self.ws_manager.send_progress_update(self.session_id, update_data)
        
        # Call registered callbacks
        for callback in self.update_callbacks:
            try:
                callback(update_data)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")
        
        self.last_update = datetime.utcnow()
    
    def complete_task(self, final_result: Dict[str, Any] = None):
        """Complete the entire task"""
        # Complete current step if exists
        if self.current_step and self.current_step.status != ProgressStatus.COMPLETED:
            self.complete_current_step()
        
        self.is_active = False
        self.overall_progress = 100
        
        end_time = datetime.utcnow()
        total_duration = (end_time - self.start_time).total_seconds()
        
        self._log(LogLevel.INFO, f"Task completed: {self.task_name}", {
            'total_duration': total_duration,
            'total_steps': len(self.steps),
            'thinking_entries': len(self.thinking_log),
            'tool_calls': len(self.tool_calls)
        })
        
        # Send completion update
        self._send_update('task_completed', {
            'task_name': self.task_name,
            'total_duration': total_duration,
            'final_result': final_result,
            'summary': self.get_task_summary()
        })
    
    def fail_task(self, error_message: str, error_details: Dict[str, Any] = None):
        """Mark task as failed"""
        if self.current_step:
            self.current_step.status = ProgressStatus.ERROR
            self.current_step.details['error'] = error_message
        
        self.is_active = False
        
        self._log(LogLevel.ERROR, f"Task failed: {error_message}", error_details)
        
        self._send_update('task_failed', {
            'error_message': error_message,
            'error_details': error_details or {},
            'summary': self.get_task_summary()
        })
    
    def get_task_summary(self) -> Dict[str, Any]:
        """Get comprehensive task summary"""
        end_time = datetime.utcnow()
        total_duration = (end_time - self.start_time).total_seconds()
        
        completed_steps = sum(1 for step in self.steps if step.status == ProgressStatus.COMPLETED)
        failed_steps = sum(1 for step in self.steps if step.status == ProgressStatus.ERROR)
        
        return {
            'task_id': self.task_id,
            'task_name': self.task_name,
            'start_time': self.start_time.isoformat(),
            'total_duration': total_duration,
            'overall_progress': self.overall_progress,
            'total_steps': len(self.steps),
            'completed_steps': completed_steps,
            'failed_steps': failed_steps,
            'thinking_entries': len(self.thinking_log),
            'tool_calls': len(self.tool_calls),
            'log_entries': len(self.live_logs),
            'is_active': self.is_active,
            'steps': [step.to_dict() for step in self.steps],
            'thinking_log': [thinking.to_dict() for thinking in self.thinking_log],
            'tool_calls': self.tool_calls
        }
    
    def add_update_callback(self, callback: Callable):
        """Add callback for progress updates"""
        self.update_callbacks.append(callback)
    
    def remove_update_callback(self, callback: Callable):
        """Remove progress update callback"""
        if callback in self.update_callbacks:
            self.update_callbacks.remove(callback)


class ProgressTrackerManager:
    """Manages multiple progress trackers"""
    
    def __init__(self):
        self.active_trackers: Dict[str, LiveProgressTracker] = {}
        self._lock = threading.RLock()
    
    def create_tracker(self, session_id: str, user_id: str, task_name: str = "AI Task") -> LiveProgressTracker:
        """Create new progress tracker"""
        with self._lock:
            tracker = LiveProgressTracker(session_id, user_id, task_name)
            self.active_trackers[tracker.task_id] = tracker
            return tracker
    
    def get_tracker(self, task_id: str) -> Optional[LiveProgressTracker]:
        """Get existing tracker"""
        return self.active_trackers.get(task_id)
    
    def remove_tracker(self, task_id: str):
        """Remove completed tracker"""
        with self._lock:
            if task_id in self.active_trackers:
                del self.active_trackers[task_id]
    
    def get_session_trackers(self, session_id: str) -> List[LiveProgressTracker]:
        """Get all trackers for a session"""
        return [
            tracker for tracker in self.active_trackers.values()
            if tracker.session_id == session_id
        ]
    
    def cleanup_completed_trackers(self):
        """Clean up completed trackers"""
        with self._lock:
            completed_trackers = [
                task_id for task_id, tracker in self.active_trackers.items()
                if not tracker.is_active
            ]
            
            for task_id in completed_trackers:
                del self.active_trackers[task_id]


# Global instance
progress_manager = ProgressTrackerManager()