#!/usr/bin/env python3
"""
Startup script for Get Chat - runs FastAPI with integrated WebSocket
"""
import os
import uvicorn

if __name__ == "__main__":
    # Get port from environment (Render provides this)
    port = int(os.getenv("PORT", 8000))
    
    print(f"Starting Get Chat server on port {port}...")
    print("API and WebSocket endpoints available on same port")
    
    # Run uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
