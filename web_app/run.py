#!/usr/bin/env python3
"""
OpenManus AI Web Platform - Startup Script
"""

import os
import sys
import subprocess
from pathlib import Path

def install_requirements():
    """Install required packages"""
    print("Installing requirements...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

def check_config():
    """Check if OpenManus configuration exists"""
    config_path = Path("../config/config.toml")
    if not config_path.exists():
        print("Warning: OpenManus config.toml not found. Creating example config...")
        example_config = Path("../config/config.example.toml")
        if example_config.exists():
            import shutil
            shutil.copy(example_config, config_path)
            print(f"Created {config_path} from example. Please update with your API keys.")
        else:
            print("Example config not found. Please create config.toml manually.")

def main():
    """Main startup function"""
    print("🚀 Starting OpenManus AI Web Platform...")
    
    # Change to web_app directory
    os.chdir(Path(__file__).parent)
    
    # Install requirements if needed
    try:
        import flask
        import flask_socketio
    except ImportError:
        install_requirements()
    
    # Check configuration
    check_config()
    
    # Start the application
    print("Starting Flask application...")
    from app import app, socketio
    
    print("✅ OpenManus AI Platform is ready!")
    print("🌐 Open your browser and go to: http://localhost:5000")
    print("👤 Demo login: admin / admin123")
    print("Press Ctrl+C to stop the server")
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)

if __name__ == "__main__":
    main()
