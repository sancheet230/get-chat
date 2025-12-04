import asyncio
import websockets
import json
from motor.motor_asyncio import AsyncIOMotorClient
import jwt
from datetime import datetime
import os
from dotenv import load_dotenv
from bson import ObjectId

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
                    elif data.get("type") == "group_message":
                        await handle_group_message(data, user_id)
                    elif data.get("type") == "read_status":
                        # Handle read status updates
                        message_ids = data.get("message_ids", [])
                        if message_ids:
                            await handle_read_status(message_ids, user_id)
                    elif data.get("type") == "group_read_status":
                        # Handle group read status updates
                        group_id = data.get("group_id")
                        if group_id:
                            await handle_group_read_status(group_id, user_id)
                        
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
    media_url = data.get("media_url")
    media_type = data.get("media_type")
    
    print(f"Handling message from {sender_id} to {receiver_id}: {content}")
    
    # Save message to database
    timestamp = datetime.utcnow()
    message_doc = {
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "content": content,
        "timestamp": timestamp,
        "is_read": False
    }
    
    # Add media fields if present
    if media_url:
        message_doc["media_url"] = media_url
        message_doc["media_type"] = media_type
    
    result = await db.messages.insert_one(message_doc)
    message_doc["id"] = str(result.inserted_id)
    
    # Prepare message data
    message_data = {
        "type": "message",
        "id": message_doc["id"],
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "content": content,
        "timestamp": message_doc["timestamp"].isoformat(),
        "is_read": False
    }
    
    # Add media fields if present
    if media_url:
        message_data["media_url"] = media_url
        message_data["media_type"] = media_type
    
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
    
    # Get sender's username
    sender_user = await db.users.find_one({"_id": ObjectId(sender_id)})
    sender_username = sender_user["username"] if sender_user else "Unknown"
    
    # Send notification to all other connected clients
    notification_data = {
        "type": "notification",
        "message_id": message_doc["id"],
        "sender_id": sender_id,
        "sender_username": sender_username,
        "receiver_id": receiver_id,
        "content": content[:50] + "..." if len(content) > 50 else content,  # Truncate content for notification
        "timestamp": message_doc["timestamp"].isoformat(),
        "has_media": bool(media_url),
        "media_type": media_type
    }
    
    # Send notification only to the receiver if they are online
    if receiver_id in connected_clients:
        receiver_ws = connected_clients[receiver_id]
        try:
            await receiver_ws.send(json.dumps(notification_data))
            print(f"Notification sent to receiver {receiver_id}")
        except Exception as e:
            print(f"Error sending notification to receiver {receiver_id}: {e}")
    else:
        print(f"Receiver {receiver_id} is not connected, notification not sent")

# New function to handle read status updates
async def handle_read_status(message_ids, reader_id):
    print(f"Handling read status update for messages: {message_ids} by user: {reader_id}")
    
    # Update messages in database
    from bson import ObjectId
    result = await db.messages.update_many(
        {"_id": {"$in": [ObjectId(mid) for mid in message_ids]},
         "receiver_id": reader_id},
        {"$set": {"is_read": True}}
    )
    
    print(f"Updated {result.modified_count} messages to read status")
    
    # Send read status updates to senders
    for message_id in message_ids:
        # Find the message to get sender_id
        message = await db.messages.find_one({"_id": ObjectId(message_id)})
        if message and "sender_id" in message:
            sender_id = message["sender_id"]
            print(f"Found message {message_id} with sender {sender_id}")
            # Send read status update to sender if online
            if sender_id in connected_clients:
                sender_ws = connected_clients[sender_id]
                try:
                    read_update_data = {
                        "type": "read_status",
                        "message_id": message_id,
                        "reader_id": reader_id
                    }
                    await sender_ws.send(json.dumps(read_update_data))
                    print(f"Read status update sent to sender {sender_id} for message {message_id}")
                except Exception as e:
                    print(f"Error sending read status update to sender {sender_id}: {e}")
            else:
                print(f"Sender {sender_id} is not connected, cannot send read status update")
        else:
            print(f"Could not find message {message_id} or sender_id not in message")

