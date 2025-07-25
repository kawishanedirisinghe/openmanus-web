# 🚀 Quick Setup Guide

## Prerequisites
- Python 3.8+
- Git

## 1. Install Dependencies

```bash
# Install required Python packages
pip install flask flask-socketio flask-login flask-sqlalchemy
pip install redis celery gitpython sqlalchemy flask-migrate
pip install flask-wtf wtforms werkzeug python-dotenv
pip install zipfile36 python-multipart websockets eventlet
pip install loguru
```

## 2. Install Redis (Required for background tasks)

### Ubuntu/Debian:
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl start redis
```

### macOS:
```bash
brew install redis
brew services start redis
```

### Windows:
Download and install Redis from: https://redis.io/download

## 3. Run the Application

```bash
# Clone or download the project files
# Navigate to project directory

# Run the application
python run_enhanced_app.py
```

## 4. Access the Platform

1. Open your browser
2. Go to: **http://localhost:5000**
3. Login with default credentials:
   - Username: `admin`
   - Password: `admin123`

## ✅ That's it! 

Your Manus AI Platform is now running with:
- Real-time AI chat
- Live progress tracking
- Multi-file upload
- GitHub integration
- Background processing
- Multi-user support

## 🔧 Optional: Add API Keys

1. Click **Settings** in the interface
2. Go to **API Keys** section
3. Add your API keys for:
   - OpenAI (for GPT-4)
   - Anthropic (for Claude)
   - DeepSeek (for R1)
   - Google (for Gemini)

## 🐛 Troubleshooting

**Redis Error?**
- Make sure Redis server is running: `redis-server`

**Permission Error?**
- Run with: `sudo python run_enhanced_app.py`

**Port 5000 in use?**
- Change port in `run_enhanced_app.py` line 110: `port=5001`