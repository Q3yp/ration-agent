# ration-agent

Multi-agent nutrition formulation system for dairy cows, beef cattle, cats, and dogs. Uses LangGraph Swarm to coordinate Nutritionist, Researcher, and Coder agents. Core calculations backed by NASEM 2021 (dairy/beef) and FEDIAF (companion animals). Includes SLSQP-based feed optimizer, real-time SSE streaming, and PostgreSQL-backed session persistence.

## Tech Stack

Backend: Python/FastAPI, LangGraph, LangChain, PostgreSQL, psycopg3. Frontend: Next.js/React, TypeScript, Tailwind CSS, shadcn/ui. LLMs: OpenRouter/DeepSeek via ChatOpenAI. Infra: Docker Compose, AWS.

## Quick Start

docker compose up (full stack) or: backend — uvicorn app.main:app; frontend — npm run dev

## Conventions

Multi-agent swarm pattern with handoff tools. Session state managed by LangGraph checkpointer (thread_id = session_id). Feedbases stored in LangGraph PostgresStore namespaces. Prompts loaded from Markdown templates via Jinja2. i18n: zh-CN primary, en-US secondary.

## Feature Paths (6)

### Feedbase Management & Export

> Tools and services for managing custom feedbases, searching feeds, and exporting usage reports.

| Step | Function | File | Lines | Note |
|------|----------|------|-------|------|
| 1 | `list_feedbases` | `backend/api/routes.py` | 869-937 | Lists user-created and system default feedbases from the store |
| 2 | `get_feedbase` | `backend/api/routes.py` | 941-985 | Retrieves full nutrient composition for a specific feedbase |
| 3 | `update_feedbase` | `backend/api/routes.py` | 989-1025 | Persists modified feedbase data to the PostgreSQL store |
| 4 | `export_feedbase` | `backend/api/routes.py` | 1069-1175 | Generates downloadable Excel reports of feed compositions and costs |
| 5 | `FormulationOptimizer.set_feeds` | `backend/formulation/optimizer.py` | 149-151 | Loads feedbase data into the optimizer for ration formulation |

### File Management (In-Chat)

> Flow for uploading and downloading files within a chat session.

| Step | Function | File | Lines | Note |
|------|----------|------|-------|------|
| 1 | `upload_file` | `backend/api/routes.py` | 691-736 | Uploads user-provided files to the session workspace. |
| 2 | `download_file` | `backend/api/routes.py` | 773-824 | Retrieves files from the workspace for the user. |
| 3 | `delete_file` | `backend/api/routes.py` | 742-769 | Removes files from the workspace. |

### Formulation Optimization Flow

> Calculates optimal ration using SLSQP optimization and NASEM nutrient predictions.

| Step | Function | File | Lines | Note |
|------|----------|------|-------|------|
| 1 | `FormulationOptimizer.optimize` | `backend/formulation/optimizer.py` | 889-1181 | Primary optimizer entry point using SLSQP |
| 2 | `FormulationOptimizer._get_nasem_values` | `backend/formulation/optimizer.py` | 231-317 | Predicts nutritional values (MP, ME, amino acids) using NASEM model |
| 3 | `FormulationOptimizer._get_nasem_milk_prod` | `backend/formulation/optimizer.py` | 330-352 | Calculates milk production based on the most limiting nutrient |
| 4 | `FormulationOptimizer._get_dmi` | `backend/formulation/optimizer.py` | 196-206 | Estimates dry matter intake from diet composition or override |
| 5 | `FormulationOptimizer._build_diet_for_nasem` | `backend/formulation/optimizer.py` | 208-229 | Translates feed inclusion percentages into normalized diet inputs |

### Session Management

> Flow for creating, listing, and deleting chat sessions.

| Step | Function | File | Lines | Note |
|------|----------|------|-------|------|
| 1 | `create_session` | `backend/api/routes.py` | 134-186 | Creates a new session for a specific animal type. |
| 2 | `list_sessions` | `backend/api/routes.py` | 200-206 | Retrieves the list of active sessions for the user. |
| 3 | `useSessionHistory` | `frontend/hooks/useSessionHistory.ts` | 31-72 | React hook for fetching session message history. |
| 4 | `delete_session` | `backend/api/routes.py` | 273-289 | Removes a session from the user’s view via soft delete. |

