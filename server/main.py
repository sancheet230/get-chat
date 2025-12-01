from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile
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
from datetime import datetime

# App initialization
app = FastAPI(title="Get Chat API")

# CORS middleware
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

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGODB_URL)
db = client.getchat

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

class MessageResponse(BaseModel):
    id: str
    sender_id: str
    receiver_id: str
    content: str
    timestamp: datetime

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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise credentials_exception
    user = await db.users.find_one({"email": token_data.email})
    if user is None:
        raise credentials_exception
    return user

# Routes
@app.post("/api/register", response_model=UserResponse)
async def register_user(user: UserCreate):
    # Check if user already exists
    existing_user = await db.users.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
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
    # Find user by email
    db_user = await db.users.find_one({"email": user.email})
    if not db_user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    # Verify password
    if not verify_password(user.password, db_user["password"]):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
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
    users_cursor = db.users.find({}, {"password": 0, "security_codes": 0})
    users = await users_cursor.to_list(length=100)
    for user in users:
        user["id"] = str(user["_id"])
        del user["_id"]
    return users

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
        del message["_id"]
    return messages

@app.post("/api/messages")
async def send_message(message: MessageCreate, current_user: dict = Depends(get_current_user)):
    message_doc = {
        "sender_id": str(current_user["_id"]),
        "receiver_id": message.receiver_id,
        "content": message.content,
        "timestamp": datetime.utcnow()
    }
    
    result = await db.messages.insert_one(message_doc)
    message_doc["id"] = str(result.inserted_id)
    return message_doc

@app.get("/")
async def root():
    return {"message": "Get Chat API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)