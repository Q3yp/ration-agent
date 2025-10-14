# Repository Guidelines
## Project Structure & Module Organization
- `backend/` (FastAPI + LangGraph) houses agents, API routes, services, prompts, and `files/` session workspaces. Keep new agent logic under `agents/` and shared utilities in `utils/`.
- `frontend/` (Next.js App Router) contains UI modules; feature entry points live in `app/`, reusable pieces in `components/`, hooks in `hooks/`, and typed helpers in `lib/` and `types/`.
- `data/` stores sample ration spreadsheets used for demos—never commit edits.
- Root-level `docker-compose.yml`, `README.md`, and `SETUP.md` document environment, while `CLAUDE.md` and this guide coordinate agent contributors.

## Build, Test & Development Commands
- `uv sync` (in `backend/`) installs Python deps defined in `pyproject.toml`.
- `uv run python main.py` starts the API on `localhost:8000`; use `uv run python start_server.py` for reload-friendly dev.
- `uv run python basic_test.py` and `uv run python test_optimizer.py` exercise core LangGraph flows and the formulation engine.
- `npm install` and `npm run dev` (in `frontend/`) boot the web app on `localhost:3000`; use `npm run build` before release and `npm run lint` for static checks.
- `docker-compose up -d postgres` provisions the pgvector database required by the backend.

## Coding Style & Naming Conventions
- Python modules follow PEP 8: 4-space indentation, `snake_case` functions, `PascalCase` classes, type hints for public APIs, and docstrings for prompts/tools.
- Frontend TypeScript relies on ESLint + Next defaults: prefer functional components, `PascalCase` component files, `camelCase` hooks/utilities, and Tailwind utility classes in JSX.
- Keep agent prompt files in Markdown (`backend/prompts/`) and name them `role_animal.md` to match loader expectations.

## Testing Guidelines
- Add Python tests under `backend/` using `pytest`-compatible names (`test_*.py`); integration scripts may stay beside runtime modules if they assert behavior.
- Target coverage for new optimizer or agent flows; verify session state changes and tool outputs.
- For UI work, pair `npm run lint` with Storybook-style screenshots or screen recordings in PRs until automated tests land.

## Commit & PR Guidelines
- Mirror existing history: short, imperative subjects (`refactor stopmanager caching`, `add animal type selector`). Scope one feature or fix per commit.
- PRs should explain the motivation, summarize key changes, list test commands run, and link Jira/GitHub issues. Include screenshots or console output for UX changes.
- Request review from backend and frontend owners when touching both stacks; ensure docs (`README.md`, `SETUP.md`, prompts) stay in sync.

## Security & Configuration Tips
- Store secrets in `.env`; never commit API keys. Reference variables through `python-dotenv` or Next runtime env files.
- When using sample data, duplicate files into session-specific directories instead of editing shared spreadsheets.
- Before deploying, rotate `OPENROUTER_API_KEY`, verify PostgreSQL credentials in `docker-compose.yml`, and disable unused registration endpoints per `SETUP.md`.
