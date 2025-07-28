from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from routes import router

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan"""
    print("🚀 Starting LangGraph ReAct Agent API...")
    yield
    print("🛑 Shutting down...")

app = FastAPI(
    title="LangGraph ReAct Agent API",
    description="A FastAPI backend with LangGraph ReAct agent for chat interactions",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)