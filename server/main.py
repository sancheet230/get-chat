from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Optional, List
import bcrypt
from jose import JWTError, jwt
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
import os
import uuid
import hashlib
import hmac
import urllib.parse
import base64
import aiohttp
import json
from bson import ObjectId

# App initialization
app = FastAPI(title="Get Chat API")

# Debug route registration
@app.on_event("startup")
async def debug_routes():
    print("Registered routes:")
    for route in app.routes:
        if hasattr(route, 'methods'):
            print(f"  {route.methods} {route.path}")
        else:
            print(f"  WebSocket {route.path}")

# CORS middleware
# Allow requests from localhost (development) and Vercel deployments
# Using allow_origins=["*"] for simplicity, but in production you might want to restrict this
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
import os
from dotenv import load_dotenv

# Load environment variables from .env file in the root directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# Cloudinary configuration
CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME')
CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY')
CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET')
CLOUDINARY_UPLOAD_URL = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload"

# Ensure collections exist
async def init_db():
    try:
        print("Initializing database collections...")
        # Test database connection
        await db.command("ping")
        print("Database connection successful")
        
        # Check if collections exist, create them if they don't
        collections = await db.list_collection_names()
        print(f"Existing collections: {collections}")
        
        # Create indexes for better performance
        await db.users.create_index("email", unique=True)
        await db.users.create_index("username", unique=True)
        await db.groups.create_index("name")
        await db.group_messages.create_index("group_id")
        await db.group_invitations.create_index([("group_id", 1), ("invited_user_id", 1)])
        await db.group_message_reads.create_index([("group_id", 1), ("user_id", 1)])
        print("Database indexes created successfully")
    except Exception as e:
        print(f"Error initializing database: {e}")
        import traceback
        traceback.print_exc()

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    print("Starting up server...")
    await init_db()
    print("Server startup complete")
    
    # Print all registered routes
    print("\nRegistered API routes:")
    for route in app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            print(f"  {', '.join(route.methods)} {route.path}")

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
print(f"Connecting to MongoDB at: {MONGODB_URL}")
try:
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client.getchat
    print(f"Connected to database: {db.name}")
except Exception as e:
    print(f"Failed to connect to MongoDB: {e}")

# JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

# Models
class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    profile_picture: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    security_codes: List[str]
    profile_picture: Optional[str] = None

class PublicUserResponse(BaseModel):
    id: str
    username: str
    email: str
    profile_picture: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class UserProfileUpdate(BaseModel):
    username: Optional[str] = None
    profile_picture: Optional[str] = None

class ProfilePictureUpdate(BaseModel):
    username: Optional[str] = None

class MessageCreate(BaseModel):
    receiver_id: str
    content: str

class MediaMessageCreate(BaseModel):
    receiver_id: str
    media_url: str
    media_type: str  # 'image' or 'video'

class MessageReadUpdate(BaseModel):
    message_ids: List[str]

class MessageResponse(BaseModel):
    id: str
    sender_id: str
    receiver_id: str
    content: str
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    timestamp: datetime
    is_read: Optional[bool] = False

# Group Models
class GroupCreate(BaseModel):
    name: str
    members: List[str]  # List of user IDs
    profile_picture: Optional[str] = None

class GroupMember(BaseModel):
    user_id: str
    role: str = "member"  # admin, member

class GroupResponse(BaseModel):
    id: str
    name: str
    members: List[GroupMember]
    created_at: datetime
    created_by: str
    profile_picture: Optional[str] = None

class GroupUpdate(BaseModel):
    name: Optional[str] = None
    profile_picture: Optional[str] = None

class GroupMessageCreate(BaseModel):
    group_id: str
    content: str
    media_url: Optional[str] = None
    media_type: Optional[str] = None

class GroupMessageResponse(BaseModel):
    id: str
    group_id: str
    sender_id: str
    content: str
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    timestamp: datetime
    is_read: Optional[bool] = False

# Group Invitation Models
class GroupInvitationCreate(BaseModel):
    group_id: str
    invited_user_id: str

class GroupInvitationResponse(BaseModel):
    id: str
    group_id: str
    group_name: str
    invited_user_id: str
    invited_by: str
    status: str  # pending, accepted, rejected
    created_at: datetime

class GroupInvitationUpdate(BaseModel):
    status: str  # accepted or rejected

