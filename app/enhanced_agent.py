"""
Enhanced Manus Agent with Real-time Progress Tracking
Integrates with WebSocket manager for live updates
"""

import asyncio
import queue
import time
from datetime import datetime
from typing import Dict, Any, Optional, Callable
import json

from app.agent.manus import Manus
from app.logger import logger
from app.websocket_manager import get_websocket_manager


class EnhancedManus(Manus):
    """Enhanced Manus agent with real-time progress tracking"""
    
    def __init__(self, progress_callback: Optional[Callable] = None):
        super().__init__()
        self.progress_callback = progress_callback
        self.current_session_id = None
        self.progress_queue = None
        self.ws_manager = get_websocket_manager()
        
    def set_session(self, session_id: str, progress_queue: queue.Queue = None):
        """Set current chat session for progress tracking"""
        self.current_session_id = session_id
        self.progress_queue = progress_queue
        
    def send_progress_update(self, progress: int, step: str, details: Dict[str, Any] = None):
        """Send progress update via multiple channels"""
        update_data = {
            'progress': progress,
            'step': step,
            'details': details or {},
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Send to progress queue if available
        if self.progress_queue:
            try:
                self.progress_queue.put(update_data)
            except Exception as e:
                logger.error(f"Error sending to progress queue: {e}")
        
        # Send via WebSocket if available
        if self.ws_manager and self.current_session_id:
            try:
                self.ws_manager.send_progress_update(self.current_session_id, {
                    **update_data,
                    'session_id': self.current_session_id
                })
            except Exception as e:
                logger.error(f"Error sending WebSocket update: {e}")
        
        # Call custom callback if provided
        if self.progress_callback:
            try:
                self.progress_callback(update_data)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")
    
    def send_tool_update(self, tool_name: str, status: str, details: Dict[str, Any] = None):
        """Send tool execution update"""
        if self.ws_manager and self.current_session_id:
            self.ws_manager.send_tool_update(
                self.current_session_id, 
                tool_name, 
                status, 
                details
            )
    
    def send_thinking_update(self, thought: str):
        """Send AI thinking process update"""
        self.send_progress_update(
            progress=None,  # Thinking doesn't have specific progress
            step="Thinking...",
            details={
                'type': 'thinking',
                'thought': thought,
                'reasoning': True
            }
        )
    
    async def run_with_progress(self, message: str, progress_queue: queue.Queue = None) -> Dict[str, Any]:
        """Run agent with enhanced progress tracking"""
        if progress_queue:
            self.progress_queue = progress_queue
        
        try:
            # Initial setup
            self.send_progress_update(5, "Initializing AI agent...")
            
            # Parse and understand the request
            self.send_progress_update(15, "Understanding your request...")
            self.send_thinking_update(f"Analyzing message: {message[:100]}...")
            
            # Determine what tools/actions are needed
            self.send_progress_update(25, "Planning approach...")
            
            # Start processing with enhanced tracking
            result = await self._enhanced_run(message)
            
            # Final processing
            self.send_progress_update(95, "Finalizing response...")
            
            # Complete
            self.send_progress_update(100, "Response ready!")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in enhanced agent run: {e}")
            self.send_progress_update(0, f"Error occurred: {str(e)}")
            raise
        finally:
            # Signal completion to progress queue
            if self.progress_queue:
                self.progress_queue.put(None)  # Sentinel value
    
    async def _enhanced_run(self, message: str) -> Dict[str, Any]:
        """Enhanced run method with detailed progress tracking"""
        
        # Step 1: Text analysis and intent recognition
        self.send_progress_update(30, "Analyzing intent and context...")
        
        # Simulate some processing time for demonstration
        await asyncio.sleep(0.5)
        
        # Step 2: Tool selection and preparation
        self.send_progress_update(40, "Selecting appropriate tools...")
        self.send_thinking_update("Determining which tools are needed for this task...")
        
        # Step 3: Execute the original agent logic with progress tracking
        self.send_progress_update(50, "Processing with AI model...")
        
        # Hook into the original run method
        original_result = await super().run(message)
        
        # Step 4: Post-processing and formatting
        self.send_progress_update(80, "Formatting response...")
        
        # Enhanced result with metadata
        enhanced_result = {
            'content': original_result if isinstance(original_result, str) else str(original_result),
            'metadata': {
                'processing_time': time.time(),
                'tools_used': getattr(self, 'tools_used', []),
                'model_calls': getattr(self, 'model_calls', 0),
                'session_id': self.current_session_id,
                'enhanced': True
            },
            'status': 'completed'
        }
        
        return enhanced_result
    
    def _track_tool_execution(self, tool_name: str, action: str, **kwargs):
        """Track tool execution with real-time updates"""
        
        if action == 'start':
            self.send_tool_update(tool_name, 'starting', {
                'parameters': kwargs
            })
            self.send_thinking_update(f"Starting to use {tool_name} tool...")
            
        elif action == 'progress':
            progress = kwargs.get('progress', 0)
            self.send_tool_update(tool_name, 'running', {
                'progress': progress,
                'current_step': kwargs.get('step', '')
            })
            
        elif action == 'complete':
            self.send_tool_update(tool_name, 'completed', {
                'result': kwargs.get('result', {}),
                'execution_time': kwargs.get('execution_time', 0)
            })
            self.send_thinking_update(f"Completed {tool_name} tool execution")
            
        elif action == 'error':
            self.send_tool_update(tool_name, 'failed', {
                'error': kwargs.get('error', 'Unknown error'),
                'traceback': kwargs.get('traceback', '')
            })
    
    def _enhanced_file_operations(self, operation: str, **kwargs):
        """Enhanced file operations with progress tracking"""
        
        if operation == 'read_file':
            file_path = kwargs.get('file_path')
            self.send_progress_update(
                kwargs.get('progress', 60),
                f"Reading file: {file_path}",
                {'operation': 'file_read', 'file': file_path}
            )
            
        elif operation == 'write_file':
            file_path = kwargs.get('file_path')
            self.send_progress_update(
                kwargs.get('progress', 70),
                f"Writing file: {file_path}",
                {'operation': 'file_write', 'file': file_path}
            )
            
        elif operation == 'search_files':
            pattern = kwargs.get('pattern')
            self.send_progress_update(
                kwargs.get('progress', 65),
                f"Searching files: {pattern}",
                {'operation': 'file_search', 'pattern': pattern}
            )
    
    def create_code_suggestion(self, language: str, context: str, requirements: str) -> Dict[str, Any]:
        """Create code suggestions with progress tracking"""
        
        self.send_progress_update(60, f"Generating {language} code...")
        self.send_thinking_update(f"Creating {language} code based on: {requirements[:100]}...")
        
        # Simulate code generation process
        time.sleep(1)
        
        # This would integrate with the actual code generation logic
        code_result = {
            'language': language,
            'code': f"// Generated {language} code\n// Context: {context}\n// Requirements: {requirements}",
            'explanation': f"This {language} code implements the requested functionality.",
            'suggestions': [
                "Consider adding error handling",
                "Add unit tests for better coverage",
                "Document the function parameters"
            ]
        }
        
        self.send_progress_update(75, "Code generation completed")
        
        return code_result
    
    def analyze_project_structure(self, project_path: str) -> Dict[str, Any]:
        """Analyze project structure with progress tracking"""
        
        self.send_progress_update(45, "Analyzing project structure...")
        
        # This would integrate with actual project analysis
        analysis_result = {
            'project_type': 'web_application',
            'languages': ['python', 'javascript', 'html', 'css'],
            'frameworks': ['flask', 'react'],
            'structure': {
                'backend': ['app.py', 'models.py', 'api/'],
                'frontend': ['src/', 'components/', 'assets/'],
                'config': ['requirements.txt', 'package.json']
            },
            'recommendations': [
                "Add automated testing",
                "Implement proper logging",
                "Add API documentation"
            ]
        }
        
        self.send_progress_update(65, "Project analysis completed")
        
        return analysis_result


class ProgressTracker:
    """Helper class for tracking progress across multiple operations"""
    
    def __init__(self, total_steps: int, session_id: str = None):
        self.total_steps = total_steps
        self.current_step = 0
        self.session_id = session_id
        self.ws_manager = get_websocket_manager()
        
    def update(self, step_description: str, details: Dict[str, Any] = None):
        """Update progress"""
        self.current_step += 1
        progress = int((self.current_step / self.total_steps) * 100)
        
        if self.ws_manager and self.session_id:
            self.ws_manager.send_progress_update(self.session_id, {
                'progress': progress,
                'step': step_description,
                'current_step': self.current_step,
                'total_steps': self.total_steps,
                'details': details or {},
                'timestamp': datetime.utcnow().isoformat()
            })
    
    def complete(self, final_message: str = "Operation completed"):
        """Mark as complete"""
        if self.ws_manager and self.session_id:
            self.ws_manager.send_progress_update(self.session_id, {
                'progress': 100,
                'step': final_message,
                'current_step': self.total_steps,
                'total_steps': self.total_steps,
                'completed': True,
                'timestamp': datetime.utcnow().isoformat()
            })