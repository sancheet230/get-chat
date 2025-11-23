from fastapi import FastAPI, Depends, HTTPException, status
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
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGODB_URL)
db = client.getchat

# JWT configuration
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Models
class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    security_codes: List[str]

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

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
        expire = datetime.utcnow() + timedelta(minutes=15)
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

@app.get("/api/security-codes/{email}")
async def get_security_codes(email: str):
    # Find user by email
    db_user = await db.users.find_one({"email": email})
    if not db_user:
        raise HTTPException(status_code=400, detail="User not found")
    
    return {"security_codes": db_user["security_codes"]}

@app.get("/api/users")
async def get_users():
    users_cursor = db.users.find({}, {"password": 0, "security_codes": 0})
    users = await users_cursor.to_list(length=100)
    for user in users:
        user["id"] = str(user["_id"])
        del user["_id"]
    return users

@app.get("/api/messages/{user_id}")
async def get_messages(user_id: str):
    messages_cursor = db.messages.find({
        "$or": [
            {"sender_id": user_id},
            {"receiver_id": user_id}
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