### User Authentication (SMS)

> Flow for user registration and login using SMS verification codes.

| Step | Function | File | Lines | Note |
|------|----------|------|-------|------|
| 1 | `SmsRegisterForm` | `frontend/components/auth/SmsRegisterForm.tsx` | 32-307 | Frontend form for mobile input and SMS code verification. |
| 2 | `request_sms_code` | `backend/auth/routes.py` | 166-234 | API endpoint to request a 6-digit verification code. |
| 3 | `SMSClient.send_verification_code` | `backend/auth/sms_service.py` | 59-87 | Sends the code via Ihuyi SMS API. |
| 4 | `register_with_sms` | `backend/auth/routes.py` | 238-345 | API endpoint to verify code and create account. |
| 5 | `login_with_identifier` | `backend/auth/routes.py` | 349-386 | API endpoint for password-based login. |

### User Chat Flow

> End-to-end flow from user message to agent response via streaming.

| Step | Function | File | Lines | Note |
|------|----------|------|-------|------|
| 1 | `stream_chat` | `backend/api/routes.py` | 538-686 | API entry point: receives message and starts SSE stream |
| 2 | `StopManager.stream_to_frontend` | `backend/utils/stop_manager.py` | 450-506 | Coordinates background producer and frontend replay |
| 3 | `StopManager._producer` | `backend/utils/stop_manager.py` | 283-448 | Runs LangGraph agent stream and caches events |
| 4 | `create_agent_swarm_for_type` | `backend/agents/nodes.py` | 101-125 | Initializes the multi-agent swarm (Nutritionist, Researcher, Coder) |
| 5 | `MessageProcessor.processSSEEvent` | `frontend/utils/messageProcessor.ts` | 136-279 | Frontend: processes incoming SSE events into UI messages |

## Directory Tree

