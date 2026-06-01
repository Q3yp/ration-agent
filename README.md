# Ration Agent

AI-powered dairy cattle nutrition formulation system. Multi-agent LangGraph swarm coordinates a Nutritionist, Researcher, and Coder to formulate optimal rations backed by the NASEM 2021 model.

**Live demo:** [ration.moueasy.fan](https://ration.moueasy.fan/)

## Features

- **NASEM 2021 Nutrient Predictions** -- MP, ME, amino acids, minerals, milk yield, DMI
- **SLSQP Optimizer** -- minimizes ration cost while meeting nutritional constraints
- **Multi-Agent Swarm** -- Nutritionist (supervisor), Researcher (web search), Coder (data analysis)
- **Real-time Streaming** -- SSE-based live response from agents
- **Session Persistence** -- PostgreSQL-backed via LangGraph checkpointer
- **Feed Management** -- user and system feedbases, semantic search, Excel import/export
- **Authentication** -- JWT, SMS verification (China +86), Google OAuth
- **Chat Interface** -- Next.js frontend with i18n (zh-CN, en-US)

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.13, FastAPI, LangGraph, LangChain |
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS |
| Database | PostgreSQL 17 + pgvector |
| Nutrition Model | [NASEM-Model-Python](https://github.com/CNM-University-of-Guelph/NASEM-Model-Python) (NASEM 2021) |
| Infra | Docker Compose |

## Quick Start

```bash
# 1. Clone
git clone https://github.com/Q3yp/ration-agent.git
cd ration-agent

# 2. Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env -- set at minimum:
#   JWT_SECRET (generate: python -c "import secrets; print(secrets.token_urlsafe(48))")
#   ADMIN_PASSWORD
#   OPENROUTER_API_KEY

# 3. Start everything
docker compose up
```

Backend: `http://localhost:8000` | Frontend: `http://localhost:3000`

### Development (without Docker)

```bash
# Database
docker compose up -d postgres

# Backend
cd backend && uv sync && uv run python main.py

# Frontend
cd frontend && npm install && npm run dev
```

## Environment Variables

Required in `backend/.env`:

| Variable | Description |
|----------|-------------|
| `JWT_SECRET` | Secret for JWT signing (32+ chars). App refuses to start without it. |
| `ADMIN_PASSWORD` | Password for the default admin user. Required on first run. |
| `OPENROUTER_API_KEY` | API key for LLM access via OpenRouter |
| `POSTGRES_HOST` | PostgreSQL host (default: `localhost`) |
| `POSTGRES_PORT` | PostgreSQL port (default: `5433`) |
| `POSTGRES_DB` | Database name (default: `ration_agent`) |
| `POSTGRES_USER` | Database user (default: `ration_user`) |
| `POSTGRES_PASSWORD` | Database password |

Optional:

| Variable | Description |
|----------|-------------|
| `EMBEDDING_API_KEY` | For semantic feed search |
| `USDA_API_KEY` | For USDA FoodData Central lookups |
| `IHUYI_SMS_ACCOUNT` / `IHUYI_SMS_PASSWORD` | SMS verification (China +86) |
| `GOOGLE_OAUTH_CLIENT_ID` | Google OAuth login |

See `backend/.env.example` for the full list.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/chat/stream/{session_id}` | Stream chat response (SSE) |
| POST | `/sessions/create` | Create session for an animal type |
| GET | `/sessions/{id}/history` | Load session message history |
| DELETE | `/sessions/{id}` | Soft-delete session |
| POST | `/files/upload/{session_id}` | Upload file to session workspace |
| GET | `/files/list/{session_id}` | List session files |
| POST | `/auth/sms/code` | Request SMS verification code |
| POST | `/auth/sms/register` | Register via phone + SMS code |
| POST | `/auth/jwt/login` | Login with credentials |
| GET | `/admin/users` | List users (admin only) |
| GET | `/health` | Health check |

## Acknowledgments

This project uses [NASEM-Model-Python](https://github.com/CNM-University-of-Guelph/NASEM-Model-Python) by [CNM, University of Guelph](https://github.com/CNM-University-of-Guelph) -- a Python implementation of the NASEM 2021 Nutrient Requirements of Dairy Cattle model (licensed under MIT).
