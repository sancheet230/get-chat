#!/usr/bin/env python3
"""
Startup script to run both FastAPI and WebSocket servers simultaneously
"""
import subprocess
import sys
import os
import signal
import time

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\nShutting down servers...")
    sys.exit(0)

def main():
    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Get port from environment (Render provides this)
    port = os.getenv("PORT", "8000")
    
    print("Starting Get Chat servers...")
    print(f"API Server will run on port {port}")
    print("WebSocket Server will run on port 8001")
    
    # Start FastAPI server
    api_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", port],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True
    )
    
    # Give API server a moment to start
    time.sleep(2)
    
    # Start WebSocket server
    ws_process = subprocess.Popen(
        [sys.executable, "websocket_server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True
    )
    
    print("Both servers started successfully!")
    print(f"API Server PID: {api_process.pid}")
    print(f"WebSocket Server PID: {ws_process.pid}")
    
    try:
        # Monitor both processes
        while True:
            # Check if API server is still running
            if api_process.poll() is not None:
                print("API server stopped unexpectedly!")
                ws_process.terminate()
                sys.exit(1)
            
            # Check if WebSocket server is still running
            if ws_process.poll() is not None:
                print("WebSocket server stopped unexpectedly!")
                api_process.terminate()
                sys.exit(1)
            
            # Print output from both servers
            if api_process.stdout:
                line = api_process.stdout.readline()
                if line:
                    print(f"[API] {line.strip()}")
            
            if ws_process.stdout:
                line = ws_process.stdout.readline()
                if line:
                    print(f"[WS] {line.strip()}")
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nShutting down servers...")
        api_process.terminate()
        ws_process.terminate()
        api_process.wait()
        ws_process.wait()
        print("Servers stopped.")

if __name__ == "__main__":
    main()
