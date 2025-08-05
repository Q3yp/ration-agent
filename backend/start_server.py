#!/usr/bin/env python3
"""
Start script for the Ration Agent backend server.
This provides a proper Python entry point for uv run start.
"""
import uvicorn

def main():
    """Start the uvicorn server with proper configuration."""
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["files/**"]
    )

if __name__ == "__main__":
    main()