# New function to handle group read status updates
async def handle_group_read_status(group_id, reader_id):
    print(f"Handling group read status update for group: {group_id} by user: {reader_id}")
    
    # Update group messages in database to mark them as read by this user
    # We'll store read status per user in a separate collection
    from bson import ObjectId
    timestamp = datetime.utcnow()
    
    # Create or update read status record
    await db.group_message_reads.update_one(
        {
            "group_id": group_id,
            "user_id": reader_id
        },
        {
            "$set": {
                "last_read_timestamp": timestamp
            }
        },
        upsert=True
    )
    
    print(f"Updated group read status for user {reader_id} in group {group_id}")
    
    # Send read status updates to group members
    group = await db.groups.find_one({"_id": ObjectId(group_id)})
    if group:
        for member in group["members"]:
            member_id = member["user_id"]
            # Skip the reader themselves
            if member_id == reader_id:
                continue
                
            # Send read status update to member if online
            if member_id in connected_clients:
                try:
                    read_update_data = {
                        "type": "group_read_status",
                        "group_id": group_id,
                        "reader_id": reader_id,
                        "timestamp": timestamp.isoformat()
                    }
                    await connected_clients[member_id].send(json.dumps(read_update_data))
                    print(f"Group read status update sent to member {member_id}")
                except Exception as e:
                    print(f"Error sending group read status update to member {member_id}: {e}")

async def handle_group_message(data, sender_id):
    group_id = data.get("group_id")
    content = data.get("content")
    media_url = data.get("media_url")
    media_type = data.get("media_type")
    
    print(f"Handling group message from {sender_id} to group {group_id}: {content}")
    
    # Verify user is a member of the group
    group = await db.groups.find_one({
        "_id": ObjectId(group_id),
        "members.user_id": sender_id
    })
    
    if not group:
        # Send error back to sender
        if sender_id in connected_clients:
            error_data = {
                "type": "error",
                "message": "Not a member of this group"
            }
            try:
                await connected_clients[sender_id].send(json.dumps(error_data))
            except Exception as e:
                print(f"Error sending error to sender {sender_id}: {e}")
        return
    
    # Save group message to database
    timestamp = datetime.utcnow()
    message_doc = {
        "group_id": group_id,
        "sender_id": sender_id,
        "content": content,
        "timestamp": timestamp,
        "is_read": False
    }
    
    # Add media fields if present
    if media_url:
        message_doc["media_url"] = media_url
        message_doc["media_type"] = media_type
    
    result = await db.group_messages.insert_one(message_doc)
    message_doc["id"] = str(result.inserted_id)
    
    # Prepare group message data
    message_data = {
        "type": "group_message",
        "id": message_doc["id"],
        "group_id": group_id,
        "sender_id": sender_id,
        "content": content,
        "timestamp": message_doc["timestamp"].isoformat(),
        "is_read": False
    }
    
    # Add media fields if present
    if media_url:
        message_data["media_url"] = media_url
        message_data["media_type"] = media_type
    
    print(f"Group message saved with ID: {message_doc['id']}")
    
    # Get sender info for notifications
    sender_user = await db.users.find_one({"_id": ObjectId(sender_id)})
    sender_username = sender_user["username"] if sender_user else "Unknown"
    
    # Send message to all group members who are online
    for member in group["members"]:
        member_id = member["user_id"]
            
        # Send to member if they're online
        if member_id in connected_clients:
            try:
                await connected_clients[member_id].send(json.dumps(message_data))
                print(f"Group message sent to member {member_id}")
                
                # Also send notification if not the sender
                if member_id != sender_id:
                    notification_data = {
                        "type": "notification",
                        "message_id": message_doc["id"],
                        "sender_id": sender_id,
                        "sender_username": sender_username,
                        "group_id": group_id,
                        "group_name": group["name"],
                        "content": content[:50] + "..." if len(content) > 50 else content,
                        "timestamp": message_doc["timestamp"].isoformat(),
                        "has_media": bool(media_url),
                        "media_type": media_type,
                        "is_group": True
                    }
                    await connected_clients[member_id].send(json.dumps(notification_data))
                    print(f"Group notification sent to member {member_id}")
            except Exception as e:
                print(f"Error sending group message to member {member_id}: {e}")

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