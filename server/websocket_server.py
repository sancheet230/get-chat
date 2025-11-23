import asyncio
import websockets
import json
from motor.motor_asyncio import AsyncIOMotorClient

# MongoDB connection
import os
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGODB_URL)
db = client.getchat

# Store connected clients
connected_clients = {}

async def handle_client(websocket, path):
    try:
        # Wait for authentication message
        auth_message = await websocket.recv()
        auth_data = json.loads(auth_message)
        
        if auth_data.get("type") == "authenticate":
            user_id = auth_data.get("user_id")
            # Store the client connection
            connected_clients[user_id] = websocket
            
            # Notify others that user is online
            await notify_user_status(user_id, "online")
            
            # Handle incoming messages
            async for message in websocket:
                data = json.loads(message)
                if data.get("type") == "message":
                    await handle_message(data)
                    
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        # Clean up on disconnect
        user_id = None
        for uid, ws in connected_clients.items():
            if ws == websocket:
                user_id = uid
                break
        
        if user_id:
            del connected_clients[user_id]
            await notify_user_status(user_id, "offline")

async def handle_message(data):
    sender_id = data.get("sender_id")
    receiver_id = data.get("receiver_id")
    content = data.get("content")
    
    # Save message to database
    message_doc = {
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "content": content,
        "timestamp": asyncio.get_event_loop().time()
    }
    
    await db.messages.insert_one(message_doc)
    
    # Forward message to receiver if online
    if receiver_id in connected_clients:
        receiver_ws = connected_clients[receiver_id]
        await receiver_ws.send(json.dumps({
            "type": "message",
            "sender_id": sender_id,
            "content": content,
            "timestamp": message_doc["timestamp"]
        }))

async def notify_user_status(user_id, status):
    # Notify all connected clients about user status change
    status_message = {
        "type": "user_status",
        "user_id": user_id,
        "status": status
    }
    
    # Send to all connected clients
    disconnected_clients = []
    for uid, websocket in connected_clients.items():
        try:
            await websocket.send(json.dumps(status_message))
        except websockets.exceptions.ConnectionClosed:
            disconnected_clients.append(uid)
    
    # Clean up disconnected clients
    for uid in disconnected_clients:
        del connected_clients[uid]

# Start the WebSocket server
start_server = websockets.serve(handle_client, "localhost", 8001)

if __name__ == "__main__":
    print("WebSocket server starting on ws://localhost:8001")
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()