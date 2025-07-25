# 🤖 Cursor Agents Platform

A modern, collaborative AI agent management platform inspired by [Cursor](https://cursor.com/agents). Create, manage, and execute AI agents with your team in a beautiful, intuitive interface.

## ✨ Features

### 🎯 Core Features
- **Agent Creation & Management** - Create AI agents with custom system prompts, capabilities, and models
- **Real-time Execution** - Execute agents with live progress tracking via WebSockets
- **Team Collaboration** - Share agents and collaborate with team members
- **Modern UI** - Beautiful dark theme interface inspired by Cursor's design
- **Multi-Model Support** - Support for GPT-4, Claude, and other AI models
- **Template System** - Pre-built agent templates for common use cases

### 🛠 Agent Capabilities
- **Code Generation** - Generate, debug, and review code
- **Data Analysis** - Analyze datasets and create visualizations
- **UI/UX Design** - Create beautiful interfaces and user experiences
- **Content Writing** - Write articles, documentation, and marketing copy
- **Research** - Gather and analyze information
- **Project Planning** - Plan and organize projects

### 👥 Team Features
- **Team Management** - Create and manage teams
- **Agent Sharing** - Share agents within teams
- **Collaborative Execution** - Team members can execute shared agents
- **Activity Tracking** - Monitor team activity and agent usage

### 📊 Dashboard & Analytics
- **Usage Statistics** - Track agent executions and success rates
- **Real-time Updates** - Live updates via WebSocket connections
- **Execution History** - Detailed logs of all agent executions
- **Performance Metrics** - Monitor agent performance and team productivity

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- pip or uv (recommended for faster installation)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd cursor_agents_platform
   ```

2. **Install dependencies**
   
   Using pip:
   ```bash
   pip install -r requirements.txt
   ```
   
   Using uv (recommended):
   ```bash
   uv pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   python app.py
   ```

4. **Access the platform**
   Open your browser and go to `http://localhost:5000`

### Demo Accounts

The platform comes with pre-configured demo accounts:

| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin123` | Administrator with full access |
| `alice` | `alice123` | Team member |
| `bob` | `bob123` | Team member |

## 📱 User Interface

### Dashboard
- **Overview Stats** - Total agents, active executions, team members, success rate
- **Quick Actions** - Create agent, join team, view history
- **Recent Activity** - Latest agents and executions
- **Team Activity** - Real-time team collaboration updates

### Agent Management
- **Grid/List Views** - Flexible viewing options for your agents
- **Search & Filter** - Find agents by name, description, or capabilities
- **Agent Templates** - Quick-start templates for common use cases
- **Execution Interface** - Execute agents with custom task descriptions

### Team Collaboration
- **Team Dashboard** - Manage team members and shared agents
- **Real-time Updates** - Live notifications when team members create or execute agents
- **Permission System** - Control who can view, edit, and execute agents

## 🏗 Architecture

### Backend (Flask)
- **Flask** - Web framework
- **Flask-SocketIO** - Real-time WebSocket communication
- **In-memory Storage** - Simple storage for demo (easily replaceable with database)
- **Modular Design** - Clean separation of concerns

### Frontend (Modern Web)
- **Tailwind CSS** - Utility-first CSS framework
- **Alpine.js** - Lightweight JavaScript framework
- **Font Awesome** - Icon library
- **Responsive Design** - Works on desktop, tablet, and mobile

### Key Components

```
cursor_agents_platform/
├── app.py                      # Main Flask application
├── requirements.txt            # Python dependencies
├── templates/
│   ├── base.html              # Base template with sidebar and navigation
│   ├── dashboard.html         # Main dashboard page
│   ├── agents.html            # Agent management interface
│   ├── login.html             # Login page with demo accounts
│   └── modals/
│       ├── create_agent.html  # Agent creation modal
│       └── create_team.html   # Team creation modal
└── README.md                  # This file
```

## 🤖 Agent System

### Agent Creation
Agents are created with the following properties:
- **Name & Description** - Human-readable identification
- **System Prompt** - Instructions that define the agent's behavior
- **Capabilities** - Tagged skills the agent possesses
- **AI Model** - The underlying LLM (GPT-4, Claude, etc.)
- **Team Assignment** - Optional team membership

### Agent Templates
Pre-built templates include:
- **Code Assistant** - Programming help, debugging, code review
- **Data Analyst** - Data processing, visualization, insights
- **UI/UX Designer** - Interface design, user experience
- **Content Writer** - Articles, documentation, marketing copy

### Execution System
- **Background Processing** - Agents run asynchronously
- **Real-time Updates** - Progress tracked via WebSockets
- **Logging** - Detailed execution logs
- **Error Handling** - Graceful error reporting

## 🔧 Configuration

### Environment Variables
```bash
# Optional: Set custom configuration
FLASK_ENV=development
FLASK_DEBUG=True
SECRET_KEY=your-secret-key
```

### Customization
- **Models** - Add support for new AI models in `app.py`
- **Capabilities** - Extend the capabilities list in agent templates
- **UI Theme** - Modify Tailwind configuration for custom styling
- **Storage** - Replace in-memory storage with database (PostgreSQL, MongoDB, etc.)

## 🌐 API Reference

### Authentication
All API endpoints require authentication via session.

### Agents
```bash
GET    /api/agents              # List user's agents
POST   /api/agents              # Create new agent
GET    /api/agents/{id}         # Get specific agent
PUT    /api/agents/{id}         # Update agent
DELETE /api/agents/{id}         # Delete agent
POST   /api/agents/{id}/execute # Execute agent
```

### Executions
```bash
GET    /api/executions          # List user's executions
GET    /api/executions/{id}     # Get specific execution
```

### Teams
```bash
GET    /api/teams               # List user's teams
POST   /api/teams               # Create new team
```

## 🔮 Roadmap

### Upcoming Features
- [ ] **Database Integration** - PostgreSQL/MongoDB support
- [ ] **Real AI Integration** - Connect to actual AI APIs (OpenAI, Anthropic)
- [ ] **File Management** - Upload and manage files for agents
- [ ] **Agent Workflows** - Chain multiple agents together
- [ ] **Version Control** - Track agent changes and rollbacks
- [ ] **API Keys Management** - Secure API key storage and rotation
- [ ] **Usage Analytics** - Detailed usage tracking and billing
- [ ] **Plugin System** - Extensible agent capabilities
- [ ] **Mobile App** - Native iOS/Android applications

### Integrations
- [ ] **GitHub Integration** - Import/export agents as code
- [ ] **Slack Bot** - Execute agents from Slack
- [ ] **VS Code Extension** - Integrate with Cursor-like IDE features
- [ ] **Zapier Webhooks** - Automate agent executions
- [ ] **Docker Deployment** - Containerized deployment options

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup
```bash
# Install development dependencies
pip install -r requirements.txt

# Run in development mode
FLASK_ENV=development python app.py

# The app will reload automatically on code changes
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Inspired by [Cursor](https://cursor.com/agents) - The AI code editor that sparked this project
- Built with modern web technologies and best practices
- Designed for developer productivity and team collaboration

## 📞 Support

- **Issues** - [GitHub Issues](https://github.com/your-repo/issues)
- **Discussions** - [GitHub Discussions](https://github.com/your-repo/discussions)
- **Email** - support@yourplatform.com

---

**Made with ❤️ for the AI development community**