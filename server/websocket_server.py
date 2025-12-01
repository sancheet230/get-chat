import asyncio
import websockets
import json
from motor.motor_asyncio import AsyncIOMotorClient
import jwt
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables from .env file in the root directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGODB_URL)
db = client.getchat

# JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"

# Store connected clients
connected_clients = {}

async def handle_client(websocket):
    try:
        # Wait for authentication message
        auth_message = await websocket.recv()
        auth_data = json.loads(auth_message)
        
        if auth_data.get("type") == "authenticate":
            token = auth_data.get("token")
            
            # Validate JWT token
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                email = payload.get("sub")
                
                # Get user from database
                user = await db.users.find_one({"email": email})
                if not user:
                    await websocket.close()
                    return
                
                user_id = str(user["_id"])
                
                print(f"User {email} connected with ID: {user_id}")
                
                # Store the client connection
                connected_clients[user_id] = websocket
                print(f"Connected clients: {list(connected_clients.keys())}")
                
                # Notify others that user is online
                await notify_user_status(user_id, "online")
                
                # Handle incoming messages
                async for message in websocket:
                    data = json.loads(message)
                    if data.get("type") == "message":
                        await handle_message(data, user_id)
                        
            except jwt.ExpiredSignatureError:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": "Token has expired"
                }))
                await websocket.close()
                return
            except jwt.PyJWTError:
                await websocket.close()
                return
                    
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

async def handle_message(data, sender_id):
    receiver_id = data.get("receiver_id")
    content = data.get("content")
    
    print(f"Handling message from {sender_id} to {receiver_id}: {content}")
    
    # Save message to database
    timestamp = datetime.utcnow()
    message_doc = {
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "content": content,
        "timestamp": timestamp
    }
    
    result = await db.messages.insert_one(message_doc)
    message_doc["id"] = str(result.inserted_id)
    
    # Prepare message data
    message_data = {
        "type": "message",
        "id": message_doc["id"],
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "content": content,
        "timestamp": message_doc["timestamp"].isoformat()
    }
    
    print(f"Message saved with ID: {message_doc['id']}")
    print(f"Sending to receiver: {receiver_id in connected_clients}")
    print(f"Sending to sender: {sender_id in connected_clients}")
    
    # Forward message to receiver if online
    if receiver_id in connected_clients:
        receiver_ws = connected_clients[receiver_id]
        try:
            await receiver_ws.send(json.dumps(message_data))
            print(f"Message sent to receiver {receiver_id}")
        except Exception as e:
            print(f"Error sending to receiver: {e}")
    
    # Also send back to sender for confirmation
    if sender_id in connected_clients:
        sender_ws = connected_clients[sender_id]
        try:
            await sender_ws.send(json.dumps(message_data))
            print(f"Message sent to sender {sender_id}")
        except Exception as e:
            print(f"Error sending to sender: {e}")

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

async def main():
    # Start the WebSocket server
    server = await websockets.serve(handle_client, "localhost", 8001)
    print("WebSocket server starting on ws://localhost:8001")
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())