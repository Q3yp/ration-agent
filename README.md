# Ration Agent

A sophisticated LangGraph ReAct Agent system designed for dairy cattle nutrition formulation and analysis. This multi-agent orchestrator provides specialized expertise in dairy cow ration formulation following NRC 2021 guidelines, with integrated research capabilities and code execution tools.

## 🎯 Key Features

- **Expert Dairy Nutrition AI**: Specialized supervisor agent with comprehensive NRC 2021 formulation knowledge
- **Multi-Agent Architecture**: Intelligent routing between research and code execution specialists
- **Interactive File Management**: Session-based workspaces with Excel processing capabilities
- **Real-time Streaming**: Server-sent events for live response streaming
- **Persistent Conversations**: PostgreSQL-backed state management with LangGraph checkpointing
- **Web Research Integration**: DuckDuckGo search and web crawling capabilities
- **HTML Artifacts**: Create interactive visualizations and reports

## 🏗️ Architecture

### Core Components

1. **Supervisor Agent**: Expert dairy nutritionist that analyzes requests and routes to appropriate workers
2. **Research Worker**: Handles knowledge base searches and web research
3. **Code Worker**: Executes Python code, processes Excel files, and manages session files
4. **Session Management**: Isolated workspaces with persistent state across conversations

### Technology Stack

- **Backend**: FastAPI, LangGraph, LangChain, PostgreSQL with pgvector
- **Frontend**: Next.js 15, React 19, TypeScript, Tailwind CSS
- **AI Models**: OpenAI/OpenRouter integration with configurable models per agent
- **Database**: PostgreSQL with vector extensions for conversation persistence

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker and Docker Compose
- OpenAI or OpenRouter API key

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd ration_agent
   ```

2. **Set up the database**
   ```bash
   docker-compose up -d postgres
   ```

3. **Backend setup**
   ```bash
   cd ration-agent/backend
   uv sync
   ```

4. **Frontend setup**
   ```bash
   cd ration-agent/frontend
   npm install
   ```

5. **Environment configuration**
   Create `.env` file in the backend directory:
   ```env
   # Database Configuration
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5433
   POSTGRES_DB=ration_agent
   POSTGRES_USER=ration_user
   POSTGRES_PASSWORD=ration_password
   
   # AI Model Configuration
   OPENROUTER_API_KEY=your_api_key_here
   OPENAI_ENDPOINT=https://openrouter.ai/api/v1
   OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
   
   # Agent Configuration
   LANGGRAPH_RECURSION_LIMIT=100

   # SMS Provider (required for phone registration/login flows)
   IHUYI_SMS_ACCOUNT=your_api_id
   IHUYI_SMS_PASSWORD=your_api_key
   IHUYI_SMS_TEMPLATE_ID=320655
   SMS_CODE_TTL_SECONDS=600
   SMS_CODE_RESEND_INTERVAL_SECONDS=60
   SMS_CODE_DAILY_LIMIT=20
   ```
   _Note: the current SMS provider only supports mainland China (+86) phone numbers._

### Running the Application

1. **Start the backend**
   ```bash
   cd ration-agent/backend
   uv run python main.py
   ```
   Backend runs on `http://localhost:8000`

2. **Start the frontend**
   ```bash
   cd ration-agent/frontend
   npm run dev
   ```
   Frontend runs on `http://localhost:3000`

## 📋 Usage Examples

### Basic Dairy Nutrition Consultation

```
User: "I need to formulate a ration for high-producing dairy cows (45kg milk/day, 3.8% fat, 3.2% protein)"

System: Supervisor analyzes the request and either:
- Provides direct nutritional guidance based on NRC 2021 principles
- Routes to researcher for specific ingredient information
- Routes to coder for optimization calculations
```

### Excel Data Analysis

```
User: "Analyze the feed composition data in my uploaded Excel file"

System: 
1. Coder processes the Excel file using pandas
2. Generates nutritional analysis and recommendations
3. Creates HTML artifacts with interactive charts
```

### Research Integration

```
User: "What are the latest trends in dairy cow nutrition for 2024?"

System:
1. Routes to researcher
2. Performs web searches and knowledge base queries
3. Synthesizes findings with expert nutritional context
```

## 🛠️ Development

### Backend Commands

```bash
# Install dependencies
cd ration-agent/backend && uv sync

# Start development server
uv run python main.py

# Alternative start method
uv run python start_server.py
```

### Frontend Commands

