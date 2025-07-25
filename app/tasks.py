"""
Celery tasks for background processing
"""
import os
import git
import shutil
import zipfile
from datetime import datetime
from typing import Dict, Any, List
from celery import Celery
import queue

from app.models import db, Task, UserFile, GitHubProject, ChatMessage
from app.logger import logger
from app.websocket_manager import get_websocket_manager


# Initialize Celery
celery = Celery('manus_tasks')
celery.conf.update(
    broker_url='redis://localhost:6379/0',
    result_backend='redis://localhost:6379/0',
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)


@celery.task(bind=True)
def process_file_upload(self, task_id: str, file_id: str, user_id: str):
    """Process uploaded file in background"""
    try:
        # Update task status
        task = Task.query.get(task_id)
        user_file = UserFile.query.get(file_id)
        
        if not task or not user_file:
            raise Exception("Task or file not found")
        
        task.status = 'running'
        task.started_at = datetime.utcnow()
        task.current_step = 'Starting file processing...'
        db.session.commit()
        
        # Progress tracking
        progress_steps = [
            (10, 'Reading file...'),
            (30, 'Analyzing content...'),
            (60, 'Extracting information...'),
            (80, 'Generating summary...'),
            (100, 'Processing complete')
        ]
        
        ws_manager = get_websocket_manager()
        result_data = {}
        
        for progress, step in progress_steps:
            task.progress = progress
            task.current_step = step
            db.session.commit()
            
            if ws_manager:
                ws_manager.send_user_notification(user_id, {
                    'type': 'task_progress',
                    'task_id': task_id,
                    'progress': progress,
                    'step': step
                })
            
            # Simulate processing time
            import time
            time.sleep(1)
            
            # Actual file processing based on step
            if progress == 30:
                # Analyze file content
                file_path = user_file.file_path
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    result_data['content_length'] = len(content)
                    result_data['line_count'] = content.count('\n')
            
            elif progress == 60:
                # Extract specific information based on file type
                if user_file.mime_type and 'text/' in user_file.mime_type:
                    result_data['file_type'] = 'text'
                    if user_file.filename.endswith('.py'):
                        result_data['language'] = 'python'
                    elif user_file.filename.endswith('.js'):
                        result_data['language'] = 'javascript'
                    else:
                        result_data['language'] = 'unknown'
            
            elif progress == 80:
                # Generate summary
                result_data['summary'] = f"Processed {user_file.original_filename} successfully"
                result_data['processed_at'] = datetime.utcnow().isoformat()
        
        # Update file as processed
        user_file.is_processed = True
        user_file.processing_result = result_data
        
        # Complete task
        task.status = 'completed'
        task.completed_at = datetime.utcnow()
        task.result_data = result_data
        db.session.commit()
        
        if ws_manager:
            ws_manager.send_user_notification(user_id, {
                'type': 'file_processed',
                'file_id': file_id,
                'result': result_data
            })
        
        return result_data
        
    except Exception as e:
        logger.error(f"Error processing file {file_id}: {e}")
        
        # Update task with error
        task = Task.query.get(task_id)
        if task:
            task.status = 'failed'
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
            db.session.commit()
        
        if ws_manager:
            ws_manager.send_user_notification(user_id, {
                'type': 'task_error',
                'task_id': task_id,
                'error': str(e)
            })
        
        raise


