#!/usr/bin/env python3
"""
Enhanced Manus AI Platform - Main Application Runner
Cursor.com inspired AI development environment with advanced features
"""

import os
import sys
import threading
import time
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Create necessary directories
os.makedirs('logs', exist_ok=True)
os.makedirs('config', exist_ok=True)
os.makedirs('workspaces', exist_ok=True)
os.makedirs('uploads', exist_ok=True)
os.makedirs('temp', exist_ok=True)

# Set environment variables
os.environ.setdefault('SECRET_KEY', 'dev-secret-key-change-in-production')
os.environ.setdefault('DATABASE_URL', 'sqlite:///manus_enhanced.db')
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/0')

# Import the enhanced application
from enhanced_app import app, socketio, create_app

def start_redis_server():
    """Start Redis server if not running"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print("✅ Redis server is already running")
    except:
        print("⚠️  Redis server not found. Please install and start Redis:")
        print("   Ubuntu/Debian: sudo apt install redis-server")
        print("   macOS: brew install redis && brew services start redis")
        print("   Or run: redis-server")
        return False
    return True

def start_celery_worker():
    """Start Celery worker in background"""
    def run_worker():
        try:
            from app.tasks import celery
            celery.worker_main(['worker', '--loglevel=info', '--concurrency=4'])
        except Exception as e:
            print(f"❌ Error starting Celery worker: {e}")
    
    worker_thread = threading.Thread(target=run_worker, daemon=True)
    worker_thread.start()
    print("✅ Celery worker started")

def print_banner():
    """Print application banner"""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                      🤖 MANUS AI PLATFORM                    ║
    ║              Advanced AI Development Environment             ║
    ║                  Inspired by Cursor.com                     ║
    ╠══════════════════════════════════════════════════════════════╣
    ║                                                              ║
    ║  Features:                                                   ║
    ║  🔥 Real-time AI coding assistance                          ║
    ║  📊 Live progress tracking & debugging                      ║
    ║  📁 Advanced file management                                ║
    ║  🔧 GitHub integration & collaboration                      ║
    ║  🔑 Multi-API key management                                ║
    ║  👥 Multi-user platform                                     ║
    ║  🚀 Background task processing                              ║
    ║  💬 Live WebSocket communication                            ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)

def check_dependencies():
    """Check if all dependencies are installed"""
    required_packages = [
        'flask', 'flask_socketio', 'flask_login', 'flask_sqlalchemy',
        'redis', 'celery', 'gitpython', 'sqlalchemy'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing required packages: {', '.join(missing_packages)}")
        print("Install them with: pip install -r requirements.txt")
        return False
    
    print("✅ All required packages are installed")
    return True

def main():
    """Main application entry point"""
    print_banner()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check Redis
    if not start_redis_server():
        print("⚠️  Continuing without Redis (some features may not work)")
    
    # Create the Flask app
    enhanced_app = create_app()
    
    # Start Celery worker
    start_celery_worker()
    
    print("\n🚀 Starting Manus AI Platform...")
    print("📍 Server will be available at: http://localhost:5000")
    print("🔐 Default login: admin / admin123")
    print("\n💡 Features available:")
    print("   • Real-time AI chat with progress tracking")
    print("   • Multi-file upload and management")
    print("   • GitHub repository import")
    print("   • Live debugging and tool usage logs")
    print("   • Advanced API key management")
    print("   • Multi-user support")
    print("\n⚡ Press Ctrl+C to stop the server")
    print("=" * 60)
    
    try:
        # Run the application with WebSocket support
        socketio.run(
            enhanced_app,
            host='0.0.0.0',
            port=5000,
            debug=False,  # Set to False for production
            allow_unsafe_werkzeug=True,
            use_reloader=False  # Disable reloader when using threads
        )
    except KeyboardInterrupt:
        print("\n👋 Shutting down Manus AI Platform...")
        print("Thank you for using Manus AI!")
    except Exception as e:
        print(f"\n❌ Error starting application: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()