```bash
# Development
npm run dev

# Build for production
npm run build

# Lint code
npm run lint
```

### Database Management

```bash
# Start PostgreSQL with pgvector
docker-compose up -d postgres

# View logs
docker-compose logs postgres

# Stop database
docker-compose down
```

## 📡 API Endpoints

### Session Management
- `POST /sessions/create` - Create new session
- `GET /sessions/{session_id}/stats` - Get session statistics
- `DELETE /sessions/{session_id}` - Soft delete session
- `GET /sessions/{session_id}/history` - Get conversation history

### Chat Interface
- `POST /chat/stream/{session_id}` - Stream chat responses (SSE)

### File Operations
- `POST /files/upload/{session_id}` - Upload files to session workspace
- `GET /files/list/{session_id}` - List session files
- `DELETE /files/delete/{session_id}/{filename}` - Delete file

### Health Check
- `GET /health` - System health status

### Authentication
- `POST /auth/sms/code` - Request a verification code for register/login/bind flows
- `POST /auth/sms/register` - Complete registration using phone + SMS code (returns JWT)
  - Only mainland China (+86) numbers are supported; 11-digit inputs auto-normalize to `+86`.
- `POST /auth/login` - Password login that accepts username, email, or phone number identifiers

## 🔧 Configuration

### Model Configuration

Configure different models for different agent roles in `utils/model_config.py`:

```python
model_configs = {
    "supervisor": {"model": "anthropic/claude-3.5-sonnet", "temperature": 0},
    "researcher": {"model": "anthropic/claude-3.5-sonnet", "temperature": 0},
    "coder": {"model": "anthropic/claude-3.5-sonnet", "temperature": 0},
    "title_generation": {"model": "anthropic/claude-3.5-sonnet", "temperature": 0.3}
}
```

### Agent Prompts

Customize agent behavior by modifying prompts in `backend/prompts/`:
- `supervisor.md` - Main orchestrator with dairy nutrition expertise
- `researcher.md` - Research and knowledge retrieval specialist
- `coder.md` - Code execution and data analysis specialist

## 📊 State Management

The system uses LangGraph's `OrchestratorState` for managing multi-agent conversations:

- **Workflow Stages**: analyzing → delegating → working → synthesizing
- **Message Isolation**: Separate message threads for each agent role
- **Result Accumulation**: Persistent findings from research and code execution
- **Session Persistence**: PostgreSQL checkpointing with shared connection pooling

## 🔍 Expert Domain Knowledge

The supervisor agent is equipped with comprehensive dairy nutrition expertise:

- **NRC 2021 Guidelines**: Complete implementation of latest nutritional standards
- **Energy Requirements**: NEL calculations for different lactation stages
- **Protein Systems**: Metabolizable protein and microbial synthesis optimization
- **Fiber Management**: NDF digestibility and intake relationship modeling
- **Mineral Balance**: DCAD calculations and Ca:P ratio optimization

## 📁 Project Structure

```
ration_agent/
├── ration-agent/
│   ├── backend/                 # FastAPI backend
│   │   ├── agents/             # LangGraph agent nodes
│   │   ├── api/                # FastAPI routes
│   │   ├── core/               # Agent creation and management
│   │   ├── prompts/            # Agent prompt templates
│   │   ├── services/           # Session and chat history services
│   │   ├── utils/              # Tools, model config, parsers
│   │   └── files/              # Session workspaces
│   ├── frontend/               # Next.js frontend
│   │   ├── app/                # Next.js app router
│   │   ├── components/         # React components
│   │   ├── hooks/              # Custom React hooks
│   │   └── utils/              # Frontend utilities
│   └── docker-compose.yml      # Database configuration
└── README.md
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

[Add your license information here]

## 🆘 Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Ensure PostgreSQL is running: `docker-compose up -d postgres`
   - Check environment variables match docker-compose.yml

2. **Agent Not Responding**
   - Verify API key is configured correctly
   - Check model availability at your endpoint

3. **File Upload Issues**
   - Ensure session exists before uploading files
   - Check file size limits (10MB max) and allowed extensions

4. **Frontend Not Connecting**
   - Verify backend is running on port 8000
   - Check CORS configuration in FastAPI

### Debug Mode

Enable detailed logging by setting environment variables:
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"
export LOG_LEVEL=DEBUG
```

For more detailed guidance, see the [CLAUDE.md](./CLAUDE.md) file which contains technical implementation details for developers.