@celery.task(bind=True)
def import_github_project(self, task_id: str, repo_url: str, user_id: str):
    """Import GitHub project in background"""
    try:
        task = Task.query.get(task_id)
        if not task:
            raise Exception("Task not found")
        
        task.status = 'running'
        task.started_at = datetime.utcnow()
        task.current_step = 'Preparing to clone repository...'
        db.session.commit()
        
        ws_manager = get_websocket_manager()
        
        # Extract repo name from URL
        repo_name = repo_url.split('/')[-1].replace('.git', '')
        local_path = os.path.join('workspaces', user_id, 'github', repo_name)
        
        # Create GitHub project record
        github_project = GitHubProject(
            user_id=user_id,
            repo_url=repo_url,
            repo_name=repo_name,
            local_path=local_path,
            clone_status='cloning'
        )
        db.session.add(github_project)
        db.session.commit()
        
        # Progress steps for cloning
        progress_steps = [
            (20, 'Connecting to GitHub...'),
            (40, 'Cloning repository...'),
            (70, 'Processing files...'),
            (90, 'Finalizing import...'),
            (100, 'Import complete')
        ]
        
        for progress, step in progress_steps:
            task.progress = progress
            task.current_step = step
            db.session.commit()
            
            if ws_manager:
                ws_manager.send_user_notification(user_id, {
                    'type': 'github_import_progress',
                    'task_id': task_id,
                    'repo_name': repo_name,
                    'progress': progress,
                    'step': step
                })
            
            if progress == 40:
                # Actual cloning
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                if os.path.exists(local_path):
                    shutil.rmtree(local_path)
                
                repo = git.Repo.clone_from(repo_url, local_path)
                
            elif progress == 70:
                # Process files in the repository
                file_count = 0
                total_size = 0
                
                for root, dirs, files in os.walk(local_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            size = os.path.getsize(file_path)
                            total_size += size
                            file_count += 1
                        except OSError:
                            continue
                
                github_project.metadata = {
                    'file_count': file_count,
                    'total_size': total_size,
                    'imported_at': datetime.utcnow().isoformat()
                }
        
        # Complete the import
        github_project.clone_status = 'completed'
        github_project.last_sync = datetime.utcnow()
        
        task.status = 'completed'
        task.completed_at = datetime.utcnow()
        task.result_data = {
            'repo_name': repo_name,
            'local_path': local_path,
            'file_count': github_project.metadata.get('file_count', 0),
            'total_size': github_project.metadata.get('total_size', 0)
        }
        db.session.commit()
        
        if ws_manager:
            ws_manager.send_user_notification(user_id, {
                'type': 'github_import_complete',
                'project_id': github_project.id,
                'repo_name': repo_name,
                'result': task.result_data
            })
        
        return task.result_data
        
    except Exception as e:
        logger.error(f"Error importing GitHub project {repo_url}: {e}")
        
        # Update project status
        github_project = GitHubProject.query.filter_by(
            user_id=user_id,
            repo_url=repo_url
        ).first()
        if github_project:
            github_project.clone_status = 'failed'
            github_project.metadata = {'error': str(e)}
        
        # Update task
        task = Task.query.get(task_id)
        if task:
            task.status = 'failed'
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
            db.session.commit()
        
        if ws_manager:
            ws_manager.send_user_notification(user_id, {
                'type': 'github_import_error',
                'task_id': task_id,
                'error': str(e)
            })
        
        raise


@celery.task(bind=True)
def create_project_download(self, task_id: str, user_id: str, file_ids: List[str]):
    """Create downloadable package of modified files"""
    try:
        task = Task.query.get(task_id)
        if not task:
            raise Exception("Task not found")
        
        task.status = 'running'
        task.started_at = datetime.utcnow()
        task.current_step = 'Preparing download package...'
        db.session.commit()
        
        ws_manager = get_websocket_manager()
        
        # Create temp directory for package
        package_dir = os.path.join('temp', user_id, f'package_{task_id}')
        os.makedirs(package_dir, exist_ok=True)
        
        progress_steps = [
            (20, 'Collecting files...'),
            (50, 'Copying files...'),
            (80, 'Creating archive...'),
            (100, 'Package ready for download')
        ]
        
        collected_files = []
        
        for progress, step in progress_steps:
            task.progress = progress
            task.current_step = step
            db.session.commit()
            
            if ws_manager:
                ws_manager.send_user_notification(user_id, {
                    'type': 'download_progress',
                    'task_id': task_id,
                    'progress': progress,
                    'step': step
                })
            
            if progress == 20:
                # Collect files
                user_files = UserFile.query.filter(
                    UserFile.id.in_(file_ids),
                    UserFile.user_id == user_id
                ).all()
                collected_files = user_files
            
            elif progress == 50:
                # Copy files to package directory
                for user_file in collected_files:
                    if os.path.exists(user_file.file_path):
                        dest_path = os.path.join(package_dir, user_file.original_filename)
                        shutil.copy2(user_file.file_path, dest_path)
            
            elif progress == 80:
                # Create ZIP archive
                zip_path = f"{package_dir}.zip"
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(package_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, package_dir)
                            zipf.write(file_path, arcname)
        
        # Complete task
        task.status = 'completed'
        task.completed_at = datetime.utcnow()
        task.result_data = {
            'download_path': f"{package_dir}.zip",
            'file_count': len(collected_files),
            'package_size': os.path.getsize(f"{package_dir}.zip")
        }
        db.session.commit()
        
        # Clean up temp directory
        shutil.rmtree(package_dir)
        
        if ws_manager:
            ws_manager.send_user_notification(user_id, {
                'type': 'download_ready',
                'task_id': task_id,
                'download_url': f"/api/download/{task_id}",
                'result': task.result_data
            })
        
        return task.result_data
        
    except Exception as e:
        logger.error(f"Error creating download package: {e}")
        
        task = Task.query.get(task_id)
        if task:
            task.status = 'failed'
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
            db.session.commit()
        
        if ws_manager:
            ws_manager.send_user_notification(user_id, {
                'type': 'download_error',
                'task_id': task_id,
                'error': str(e)
            })
        
        raise


def start_celery_worker():
    """Start Celery worker process"""
    celery.worker_main(['worker', '--loglevel=info', '--concurrency=4'])