```
|-- backend
|   |-- agents
|   |   `-- nodes.py  # Defines specialized agent nodes (Nutritionist, Researcher, Coder) and the swarm orchestration logic for the multi-agent system.
|   |-- api
|   |   |-- feedback_routes.py  # API endpoints for user feedback submission and admin-side feedback retrieval.
|   |   `-- routes.py  # Flask API routes: chat streaming, file downloads, session management.
|   |-- auth
|   |   |-- admin_routes.py  # FastAPI endpoints for administrative tasks, including user CRUD and animal type permission management.
|   |   |-- config.py  # Integration hub for fastapi_users; configures JWT-based authentication and superuser dependencies.
|   |   |-- database.py  # Configuration for asynchronous database operations in the authentication module; sets up the SQLAlchemy engine and provides async session generators.
|   |   |-- models.py  # SQLAlchemy models for user entities, including account tiers, permissions (allowed animal types), and local preferences.
|   |   |-- routes.py  # Defines authentication endpoints, including signup, login, session validation, and phone verification flows.
|   |   |-- schemas.py  # Pydantic data models for authentication workflows; defines standard and admin-specific user schemas, plus SMS verification and login request patterns.
|   |   `-- sms_service.py  # Asynchronous client for the Ihuyi SMS provider; manages authentication and template IDs.
|   |-- core
|   |   `-- agent.py  # LangGraph agent: defines FormulationState and orchestrates tool-calling loop.
|   |-- formulation
|   |   `-- optimizer.py  # Implements the feed formulation optimizer using SLSQP. Coordinates nutrient predictions via NASEM and animal performance models to minimize costs/maximize production.
|   |-- migrations
|   |   |-- data
|   |   |   `-- system_feedbases.json
|   |   `-- schema_manager.py  # Manages database schema updates and migrations in an idempotent way, ensuring base tables, user sessions, and LangGraph checkpointer tables are correctly initialized and updated.
|   |-- models
|   |   |-- api.py  # Pydantic models for the primary chat and session API; defines schemas for messages and session operations.
|   |   |-- chat.py  # Pydantic models and factory functions for defining parsed message types (user, agent, tool_call, etc.) used in the chat interface.
|   |   |-- common.py  # Core enum definitions for the application, specifically the AnimalType enum.
|   |   |-- feedback.py  # SQLAlchemy model and Pydantic schemas for user feedback; handles storage and retrieval of user comments and session links.
|   |   `-- feedbase.py  # Pydantic models for feed and feedbase data structures; handles dry matter, nutrition, and cost data.
|   |-- nasem_dairy
|   |   |-- dag
|   |   |   `-- ModelDAG.py  # Manages the Directed Acyclic Graph (DAG) for NASEM calculations, handling dependency parsing, execution order, and dynamic function generation.
|   |   |-- data
|   |   |   |-- demo
|   |   |   |   |-- calf_starter_feed.json
|   |   |   |   |-- dry_cow.json
|   |   |   |   |-- dry_cow_grazing.json
|   |   |   |   |-- dry_cow_late_gestation.json
|   |   |   |   |-- jersey_heifer.json
|   |   |   |   |-- lactating_cow_early_lactation.json
|   |   |   |   |-- lactating_cow_other.json
|   |   |   |   |-- lactating_cow_test.csv
|   |   |   |   `-- lactating_cow_test.json
|   |   |   |-- feed_library
|   |   |   |   `-- NASEM_feed_library.csv
|   |   |   `-- constants.py  # Extensive dictionary of nutritional and physiological constants used throughout the NASEM model calculation.
|   |   |-- model
|   |   |   |-- input_definitions.py  # TypedDict and schema definitions for NASEM model inputs, including animal, environment, and diet data.
|   |   |   |-- input_validation.py  # Provides validation functions for input data (animal, diet, feed library, etc.) ensuring they conform to expected schemas defined in input_definitions.py.
|   |   |   |-- nasem.py  # Implementation of the core NASEM 2021 dairy model; orchestrates high-fidelity nutritional calculations by integrating diverse equation modules.
|   |   |   `-- utility.py  # Utility functions for the NASEM model; handles input parsing (CSV/JSON), demo scenarios, and nutrient adjustment algorithms.
|   |   |-- model_output
|   |   |   |-- model_output_structure.json
|   |   |   |-- ModelOutput.py  # Defines the ModelOutput class which organizes, categorizes, and retrieves NASEM model computation results using JSON configuration files for reports and structure.
|   |   |   `-- report_structure.json
|   |   |-- nasem_equations
|   |   |   |-- amino_acid.py  # Detailed calculations for amino acid absorption, profiles, and utilization; implements 2021 NASEM equations for predicting milk protein response and amino acid efficiency.
|   |   |   |-- animal.py  # Functions for calculating animal-level intakes from diet and infusions, including efficiencies and physiological state adjustments for the NASEM model.
|   |   |   |-- body_composition.py  # Functions for calculating body component gains (fat, protein, ash, water) and empty body weight changes in dairy cattle.
|   |   |   |-- coefficient_adjustment.py  # Adjusts model coefficients like lower critical temperature based on animal age.
|   |   |   |-- dry_matter_intake.py  # Contains mathematical models and equations for predicting dry matter intake (DMI) across different animal physiological states (lactating, heifers, dry cows, calves) and diet compositions.
|   |   |   |-- energy_requirement.py  # Calculates net and metabolizable energy for maintenance, activity, growth, and gestation.
|   |   |   |-- fecal.py  # Estimates fecal output of nitrogen, organic matter, starch, and endogenous losses.
|   |   |   |-- gestation.py  # Models fetal growth, uterine weight dynamics, and nutrient requirements during pregnancy.
|   |   |   |-- infusion.py  # Functions to calculate nutrient contributions from infusions (ruminal, intestinal, arterial) into the NASEM model's nutrient supply.
|   |   |   |-- manure.py  # Calculates manure volume and composition, including volatile solids and mineral excretion.
|   |   |   |-- methane.py  # Calculates methane emissions (g/d, L/d) and intensity per unit of milk production.
|   |   |   |-- microbial_protein.py  # Estimates microbial nitrogen flow and protein synthesis in the rumen using multiple equation benchmarks (NRC 2021, NRC 2001, Virginia Tech).
|   |   |   |-- micronutrient_requirement.py  # Extensive calculations for mineral and vitamin requirements across various physiological states.
|   |   |   |-- milk.py  # Calculates milk composition, yield predictions (component or nutrient-based), and energy content.
|   |   |   |-- nutrient_intakes.py  # Functions to estimate animal nutrient intakes (energy, protein, minerals) based on dietary composition and dry matter intake, implementing NASEM dairy model equations.
|   |   |   |-- protein.py  # Models protein utilization, synthesis of scurf/export proteins, and metabolizable protein efficiency.
|   |   |   |-- protein_requirement.py  # Estimates metabolizable protein requirements for maintenance, growth, gestation, and lactation.
|   |   |   |-- report.py  # Utility for calculating peripheral metrics, ratios, and percentages for use in model reports.
|   |   |   |-- rumen.py  # Functions for estimating digestibility and passage of NDF and starch in the rumen.
|   |   |   |-- urine.py  # Calculates urinary nitrogen excretion, endogenous losses, and associated energy values.
|   |   |   `-- water.py  # Estimates voluntary water intake and balance based on diet and environment.
|   |   |-- sensitivity
|   |   |   |-- DatabaseManager.py  # SQLite database manager for sensitivity analysis, handling storage and retrieval of problems, coefficients, samples, and results using sqlite3 and pandas.
|   |   |   |-- response_variables_config.py  # Configuration file defining target response variables for NASEM model sensitivity analysis.
|   |   |   `-- SensitivityAnalyzer.py  # Handles sensitivity analysis for the NASEM dairy model using SOBOL methods; manages sampling, model execution, and results storage.
|   |   `-- pyproject.toml
|   |-- prompts
|   |   |-- coder.md  # System prompt for the Coder agent, focusing on data analysis and computational tasks without nutritional formulation.
|   |   |-- nutritionist.md  # System prompt for the lead Nutritionist agent, detailing NRC 2021 principles and formulation workflows.
|   |   |-- nutritionist_beef_cow.md  # System prompt for the Beef Cow Nutritionist agent, based on NRC 2016 standards and specific safety review protocols.
|   |   |-- nutritionist_cat.md  # System prompt for the Feline Nutritionist agent, adhering to FEDIAF 2025 standards for obligate carnivores.
|   |   |-- nutritionist_dairy_cow.md  # System prompt for the Dairy Cow Nutritionist agent, focused on NASEM 2021 model interactions and tool usage.
|   |   |-- nutritionist_dog.md  # System prompt for the Canine Nutritionist agent, based on FEDIAF 2025 standards and breed-specific needs.
|   |   |-- researcher.md  # System prompt for the Research agent, specializing in targeted information gathering for nutritionists.
|   |   `-- title_generation.md  # Prompt for generating concise, descriptive chat titles based on user messages.
|   |-- scripts
|   |   |-- build_companion_feedbases.py  # Fetches nutrient data from USDA for cat/dog ingredients and generates standardized system feedbases aligned with FEDIAF reporting requirements.
|   |   |-- extract_nasem_feeds.py  # Admin utility for extracting default feed library data from Excel sources into the system database.
|   |   |-- feed_embeddings.json
|   |   |-- feed_embeddings.json.bak
|   |   |-- feedipedia_to_nasem.py  # Builds an enriched dairy feedbase by mapping Feedipedia nutrient records to NASEM columns, selecting template feeds, and adapting nutrients for export.
|   |   |-- generate_new_embeddings.py  # Incremental embedding generator that creates embeddings only for new feeds added to the enriched feedbase. Preserves existing embeddings, supports batch API calls with retry logic, and backs up the original embeddings file before merging.
|   |   |-- manual_feed_overrides.json
|   |   |-- NASEM_feed_library.csv
|   |   |-- nasem_feedbase.json
|   |   |-- nasem_feedbase_enriched.json
|   |   |-- nasem_nutrient_graph.py  # Defines NASEM feed nutrient dependency rules and applies consistency-preserving overrides when external nutrient values replace template values.
|   |   `-- scrape_feedipedia.py  # Scrapes Feedipedia feed pages into a local SQLite database of feeds, sub-feeds, nutrient tables, and crawl metadata.
|   |-- services
|   |   |-- chat_history_service.py  # Handles persistence and retrieval of chat history and session summaries using LangGraph's Postgres checkpointer, ensuring conversation continuity.
|   |   |-- embedding_service.py  # Service for semantic feed search using OpenAI text embeddings, allowing users to find feeds by description or similar names.
|   |   |-- nasem_service.py  # Orchestrates NASEM model runs by preparing diet inputs, animal parameters, and selecting appropriate equations for nutrient prediction.
|   |   `-- session_manager.py  # Manages session lifecycle, database persistence (PostgreSQL), and file workspaces. Tracks token usage and provides session metadata/statistics.
|   |-- test_suite
|   |   |-- calculate_test_costs.py  # Analyzes token usage and calculates costs for completed test cases using Claude 4.5 pricing; generates detailed JSON reports.
|   |   |-- conclude_results.py  # Analyzes formulation test results to determine if nutritional targets were met and generates summary comparisons.
|   |   |-- dump_session.py  # Utility for serializing and dumping session state and messages to JSON files for debugging and testing purposes.
|   |   |-- extract_test_results.py  # Extracts test results (formulations, sessions, costs) from automated test runs.
|   |   |-- run_test_batch.py  # Orchestrates batch execution of multiple nutrition scenarios to validate model stability and prediction accuracy.
|   |   `-- test_beef_scenarios.py  # Integration tests for beef cow scenarios, validating NASEM predictions and formulation outcomes for beef cattle.
|   |-- tiktoken_cache
|   |   `-- 9b5ad71b2ce5302211f9c61530b329a4922fc6a4
|   |-- tools
|   |   |-- ask_user_tool.py  # Implementation of a tool that allows the agent to pause execution and request specific information from the user.
|   |   |-- excel_tools.py  # Provides tools for agents to read, write, and manipulate Excel files (xlsx) for ration reports and data analysis.
|   |   |-- formulation_exporter.py  # Tool for exporting formulation results to detailed Excel spreadsheets, including feed composition, cost analysis, nutrient constraints, and NASEM model predictions.
|   |   |-- formulation_tools.py  # Defines LangGraph tools for ration formulation (formulate_ration, check_feeds, add_feed), orchestrating feedbase access, validation, and optimizer execution.
|   |   |-- nasem_tools.py  # LangChain-compatible tools for agents; provides high-level interfaces for predicting dairy requirements and evaluating formulated diets via the NASEM model.
|   |   |-- tools.py  # Registry for all agent tools, grouping them into researcher, coder, and nutritionist toolkits for the swarm system.
|   |   |-- usda_client.py  # Reusable wrapper for the USDA FoodData Central API, providing search and retrieval of nutrient information with retry logic.
|   |   `-- usda_tools.py  # Tools for interacting with USDA databases or related services for feed composition data.
|   |-- utils
|   |   |-- deepseek_wrapper.py  # Wrapper for DeepSeek API calls, handling model-specific parameters and response parsing.
|   |   |-- language.py  # Utilities for handling language labels and locale normalization across the application.
|   |   |-- message_parser.py  # Unified parser for processing agent messages, handling streaming events, tool calls, and constructing structured messages (user, agent, tool, artifact) for the frontend.
|   |   |-- model_config.py  # Centralizes configuration and initialization of LLM models (FastChat, OpenAI, LangChain) used across different agents and tasks.
|   |   |-- prompt_loader.py  # Loads and renders Markdown-based prompt templates using Jinja2, providing a dynamic way to manage complex agent instructions.
|   |   |-- stop_manager.py  # Singleton stream lifecycle manager that handles background event caching, real-time token tracking, and unified replaying of cached events for resilient frontend streaming. Uses a global memory-based cache cap (env STOP_MANAGER_MAX_CACHE_MB, default 2GB) with head-trimming eviction on the largest session under memory pressure.
|   |   `-- system_feedbases.py  # Utility for accessing and listing read-only system default feedbases embedded in the application.
|   |-- .python-version
|   |-- analyze_session.py  # Diagnostic tool for analyzing chat session state stored in Postgres; calculates token usage and message breakdowns to optimize LLM performance.
|   |-- Dockerfile
|   |-- Dockerfile.deploy
|   |-- formulate_cli.py  # Command-line tool for animal ration formulation; supports custom constraints (CP, NDF, milk production) and connects with the NASEM evaluation service.
|   |-- main.py  # FastAPI entry point; handles app lifespan, database initialization, and route registration.
|   |-- pyproject.toml
|   |-- test_cost_analysis.json
|   `-- usda_cli.py  # CLI tool for searching and fetching food details from the USDA FoodData Central API.
|-- frontend
|   |-- app
|   |   |-- admin
|   |   |   `-- page.tsx  # Main page for the admin interface, featuring user management and feedback management tabs.
|   |   |-- api
|   |   |   `-- health
|   |   |       `-- route.ts  # API endpoint for basic health checks, providing status and uptime information.
|   |   |-- chat
|   |   |   `-- page.tsx  # The primary chat application page, managing sessions, user interface, and navigation.
|   |   |-- feedbases
|   |   |   `-- page.tsx  # Page for managing feedbases, allowing users to view and interact with their feed data.
|   |   |-- guide
|   |   |   `-- page.tsx  # User guide page providing instructions and documentation for the application.
|   |   |-- login
|   |   |   `-- page.tsx  # Login page component that handles user authentication and redirection to the chat interface.
|   |   |-- register
|   |   |   `-- page.tsx  # Registration page component that uses the SMS-based registration form for user onboarding.
|   |   |-- globals.css
|   |   |-- layout.tsx  # Root layout component for the application, handling metadata, cookies, i18n, and authentication providers.
|   |   `-- page.tsx  # Responsive landing page for the application with hero and feature sections.
|   |-- components
|   |   |-- admin
|   |   |   |-- FeedbackManagement.tsx  # Admin console for reviewing user feedback and associated chat sessions.
|   |   |   |-- UserForm.tsx  # Administrative form for creating or editing user accounts with role and tier management.
|   |   |   `-- UserManagement.tsx  # Admin dashboard for managing user accounts, including editing profile details, updating tiers, and configuring animal type permissions.
|   |   |-- auth
|   |   |   |-- LoginForm.tsx  # User interface for authentication; supports both standard credential login and Google OAuth2 integration with localized error states.
|   |   |   |-- ProtectedRoute.tsx  # Guard component that protects routes, requiring authentication and optional admin permissions.
|   |   |   |-- RegisterForm.tsx  # Legacy email/username-based registration form, replaced by SMS-based registration.
|   |   |   `-- SmsRegisterForm.tsx  # User interface for mobile-based registration; includes phone number normalization, SMS verification code management, and localized validation.
|   |   |-- chat
|   |   |   |-- ChatInterface.tsx  # Main chat UI component that captures user input, handles file uploads, renders messages via MessageList, and manages UI states (loading, typing, errors).
|   |   |   |-- HtmlArtifact.tsx  # Component for rendering HTML artifacts (reports, visualizations) in an iframe with expansion and download options.
|   |   |   |-- MarkdownMessage.tsx  # Renders chat messages as markdown, supporting GFM, LaTeX math, and custom table/code block styling.
|   |   |   |-- MessageBubble.tsx  # Main chat UI component that renders different message types (user, agent, tool calls, artifacts, role transitions) with specialized styling, animations, and interactive elements.
|   |   |   |-- MessageList.tsx  # UI component for displaying message history with dynamic state indicators (typing, thinking, etc.).
|   |   |   |-- TokenUsage.tsx  # Minimalist component for displaying prompt token usage in chat.
|   |   |   `-- TypingIndicator.tsx  # Visual indicator for agent activity; displays "thinking" reasoning steps, "formulation" or "analysis" operations, and general typing status.
|   |   |-- feedbase
|   |   |   |-- feedbaseCopy.ts  # Configuration for localized text strings and labels used in the feedbase management interface.
|   |   |   |-- FeedbaseEditor.tsx  # Advanced editor for managing feed databases; allows users to modify nutrient profiles, add new ingredients, and manage system-protected defaults.
|   |   |   |-- FeedbaseList.tsx  # Component listing available feedbases with options for selection, export, and deletion.
|   |   |   |-- FeedbaseManager.tsx  # Main UI for managing user-defined feedbases, including list, filter, and export.
|   |   |   |-- FeedEditor.tsx  # Interactive interface for editing feed nutrient concentrations and physical properties within a feedbase.
|   |   |   `-- FileUpload.tsx  # React component for uploading feed composition files (Excel/CSV/JSON) with validation and progress tracking.
|   |   |-- layout
|   |   |   |-- BackToChatButton.tsx  # Reusable navigation button for returning to the main chat interface.
|   |   |   |-- ConversationSidebar.tsx  # Main navigation component for chat history; manages session creation, animal type selection, and session-level actions like deletion.
|   |   |   `-- UserGuide.tsx  # Interactive documentation component featuring animated demos and feature walkthroughs.
|   |   `-- shared
|   |       |-- AnimalTypeSelector.tsx  # Dropdown selector for switching between animal types (dairy cow, beef cattle, etc.) to load appropriate model contexts.
|   |       |-- LocaleToggle.tsx  # Interactive button group for switching the application's language among supported locales.
|   |       |-- PlanUpgradeModal.tsx  # Subscription management dialog; provides a tiered comparison of service plans and features, highlighting the current user's tier.
|   |       `-- UserInputRequest.tsx  # Renders interactive forms for multi-agent 'ask_user' requests, allowing users to provide required numerical or text inputs.
|   |-- content
|   |   `-- userGuide.ts  # Static content and localized text for the user guide, organized by locale (zh-CN, en-US).
|   |-- contexts
|   |   |-- AuthContext.tsx  # React context providing global authentication state, user metadata, and methods for login, logout, and token management.
|   |   `-- I18nContext.tsx  # React context provider for internationalization, managing locale state (zh-CN/en-US), providing translation functions (t, tRaw), and handling server-side locale preference updates.
|   |-- hooks
|   |   |-- useAuth.ts  # Managed authentication state and actions, including login (credentials, Google), registration (SMS), and token verification.
|   |   |-- useMessages.ts  # Custom React hook that manages chat state, handles API interactions (sendMessage, loadHistory), processes SSE events, and coordinates message updates.
|   |   |-- useSessionHistory.ts  # Custom hook for fetching and managing chat message history for specific sessions.
|   |   `-- useSSEChat.ts  # React hook managing SSE connection for streaming chat messages and artifact updates.
|   |-- lib
|   |   |-- i18n
|   |   |   `-- locales.ts  # Definition of supported locales (zh-CN, en-US), translation strings for the entire app, and utilities for locale detection and string formatting.
|   |   `-- utils.ts  # Core frontend utilities, including Tailwind CSS class merging (cn) and formatting helpers.
|   |-- types
|   |   `-- chat.ts  # TypeScript definitions for chat messages, artifact data, and API request/response structures.
|   |-- utils
|   |   |-- authHeaders.ts  # Utility for generating HTTP headers with JWT tokens for authenticated API requests.
|   |   |-- errorHandler.ts  # Provides centralized error classification, recovery strategies, and localized user-friendly messaging for network, server, session, and streaming errors in the frontend.
|   |   |-- formatTime.ts  # Formatting utilities for displaying timestamps and relative dates in the chat and session history UI.
|   |   |-- httpClient.ts  # Custom HTTP client utility with integrated authentication, timeout handling, and JSON response parsing.
|   |   |-- messageProcessor.ts  # Centralizes message processing logic for realtime streaming and history loading, normalizing data from backend ParsedMessages and SSE events into a unified frontend Message format.
|   |   `-- roleMapping.ts  # Maps backend agent roles (researcher, nutritionist, coder) to UI-friendly labels, icons, and theme colors.
|   |-- .eslintrc.json
|   |-- components.json
|   |-- Dockerfile
|   |-- package.json
|   `-- tsconfig.tsbuildinfo
|-- .  # A LangGraph-based multi-agent system for dairy and companion animal nutrition formulation using NASEM 2021 and FEDIAF standards.
`-- AGENTS.md  # Workspace-specific agent instructions, including required repcon usage and project development conventions.
```

## Context Coverage

- **Files**: 146/178 described (82%)
- **Ignored**: 54 files
- **Functions**: 2320 extracted, 1644 call edges
- **Feature Paths**: 6 traced

---

*Auto-generated by `repcon export`. Do not edit manually.*
