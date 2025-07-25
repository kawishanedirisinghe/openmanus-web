# OpenManus AI Web Platform

An advanced web application similar to Replit AI and Manus.ai, built on top of the OpenManus multi-API key system. This platform provides a modern, responsive chat interface for interacting with multiple AI models with automatic failover and load balancing.

## Features

### 🤖 Advanced AI Chat Interface
- **Multi-Model Support**: GPT-4, GPT-3.5 Turbo, Claude 3 Opus, Claude 3 Sonnet
- **Real-time Communication**: WebSocket-based chat with instant responses
- **Markdown Rendering**: Full markdown support with syntax highlighting
- **Message History**: Persistent chat sessions with auto-save

### 🔑 Multi-API Key Integration
- **Automatic Failover**: Seamless switching between API keys when rate limits are hit
- **Load Balancing**: Intelligent distribution across multiple API keys
- **Usage Tracking**: Monitor API usage and costs per key
- **Rate Limit Management**: Automatic handling of rate limits and quotas

### 🎨 Modern UI/UX
- **Responsive Design**: Works perfectly on desktop, tablet, and mobile
- **Dark/Light Theme**: Toggle between themes with system preference detection
- **Glass Morphism**: Modern glass effects and gradients
- **Smooth Animations**: Fluid transitions and micro-interactions

### ⚙️ Advanced Settings
- **Temperature Control**: Adjust AI creativity from conservative to creative
- **Token Limits**: Configure maximum response length
- **Model Selection**: Switch between different AI models on the fly
- **User Preferences**: Persistent settings per user account

### 🔐 User Management
- **Secure Authentication**: Password hashing and session management
- **User Registration**: Easy account creation with validation
- **Session Persistence**: Remember user sessions across browser restarts
- **Demo Account**: Pre-configured admin account for testing

## Quick Start

### Prerequisites
- Python 3.8 or higher
- OpenManus configuration with API keys

### Installation

1. **Navigate to the web app directory:**
   ```bash
   cd web_app
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure OpenManus:**
   - Ensure your `config/config.toml` file exists with API keys
   - The startup script will create one from the example if needed

4. **Run the application:**
   ```bash
   python run.py
   ```

5. **Open your browser:**
   - Go to `http://localhost:5000`
   - Login with demo credentials: `admin` / `admin123`

## Configuration

### API Keys Setup
Make sure your `config/config.toml` includes multiple API keys for failover:

```toml
[openai]
api_keys = [
    { key = "sk-your-key-1", rate_limit = { minute = 60, hour = 1000, day = 10000 }, priority = 1 },
    { key = "sk-your-key-2", rate_limit = { minute = 60, hour = 1000, day = 10000 }, priority = 2 }
]

[anthropic]
api_keys = [
    { key = "sk-ant-your-key-1", rate_limit = { minute = 50, hour = 1000, day = 10000 }, priority = 1 }
]
```

### Environment Variables
- `FLASK_ENV`: Set to `development` for debug mode
- `SECRET_KEY`: Change the default secret key for production

## Architecture

### Backend Components
- **Flask Application**: Main web server with RESTful API
- **SocketIO**: Real-time WebSocket communication
- **OpenManus Integration**: Multi-API key management and LLM client wrapper
- **Session Management**: In-memory storage (extend to database for production)

### Frontend Components
- **Responsive UI**: Tailwind CSS with custom components
- **Real-time Chat**: Socket.IO client for instant messaging
- **Markdown Rendering**: Marked.js with Prism.js syntax highlighting
- **Theme System**: Dark/light mode with localStorage persistence

### Key Files
```
web_app/
├── app.py                 # Main Flask application
├── run.py                 # Startup script
├── requirements.txt       # Python dependencies
├── templates/
│   ├── base.html         # Base template with common components
│   ├── index.html        # Main dashboard and chat interface
│   ├── login.html        # User login page
│   └── register.html     # User registration page
└── README.md             # This file
```

## API Endpoints

### Authentication
- `GET /login` - Login page
- `POST /login` - Authenticate user
- `GET /register` - Registration page
- `POST /register` - Create new account
- `GET /logout` - Logout user

### Chat Management
- `GET /api/chat/sessions` - Get user's chat sessions
- `GET /api/chat/session/<id>` - Get specific chat session
- `POST /api/chat/session` - Create new chat session

### User Preferences
- `GET /api/preferences` - Get user preferences
- `POST /api/preferences` - Update user preferences
- `GET /api/models` - Get available AI models

### WebSocket Events
- `connect` - Client connection
- `disconnect` - Client disconnection
- `send_message` - Send chat message
- `message_added` - Receive new message
- `error` - Error notifications

## Usage Examples

### Starting a New Chat
1. Click "New Chat" in the sidebar
2. Select your preferred AI model from the dropdown
3. Type your message and press Enter or click Send
4. Watch as the AI responds in real-time

### Adjusting Settings
1. Click the settings gear icon
2. Adjust temperature for creativity control
3. Set maximum tokens for response length
4. Enable/disable auto-save for conversations

### Switching Models
- Use the model selector in the top bar
- Each message can use a different model
- Model information is saved with each response

## Production Deployment

### Database Integration
Replace in-memory storage with a proper database:
- User accounts and authentication
- Chat session persistence
- Message history storage
- User preferences and settings

### Security Enhancements
- Use environment variables for secrets
- Implement rate limiting per user
- Add CSRF protection
- Enable HTTPS in production

### Scaling Considerations
- Use Redis for session storage
- Implement horizontal scaling with load balancers
- Add monitoring and logging
- Consider CDN for static assets

## Troubleshooting

### Common Issues

**"Module not found" errors:**
```bash
pip install -r requirements.txt
```

**API key errors:**
- Check your `config/config.toml` file
- Ensure API keys are valid and have sufficient quota
- Verify the OpenManus configuration format

**WebSocket connection issues:**
- Check if port 5000 is available
- Ensure no firewall blocking the connection
- Try refreshing the browser page

**Chat not responding:**
- Check the browser console for errors
- Verify API keys have sufficient quota
- Check the Flask application logs

### Debug Mode
Run with debug enabled:
```bash
FLASK_ENV=development python run.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is part of the OpenManus ecosystem. Please refer to the main project license.

## Support

For issues and questions:
- Check the troubleshooting section above
- Review the OpenManus documentation
- Open an issue in the main repository

---

**Built with ❤️ using OpenManus Multi-API Key System**
