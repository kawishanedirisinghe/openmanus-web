#!/usr/bin/env python3
"""
Cursor Agents Platform - Run Script
Start the Flask application with proper configuration
"""

import os
import sys

def main():
    print("🤖 Starting Cursor Agents Platform...")
    print("=" * 50)
    
    # Set environment variables
    os.environ.setdefault('FLASK_ENV', 'development')
    os.environ.setdefault('FLASK_DEBUG', 'True')
    
    # Import and run the app
    try:
        from app import app, socketio, setup_demo_data
        
        # Setup demo data
        setup_demo_data()
        print("✅ Demo data loaded successfully")
        
        print("🌐 Starting server on http://localhost:5000")
        print("📱 Demo accounts available:")
        print("   • admin / admin123 (Administrator)")
        print("   • alice / alice123 (Team Member)")
        print("   • bob / bob123 (Team Member)")
        print("=" * 50)
        
        # Run the application
        socketio.run(app, debug=True, host='0.0.0.0', port=5000)
        
    except ImportError as e:
        print(f"❌ Error importing application: {e}")
        print("Make sure you've installed the requirements:")
        print("   pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()