# Utility functions
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    print(f"Authenticating user with token: {token[:10]}...")
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        print(f"Decoded email from token: {email}")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except jwt.ExpiredSignatureError:
        print("Token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as e:
        print(f"JWT error: {e}")
        raise credentials_exception
    user = await db.users.find_one({"email": token_data.email})
    print(f"Found user: {user}")
    if user is None:
        raise credentials_exception
    return user

# Routes
@app.post("/api/register", response_model=UserResponse)
async def register_user(user: UserCreate):
    # Check if user already exists by email
    existing_user = await db.users.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check if username is already taken
    existing_username = await db.users.find_one({"username": user.username})
    if existing_username:
        raise HTTPException(status_code=400, detail="Username already taken")
    
    # Hash password
    hashed_password = hash_password(user.password)
    
    # Generate 3 unique security codes
    security_codes = [str(uuid.uuid4())[:8] for _ in range(3)]
    
    # Create user document
    user_doc = {
        "username": user.username,
        "email": user.email,
        "password": hashed_password,
        "security_codes": security_codes,
        "profile_picture": user.profile_picture,
        "created_at": datetime.utcnow()
    }
    
    # Insert user into database
    result = await db.users.insert_one(user_doc)
    user_doc["id"] = str(result.inserted_id)
    
    # Return user without password
    user_doc.pop("password")
    return user_doc

@app.post("/api/login", response_model=Token)
async def login_user(user: UserLogin):
    print(f"Login attempt for email: {user.email}")
    # Find user by email
    db_user = await db.users.find_one({"email": user.email})
    print(f"Found user: {db_user}")
    if not db_user:
        print("User not found")
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    # Verify password
    password_valid = verify_password(user.password, db_user["password"])
    print(f"Password valid: {password_valid}")
    if not password_valid:
        print("Invalid password")
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    print(f"Generated access token: {access_token[:10]}...")
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/forgot-password")
async def forgot_password(email: str, security_code: str, new_password: str):
    # Find user by email
    db_user = await db.users.find_one({"email": email})
    if not db_user:
        raise HTTPException(status_code=400, detail="User not found")
    
    # Check if security code is valid
    if security_code not in db_user["security_codes"]:
        raise HTTPException(status_code=400, detail="Invalid security code")
    
    # Hash new password
    hashed_password = hash_password(new_password)
    
    # Update password
    await db.users.update_one(
        {"email": email},
        {"$set": {"password": hashed_password}}
    )
    
    return {"message": "Password updated successfully"}

@app.put("/api/profile", response_model=UserResponse)
async def update_profile(profile_update: UserProfileUpdate, current_user: dict = Depends(get_current_user)):
    # Update user profile
    update_data = {}
    if profile_update.username is not None:
        # Check if username is already taken by another user
        if profile_update.username != current_user["username"]:
            existing_username = await db.users.find_one({"username": profile_update.username})
            if existing_username:
                raise HTTPException(status_code=400, detail="Username already taken")
        update_data["username"] = profile_update.username
    if profile_update.profile_picture is not None:
        update_data["profile_picture"] = profile_update.profile_picture
    
    if update_data:
        await db.users.update_one(
            {"_id": current_user["_id"]},
            {"$set": update_data}
        )
        
        # Update current_user with new data
        current_user.update(update_data)
    
    # Return updated user without password
    user_response = current_user.copy()
    user_response["id"] = str(user_response["_id"])
    user_response.pop("_id", None)
    user_response.pop("password", None)
    user_response.pop("security_codes", None)
    return user_response

@app.post("/api/upload-profile-picture")
async def upload_profile_picture(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    # Log the Cloudinary configuration for debugging
    print(f"Cloudinary Config - Cloud Name: {CLOUDINARY_CLOUD_NAME}")
    print(f"Cloudinary Config - API Key: {CLOUDINARY_API_KEY}")
    print(f"Cloudinary Config - API Secret: {'*' * len(CLOUDINARY_API_SECRET) if CLOUDINARY_API_SECRET else None}")
    
    # Check if Cloudinary credentials are configured
    if not CLOUDINARY_CLOUD_NAME or not CLOUDINARY_API_KEY or not CLOUDINARY_API_SECRET:
        print("Cloudinary not properly configured, falling back to base64 encoding")
        # Fallback to base64 encoding if Cloudinary is not configured
        contents = await file.read()
        encoded_image = base64.b64encode(contents).decode('utf-8')
        image_url = f"data:{file.content_type};base64,{encoded_image}"
        
        # Update user's profile picture URL in database
        await db.users.update_one(
            {"_id": current_user["_id"]},
            {"$set": {"profile_picture": image_url}}
        )
        
        return {"url": image_url}
    
    try:
        print("Attempting Cloudinary upload")
        # Read the file content
        file_content = await file.read()
        
        # Validate file size (max 10MB)
        if len(file_content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")
        
        # Generate a fresh timestamp for each request using time.time() for accuracy
        import time
        timestamp = str(int(time.time()))
        
        # Prepare parameters for signing (excluding api_key and file which can't be part of signature)
        params = {
            'folder': 'getchat/profile_pictures',
            'overwrite': 'true',
            'public_id': f"user_{current_user['_id']}",
            'timestamp': timestamp
        }
        
        # Sort parameters by key and create signature string
        # Format: key1=value1&key2=value2&key3=value3
        sorted_params = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
        signature_string = f"{sorted_params}{CLOUDINARY_API_SECRET}"
        print(f"Parameters to sign: {params}")
        print(f"Sorted params string: {sorted_params}")
        print(f"Signature string (with secret): {sorted_params}[SECRET]")
        
        # Generate signature using SHA-1
        signature = hashlib.sha1(signature_string.encode('utf-8')).hexdigest()
        print(f"Generated signature: {signature}")
        
        # Prepare the form data for Cloudinary (including api_key but not in signature)
        form_data = aiohttp.FormData()
        # Use a default content type if not provided
        content_type = file.content_type if file.content_type else 'image/jpeg'
        form_data.add_field('file', file_content, filename=file.filename, content_type=content_type)
        form_data.add_field('api_key', CLOUDINARY_API_KEY)
        form_data.add_field('folder', 'getchat/profile_pictures')
        form_data.add_field('public_id', f"user_{current_user['_id']}")
        form_data.add_field('overwrite', 'true')
        form_data.add_field('timestamp', timestamp)
        form_data.add_field('signature', signature)
        
        # Make request to Cloudinary API
        async with aiohttp.ClientSession() as session:
            response = await session.post(
                CLOUDINARY_UPLOAD_URL,
                data=form_data
            )
            
            print(f"Cloudinary response status: {response.status}")
            print(f"Cloudinary response headers: {response.headers}")
            
            if response.status != 200:
                error_text = await response.text()
                print(f"Cloudinary upload failed: {error_text}")
                raise HTTPException(status_code=500, detail=f"Cloudinary upload failed: {error_text}")
            
            result = await response.json()
            print(f"Cloudinary upload successful: {result}")
        
        # Update user's profile picture URL in database
        await db.users.update_one(
            {"_id": current_user["_id"]},
            {"$set": {"profile_picture": result["secure_url"]}}
        )
        
        return {"url": result["secure_url"]}
    except Exception as e:
        print(f"Error uploading image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading image: {str(e)}")

@app.get("/api/security-codes/{email}")
async def get_security_codes(email: str):
    # Find user by email
    db_user = await db.users.find_one({"email": email})
    if not db_user:
        raise HTTPException(status_code=400, detail="User not found")
    
    return {"security_codes": db_user["security_codes"]}

@app.get("/api/users", response_model=List[PublicUserResponse])
async def get_users():
    print("Fetching users...")
    try:
        users_cursor = db.users.find({}, {"password": 0, "security_codes": 0})
        users = await users_cursor.to_list(length=100)
        print(f"Found {len(users)} users")
        for user in users:
            user["id"] = str(user["_id"])
            del user["_id"]
        print(f"Returning users: {users}")
        return users
    except Exception as e:
        print(f"Error fetching users: {e}")
        import traceback
        traceback.print_exc()
        return []

@app.get("/api/current-user", response_model=PublicUserResponse)
async def get_current_user_endpoint(current_user: dict = Depends(get_current_user)):
    # Return current user without password
    user_response = current_user.copy()
    user_response["id"] = str(user_response["_id"])
    user_response.pop("_id", None)
    user_response.pop("password", None)
    user_response.pop("security_codes", None)
    return user_response

@app.get("/api/messages/{user_id}", response_model=List[MessageResponse])
async def get_messages(user_id: str, current_user: dict = Depends(get_current_user)):
    # Get messages between current user and the specified user
    messages_cursor = db.messages.find({
        "$or": [
            {"sender_id": str(current_user["_id"]), "receiver_id": user_id},
            {"sender_id": user_id, "receiver_id": str(current_user["_id"])}
        ]
    }).sort("timestamp", 1)
    messages = await messages_cursor.to_list(length=100)
    for message in messages:
        message["id"] = str(message["_id"])
        # Add media fields if they exist
        if "media_url" in message:
            message["media_url"] = message["media_url"]
        if "media_type" in message:
            message["media_type"] = message["media_type"]
        if "is_read" not in message:
            message["is_read"] = False
        del message["_id"]
    return messages

@app.post("/api/messages")
async def send_message(message: MessageCreate, current_user: dict = Depends(get_current_user)):
    message_doc = {
        "sender_id": str(current_user["_id"]),
        "receiver_id": message.receiver_id,
        "content": message.content,
        "timestamp": datetime.utcnow(),
        "is_read": False
    }
    
    result = await db.messages.insert_one(message_doc)
    message_doc["id"] = str(result.inserted_id)
    return message_doc

@app.put("/api/messages/read")
async def mark_messages_as_read(update: MessageReadUpdate, current_user: dict = Depends(get_current_user)):
    # Update messages to mark them as read
    result = await db.messages.update_many(
        {"_id": {"$in": [ObjectId(mid) for mid in update.message_ids]},
         "receiver_id": str(current_user["_id"])},
        {"$set": {"is_read": True}}
    )
    return {"updated_count": result.modified_count}

@app.post("/api/upload-group-picture")
async def upload_group_picture(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    # Log the Cloudinary configuration for debugging
    print(f"Cloudinary Config - Cloud Name: {CLOUDINARY_CLOUD_NAME}")
    
    # Check if Cloudinary credentials are configured
    if not CLOUDINARY_CLOUD_NAME or not CLOUDINARY_API_KEY or not CLOUDINARY_API_SECRET:
        print("Cloudinary not properly configured, falling back to base64 encoding")
        # Fallback to base64 encoding if Cloudinary is not configured
        contents = await file.read()
        encoded_image = base64.b64encode(contents).decode('utf-8')
        image_url = f"data:{file.content_type};base64,{encoded_image}"
        return {"url": image_url}
    
    try:
        print("Attempting Cloudinary upload for group picture")
        # Read the file content
        file_content = await file.read()
        
        # Validate file size (max 10MB)
        if len(file_content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")
        
        # Generate a fresh timestamp for each request
        import time
        timestamp = str(int(time.time()))
        
        # Prepare parameters for signing
        params = {
            'folder': 'getchat/group_pictures',
            'overwrite': 'true',
            'public_id': f"group_{int(time.time())}",
            'timestamp': timestamp
        }
        
        # Sort parameters by key and create signature string
        sorted_params = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
        signature_string = f"{sorted_params}{CLOUDINARY_API_SECRET}"
        
        # Generate signature using SHA-1
        signature = hashlib.sha1(signature_string.encode('utf-8')).hexdigest()
        
        # Prepare the form data for Cloudinary
        form_data = aiohttp.FormData()
        content_type = file.content_type if file.content_type else 'image/jpeg'
        form_data.add_field('file', file_content, filename=file.filename, content_type=content_type)
        form_data.add_field('api_key', CLOUDINARY_API_KEY)
        form_data.add_field('folder', 'getchat/group_pictures')
        form_data.add_field('public_id', f"group_{int(time.time())}")
        form_data.add_field('overwrite', 'true')
        form_data.add_field('timestamp', timestamp)
        form_data.add_field('signature', signature)
        
        # Make request to Cloudinary API
        async with aiohttp.ClientSession() as session:
            response = await session.post(
                CLOUDINARY_UPLOAD_URL,
                data=form_data
            )
            
            print(f"Cloudinary response status: {response.status}")
            
            if response.status != 200:
                error_text = await response.text()
                print(f"Cloudinary upload failed: {error_text}")
                raise HTTPException(status_code=500, detail=f"Cloudinary upload failed: {error_text}")
            
            result = await response.json()
            print(f"Cloudinary upload successful: {result}")
        
        return {"url": result["secure_url"]}
    except Exception as e:
        print(f"Error uploading group picture: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading image: {str(e)}")

@app.post("/api/upload-media")
async def upload_media(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    # Log the Cloudinary configuration for debugging
    print(f"Cloudinary Config - Cloud Name: {CLOUDINARY_CLOUD_NAME}")
    print(f"Cloudinary Config - API Key: {CLOUDINARY_API_KEY}")
    print(f"Cloudinary Config - API Secret: {'*' * len(CLOUDINARY_API_SECRET) if CLOUDINARY_API_SECRET else None}")
    
    # Check if Cloudinary credentials are configured
    if not CLOUDINARY_CLOUD_NAME or not CLOUDINARY_API_KEY or not CLOUDINARY_API_SECRET:
        raise HTTPException(status_code=500, detail="Cloudinary not properly configured")
    
    try:
        print("Attempting Cloudinary media upload")
        # Read the file content
        file_content = await file.read()
        
        # Validate file size (max 10MB)
        if len(file_content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")
        
        # Determine media type
        media_type = 'image' if file.content_type.startswith('image/') else 'video' if file.content_type.startswith('video/') else 'other'
        
        # Generate a fresh timestamp for each request using time.time() for accuracy
        import time
        timestamp = str(int(time.time()))
        
        # Prepare parameters for signing
        params = {
            'folder': 'getchat/media',
            'overwrite': 'true',
            'public_id': f"media_{current_user['_id']}_{int(time.time())}",
            'timestamp': timestamp
        }
        
        # Sort parameters by key and create signature string
        sorted_params = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
        signature_string = f"{sorted_params}{CLOUDINARY_API_SECRET}"
        
        # Generate signature using SHA-1
        signature = hashlib.sha1(signature_string.encode('utf-8')).hexdigest()
        
        # Prepare the form data for Cloudinary
        form_data = aiohttp.FormData()
        form_data.add_field('file', file_content, filename=file.filename, content_type=file.content_type)
        form_data.add_field('api_key', CLOUDINARY_API_KEY)
        form_data.add_field('folder', 'getchat/media')
        form_data.add_field('public_id', f"media_{current_user['_id']}_{int(time.time())}")
        form_data.add_field('overwrite', 'true')
        form_data.add_field('timestamp', timestamp)
        form_data.add_field('signature', signature)
        
        # Make request to Cloudinary API
        async with aiohttp.ClientSession() as session:
            response = await session.post(
                CLOUDINARY_UPLOAD_URL,
                data=form_data
            )
            
            print(f"Cloudinary response status: {response.status}")
            
            if response.status != 200:
                error_text = await response.text()
                print(f"Cloudinary upload failed: {error_text}")
                raise HTTPException(status_code=500, detail=f"Cloudinary upload failed: {error_text}")
            
            result = await response.json()
            print(f"Cloudinary upload successful: {result}")
        
        return {"url": result["secure_url"], "type": media_type}
    except Exception as e:
        print(f"Error uploading media: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading media: {str(e)}")

@app.post("/api/send-media-message")
async def send_media_message(media_message: MediaMessageCreate, current_user: dict = Depends(get_current_user)):
    message_doc = {
        "sender_id": str(current_user["_id"]),
        "receiver_id": media_message.receiver_id,
        "content": "",
        "media_url": media_message.media_url,
        "media_type": media_message.media_type,
        "timestamp": datetime.utcnow(),
        "is_read": False
    }
    
    result = await db.messages.insert_one(message_doc)
    message_doc["id"] = str(result.inserted_id)
    return message_doc

@app.post("/api/groups", response_model=GroupResponse)
async def create_group(group: GroupCreate, request: Request, current_user: dict = Depends(get_current_user)):
    print(f"Received request to create group: {group.name}")
    print(f"Request headers: {dict(request.headers)}")
    try:
        print(f"Creating group with name: {group.name}")
        print(f"Current user: {current_user}")
        print(f"Group members: {group.members}")
        
        # Create group document
        group_doc = {
            "name": group.name,
            "members": [
                {"user_id": str(current_user["_id"]), "role": "admin"},  # Creator is admin
                *[{"user_id": member_id, "role": "member"} for member_id in group.members]
            ],
            "created_at": datetime.utcnow(),
            "created_by": str(current_user["_id"]),
            "profile_picture": group.profile_picture
        }
        
        print(f"Group document to insert: {group_doc}")
        
        # Insert group into database
        print(f"Inserting group document into database: {group_doc}")
        result = await db.groups.insert_one(group_doc)
        print(f"Insert result: {result}")
        group_doc["id"] = str(result.inserted_id)
        
        print(f"Group created successfully with ID: {group_doc['id']}")
        
        return group_doc
    except Exception as e:
        print(f"Error creating group: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/groups", response_model=List[GroupResponse])
async def get_user_groups(current_user: dict = Depends(get_current_user)):
    print(f"Fetching groups for user {current_user['_id']}")
    try:
        # Get groups where the user is a member
        groups_cursor = db.groups.find({
            "members.user_id": str(current_user["_id"])
        })
        groups = await groups_cursor.to_list(length=100)
        print(f"Found {len(groups)} groups for user {current_user['_id']}")
        for group in groups:
            group["id"] = str(group["_id"])
            del group["_id"]
        print(f"Returning groups: {groups}")
        return groups
    except Exception as e:
        print(f"Error fetching groups: {e}")
        import traceback
        traceback.print_exc()
        return []

@app.put("/api/groups/{group_id}", response_model=GroupResponse)
async def update_group(group_id: str, group_update: GroupUpdate, current_user: dict = Depends(get_current_user)):
    print(f"Updating group {group_id}")
    # Verify user is an admin of the group
    group = await db.groups.find_one({
        "_id": ObjectId(group_id),
        "members": {
            "$elemMatch": {
                "user_id": str(current_user["_id"]),
                "role": "admin"
            }
        }
    })
    
    if not group:
        raise HTTPException(status_code=403, detail="Only group admins can update group settings")
    
    # Prepare update data
    update_data = {}
    if group_update.name is not None:
        update_data["name"] = group_update.name
    if group_update.profile_picture is not None:
        update_data["profile_picture"] = group_update.profile_picture
    
    if update_data:
        await db.groups.update_one(
            {"_id": ObjectId(group_id)},
            {"$set": update_data}
        )
    
    # Return updated group
    updated_group = await db.groups.find_one({"_id": ObjectId(group_id)})
    updated_group["id"] = str(updated_group["_id"])
    del updated_group["_id"]
    
    return updated_group

@app.post("/api/group-messages")
async def send_group_message(message: GroupMessageCreate, current_user: dict = Depends(get_current_user)):
    print(f"Sending group message to group {message.group_id} from user {current_user['_id']}")
    # Verify user is a member of the group
    group = await db.groups.find_one({
        "_id": ObjectId(message.group_id),
        "members.user_id": str(current_user["_id"])
    })
    
    if not group:
        raise HTTPException(status_code=403, detail="Not a member of this group")
    
    # Create group message document
    message_doc = {
        "group_id": message.group_id,
        "sender_id": str(current_user["_id"]),
        "content": message.content,
        "timestamp": datetime.utcnow(),
        "is_read": False
    }
    
    # Add media fields if present
    if message.media_url:
        message_doc["media_url"] = message.media_url
        message_doc["media_type"] = message.media_type
    
    # Insert message into database
    result = await db.group_messages.insert_one(message_doc)
    message_doc["id"] = str(result.inserted_id)
    
    return message_doc

@app.get("/api/group-messages/{group_id}", response_model=List[GroupMessageResponse])
async def get_group_messages(group_id: str, current_user: dict = Depends(get_current_user)):
    print(f"Getting messages for group {group_id} for user {current_user['_id']}")
    # Verify user is a member of the group
    group = await db.groups.find_one({
        "_id": ObjectId(group_id),
        "members.user_id": str(current_user["_id"])
    })
    
    if not group:
        raise HTTPException(status_code=403, detail="Not a member of this group")
    
    # Get messages for the group
    messages_cursor = db.group_messages.find({
        "group_id": group_id
    }).sort("timestamp", 1)
    
    messages = await messages_cursor.to_list(length=100)
    for message in messages:
        message["id"] = str(message["_id"])
        # Add media fields if they exist
        if "media_url" in message:
            message["media_url"] = message["media_url"]
        if "media_type" in message:
            message["media_type"] = message["media_type"]
        if "is_read" not in message:
            message["is_read"] = False
        del message["_id"]
    
    return messages

@app.post("/api/group-invitations", response_model=GroupInvitationResponse)
async def create_group_invitation(invitation: GroupInvitationCreate, current_user: dict = Depends(get_current_user)):
    # Verify that the current user is an admin of the group
    group = await db.groups.find_one({
        "_id": ObjectId(invitation.group_id),
        "members": {
            "$elemMatch": {
                "user_id": str(current_user["_id"]),
                "role": "admin"
            }
        }
    })
    
    if not group:
        raise HTTPException(status_code=403, detail="Only group admins can invite members")
    
    # Check if the invited user exists
    invited_user = await db.users.find_one({"_id": ObjectId(invitation.invited_user_id)})
    if not invited_user:
        raise HTTPException(status_code=404, detail="Invited user not found")
    
    # Check if invitation already exists
    existing_invitation = await db.group_invitations.find_one({
        "group_id": invitation.group_id,
        "invited_user_id": invitation.invited_user_id,
        "status": "pending"
    })
    
    if existing_invitation:
        raise HTTPException(status_code=400, detail="Invitation already sent")
    
    # Create invitation document
    invitation_doc = {
        "group_id": invitation.group_id,
        "group_name": group["name"],
        "invited_user_id": invitation.invited_user_id,
        "invited_by": str(current_user["_id"]),
        "status": "pending",
        "created_at": datetime.utcnow()
    }
    
    # Insert invitation into database
    result = await db.group_invitations.insert_one(invitation_doc)
    invitation_doc["id"] = str(result.inserted_id)
    
    return invitation_doc

@app.put("/api/group-invitations/{invitation_id}", response_model=GroupInvitationResponse)
async def update_group_invitation(invitation_id: str, update: GroupInvitationUpdate, current_user: dict = Depends(get_current_user)):
    # Find the invitation
    invitation = await db.group_invitations.find_one({"_id": ObjectId(invitation_id)})
    
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    
    # Verify that the current user is the invited user
    if invitation["invited_user_id"] != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="Not authorized to respond to this invitation")
    
    # Update invitation status
    await db.group_invitations.update_one(
        {"_id": ObjectId(invitation_id)},
        {"$set": {"status": update.status}}
    )
    
    # If accepted, add user to the group
    if update.status == "accepted":
        # Add user to group members
        await db.groups.update_one(
            {"_id": ObjectId(invitation["group_id"])},
            {"$addToSet": {"members": {"user_id": str(current_user["_id"]), "role": "member"}}}
        )
    
    # Return updated invitation
    updated_invitation = await db.group_invitations.find_one({"_id": ObjectId(invitation_id)})
    updated_invitation["id"] = str(updated_invitation["_id"])
    del updated_invitation["_id"]
    
    return updated_invitation

@app.get("/api/group-invitations", response_model=List[GroupInvitationResponse])
async def get_user_invitations(current_user: dict = Depends(get_current_user)):
    print(f"Fetching invitations for user {current_user['_id']}")
    try:
        # Get pending invitations for the current user
        invitations_cursor = db.group_invitations.find({
            "invited_user_id": str(current_user["_id"]),
            "status": "pending"
        })
        
        invitations = await invitations_cursor.to_list(length=100)
        print(f"Found {len(invitations)} invitations for user {current_user['_id']}")
        for invitation in invitations:
            invitation["id"] = str(invitation["_id"])
            del invitation["_id"]
        
        print(f"Returning invitations: {invitations}")
        return invitations
    except Exception as e:
        print(f"Error fetching invitations: {e}")
        import traceback
        traceback.print_exc()
        return []
        import traceback
        traceback.print_exc()
        return []

@app.get("/api/group-read-status/{group_id}")
async def get_group_read_status(group_id: str, current_user: dict = Depends(get_current_user)):
    print(f"Getting read status for group {group_id} for user {current_user['_id']}")
    # Verify user is a member of the group
    group = await db.groups.find_one({
        "_id": ObjectId(group_id),
        "members.user_id": str(current_user["_id"])
    })
    
    if not group:
        raise HTTPException(status_code=403, detail="Not a member of this group")
    
    # Get read status for all members
    read_statuses = {}
    for member in group["members"]:
        member_id = member["user_id"]
        read_status = await db.group_message_reads.find_one({
            "group_id": group_id,
            "user_id": member_id
        })
        read_statuses[member_id] = read_status["last_read_timestamp"] if read_status and "last_read_timestamp" in read_status else None
    
    return read_statuses

@app.get("/")
async def root():
    return {"message": "Get Chat API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}

@app.get("/test")
async def test():
    return {"message": "Test endpoint working"}

@app.post("/api/test-group")
async def test_create_group():
    return {"message": "Test group creation endpoint working"}

@app.post("/api/debug-create-group")
async def debug_create_group(request: Request):
    print("Debug group creation endpoint hit!")
    print(f"Request headers: {dict(request.headers)}")
    try:
        body = await request.json()
        print(f"Request body: {body}")
    except Exception as e:
        print(f"Error reading request body: {e}")
    return {"message": "Debug endpoint working", "received": True}

if __name__ == "__main__":
    print("Starting server...")
    import uvicorn
    print("Server starting on port 8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
    print("Server stopped")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        print(f"User {user_id} connected via WebSocket")
    
    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            print(f"User {user_id} disconnected")
    
    async def send_personal_message(self, message: str, user_id: str):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_text(message)
            except Exception as e:
                print(f"Error sending to {user_id}: {e}")
                self.disconnect(user_id)
    
    async def broadcast(self, message: str, exclude_user: str = None):
        for user_id, connection in list(self.active_connections.items()):
            if user_id != exclude_user:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    print(f"Error broadcasting to {user_id}: {e}")
                    self.disconnect(user_id)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    user_id = None
    try:
        # Wait for authentication
        await websocket.accept()
        auth_message = await websocket.receive_text()
        auth_data = json.loads(auth_message)
        
        if auth_data.get("type") == "authenticate":
            token = auth_data.get("token")
            
            # Validate JWT token
            try:
                from jose import jwt as jose_jwt
                payload = jose_jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                email = payload.get("sub")
                
                # Get user from database
                user = await db.users.find_one({"email": email})
                if not user:
                    await websocket.close()
                    return
                
                user_id = str(user["_id"])
                manager.active_connections[user_id] = websocket
                print(f"User {email} connected with ID: {user_id}")
                
                # Handle incoming messages
                while True:
                    data_text = await websocket.receive_text()
                    data = json.loads(data_text)
                    
                    if data.get("type") == "message":
                        await handle_websocket_message(data, user_id)
                    elif data.get("type") == "group_message":
                        await handle_websocket_group_message(data, user_id)
                    elif data.get("type") == "read_status":
                        await handle_websocket_read_status(data, user_id)
                    elif data.get("type") == "group_read_status":
                        await handle_websocket_group_read_status(data, user_id)
                        
            except jose_jwt.ExpiredSignatureError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Token has expired"
                }))
                await websocket.close()
                return
            except Exception as e:
                print(f"Authentication error: {e}")
                await websocket.close()
                return
                    
    except WebSocketDisconnect:
        if user_id:
            manager.disconnect(user_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        if user_id:
            manager.disconnect(user_id)

async def handle_websocket_message(data, sender_id):
    receiver_id = data.get("receiver_id")
    content = data.get("content")
    media_url = data.get("media_url")
    media_type = data.get("media_type")
    
    # Save message to database
    timestamp = datetime.utcnow()
    message_doc = {
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "content": content,
        "timestamp": timestamp,
        "is_read": False
    }
    
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
    
    if media_url:
        message_data["media_url"] = media_url
        message_data["media_type"] = media_type
    
    # Send to receiver and sender
    await manager.send_personal_message(json.dumps(message_data), receiver_id)
    await manager.send_personal_message(json.dumps(message_data), sender_id)
    
    # Send notification
    sender_user = await db.users.find_one({"_id": ObjectId(sender_id)})
    notification_data = {
        "type": "notification",
        "message_id": message_doc["id"],
        "sender_id": sender_id,
        "sender_username": sender_user["username"] if sender_user else "Unknown",
        "receiver_id": receiver_id,
        "content": content[:50] + "..." if len(content) > 50 else content,
        "timestamp": message_doc["timestamp"].isoformat(),
        "has_media": bool(media_url),
        "media_type": media_type
    }
    await manager.send_personal_message(json.dumps(notification_data), receiver_id)

async def handle_websocket_group_message(data, sender_id):
    group_id = data.get("group_id")
    content = data.get("content")
    media_url = data.get("media_url")
    media_type = data.get("media_type")
    
    # Verify user is a member
    group = await db.groups.find_one({
        "_id": ObjectId(group_id),
        "members.user_id": sender_id
    })
    
    if not group:
        return
    
    # Save message
    timestamp = datetime.utcnow()
    message_doc = {
        "group_id": group_id,
        "sender_id": sender_id,
        "content": content,
        "timestamp": timestamp,
        "is_read": False
    }
    
    if media_url:
        message_doc["media_url"] = media_url
        message_doc["media_type"] = media_type
    
    result = await db.group_messages.insert_one(message_doc)
    message_doc["id"] = str(result.inserted_id)
    
    # Prepare message data
    message_data = {
        "type": "group_message",
        "id": message_doc["id"],
        "group_id": group_id,
        "sender_id": sender_id,
        "content": content,
        "timestamp": message_doc["timestamp"].isoformat(),
        "is_read": False
    }
    
    if media_url:
        message_data["media_url"] = media_url
        message_data["media_type"] = media_type
    
    # Send to all group members
    sender_user = await db.users.find_one({"_id": ObjectId(sender_id)})
    for member in group["members"]:
        member_id = member["user_id"]
        await manager.send_personal_message(json.dumps(message_data), member_id)
        
        # Send notification to others
        if member_id != sender_id:
            notification_data = {
                "type": "notification",
                "message_id": message_doc["id"],
                "sender_id": sender_id,
                "sender_username": sender_user["username"] if sender_user else "Unknown",
                "group_id": group_id,
                "group_name": group["name"],
                "content": content[:50] + "..." if len(content) > 50 else content,
                "timestamp": message_doc["timestamp"].isoformat(),
                "has_media": bool(media_url),
                "media_type": media_type,
                "is_group": True
            }
            await manager.send_personal_message(json.dumps(notification_data), member_id)

async def handle_websocket_read_status(data, reader_id):
    message_ids = data.get("message_ids", [])
    
    # Update messages in database
    result = await db.messages.update_many(
        {"_id": {"$in": [ObjectId(mid) for mid in message_ids]},
         "receiver_id": reader_id},
        {"$set": {"is_read": True}}
    )
    
    # Send read status updates to senders
    for message_id in message_ids:
        message = await db.messages.find_one({"_id": ObjectId(message_id)})
        if message and "sender_id" in message:
            sender_id = message["sender_id"]
            read_update_data = {
                "type": "read_status",
                "message_id": message_id,
                "reader_id": reader_id
            }
            await manager.send_personal_message(json.dumps(read_update_data), sender_id)

async def handle_websocket_group_read_status(data, reader_id):
    group_id = data.get("group_id")
    timestamp = datetime.utcnow()
    
    # Update read status
    await db.group_message_reads.update_one(
        {"group_id": group_id, "user_id": reader_id},
        {"$set": {"last_read_timestamp": timestamp}},
        upsert=True
    )
    
    # Notify group members
    group = await db.groups.find_one({"_id": ObjectId(group_id)})
    if group:
        for member in group["members"]:
            member_id = member["user_id"]
            if member_id != reader_id:
                read_update_data = {
                    "type": "group_read_status",
                    "group_id": group_id,
                    "reader_id": reader_id,
                    "timestamp": timestamp.isoformat()
                }
                await manager.send_personal_message(json.dumps(read_update_data), member_id)
