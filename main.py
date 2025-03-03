import asyncio
from fastapi import FastAPI, UploadFile, HTTPException, BackgroundTasks, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import cv2
import numpy as np
import tempfile
import os
from typing import Optional, Dict
import shutil
from fastapi.responses import StreamingResponse, Response, FileResponse
import time
from datetime import datetime, timedelta
import socket
import struct
import threading
from dataclasses import dataclass
from queue import Queue
import zmq
import json
from sqlalchemy.orm import Session
from config import get_db, engine
import models
from models import TSSegment, User
from jose import JWTError, jwt
from typing import Optional
import m3u8
from pathlib import Path

# JWT Configuration
SECRET_KEY = "your-secret-key-keep-it-secret"  # In production, use environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# HLS Configuration
HLS_SEGMENT_DURATION = 2  # seconds
HLS_SEGMENTS_TO_KEEP = 5
HLS_OUTPUT_DIR = Path("hls_output")
HLS_OUTPUT_DIR.mkdir(exist_ok=True)

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

@app.post("/register")
async def register(username: str, password: str, db: Session = Depends(get_db)):
    # Check if user exists
    db_user = db.query(User).filter(User.username == username).first()
    if db_user:
        raise HTTPException(
            status_code=400,
            detail="Username already registered"
        )
    
    # Create new user
    hashed_password = User.get_password_hash(password)
    new_user = User(username=username, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {"message": "User created successfully"}

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Find user
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not User.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@dataclass
class StreamConfig:
    type: str  # 'udp', 'srt', 'hls'
    source: str  # stream URL
    delay: float
    output_type: str  # 'udp', 'srt', or 'hls'
    output_address: str
    segment_duration: float = 2.0  # Duration of each TS segment in seconds
    active: bool = True
    hls_output_dir: Optional[Path] = None

# Store active streams
streams: Dict[str, StreamConfig] = {}

async def store_ts_segment(db: Session, stream_id: str, segment_number: int, data: bytes, duration: float):
    """Store a TS segment in the database"""
    segment = TSSegment(
        stream_id=stream_id,
        segment_number=segment_number,
        data=data,
        duration=duration
    )
    db.add(segment)
    await db.commit()

async def get_delayed_segment(db: Session, stream_id: str, delay: float):
    """Get a delayed segment from the database"""
    delayed_time = datetime.utcnow() - timedelta(seconds=delay)
    segment = db.query(TSSegment).filter(
        TSSegment.stream_id == stream_id,
        TSSegment.timestamp <= delayed_time
    ).order_by(TSSegment.segment_number.asc()).first()
    
    if segment:
        # Delete the segment after retrieval
        db.delete(segment)
        await db.commit()
        return segment.data
    return None

async def process_udp_stream(stream_id: str, db: Session):
    config = streams[stream_id]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Parse multicast address and port
    host, port = config.source.split(':')
    port = int(port)
    
    # Join multicast group
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', port))
    mreq = struct.pack("4sl", socket.inet_aton(host), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    
    segment_buffer = bytearray()
    segment_start_time = time.time()
    segment_number = 0
    
    while config.active:
        data = sock.recv(65536)
        segment_buffer.extend(data)
        
        current_time = time.time()
        if current_time - segment_start_time >= config.segment_duration:
            # Store the complete segment
            await store_ts_segment(
                db,
                stream_id,
                segment_number,
                bytes(segment_buffer),
                current_time - segment_start_time
            )
            
            # Get and send delayed segment
            delayed_data = await get_delayed_segment(db, stream_id, config.delay)
            if delayed_data and config.output_type == 'udp':
                out_host, out_port = config.output_address.split(':')
                out_port = int(out_port)
                sock.sendto(delayed_data, (out_host, out_port))
            
            # Reset buffer and update counters
            segment_buffer = bytearray()
            segment_start_time = current_time
            segment_number += 1

async def process_hls_stream(stream_id: str, db: Session):
    config = streams[stream_id]
    stream_dir = HLS_OUTPUT_DIR / stream_id
    stream_dir.mkdir(exist_ok=True)
    
    segment_buffer = bytearray()
    segment_start_time = time.time()
    segment_number = 0
    playlist = m3u8.M3U8()
    playlist.target_duration = config.segment_duration
    
    while config.active:
        # Get delayed segment
        delayed_data = await get_delayed_segment(db, stream_id, config.delay)
        if delayed_data:
            # Write segment to file
            segment_file = stream_dir / f"segment_{segment_number}.ts"
            with open(segment_file, "wb") as f:
                f.write(delayed_data)
            
            # Update playlist
            segment = m3u8.Segment(
                uri=f"segment_{segment_number}.ts",
                duration=config.segment_duration,
                program_date_time=datetime.now()
            )
            playlist.add_segment(segment)
            
            # Keep only recent segments
            if len(playlist.segments) > HLS_SEGMENTS_TO_KEEP:
                old_segment = playlist.segments.pop(0)
                try:
                    os.remove(stream_dir / old_segment.uri)
                except FileNotFoundError:
                    pass
            
            # Write playlist file
            with open(stream_dir / "playlist.m3u8", "w") as f:
                f.write(playlist.dumps())
            
            segment_number += 1
        
        await asyncio.sleep(0.1)  # Prevent CPU overload

async def cleanup_old_segments(db: Session, stream_id: str, max_age_seconds: float):
    """Remove segments that are older than max_age_seconds"""
    cutoff_time = datetime.utcnow() - timedelta(seconds=max_age_seconds)
    db.query(TSSegment).filter(
        TSSegment.stream_id == stream_id,
        TSSegment.timestamp <= cutoff_time
    ).delete()
    await db.commit()

@app.get("/hls/{stream_id}/playlist.m3u8")
async def get_hls_playlist(stream_id: str, current_user: User = Depends(get_current_user)):
    if stream_id not in streams:
        raise HTTPException(status_code=404, detail="Stream not found")
    
    playlist_path = HLS_OUTPUT_DIR / stream_id / "playlist.m3u8"
    if not playlist_path.exists():
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    return FileResponse(
        playlist_path,
        media_type="application/vnd.apple.mpegurl",
        headers={"Cache-Control": "no-cache"}
    )

@app.get("/hls/{stream_id}/{segment_file}")
async def get_hls_segment(
    stream_id: str,
    segment_file: str,
    current_user: User = Depends(get_current_user)
):
    if stream_id not in streams:
        raise HTTPException(status_code=404, detail="Stream not found")
    
    segment_path = HLS_OUTPUT_DIR / stream_id / segment_file
    if not segment_path.exists():
        raise HTTPException(status_code=404, detail="Segment not found")
    
    return FileResponse(
        segment_path,
        media_type="video/MP2T"
    )

@app.post("/stream/start")
async def start_stream(
    stream_type: str,
    source: str,
    delay: float,
    output_type: str,
    output_address: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Start a new stream with the given configuration"""
    stream_id = f"{current_user.username}_{int(time.time())}"
    
    if stream_type not in ['udp', 'srt', 'hls']:
        raise HTTPException(status_code=400, detail="Invalid stream type")
    
    if output_type not in ['udp', 'srt', 'hls']:
        raise HTTPException(status_code=400, detail="Invalid output type")
    
    config = StreamConfig(
        type=stream_type,
        source=source,
        delay=delay,
        output_type=output_type,
        output_address=output_address
    )
    
    streams[stream_id] = config
    
    if stream_type == 'udp':
        background_tasks.add_task(process_udp_stream, stream_id, db)
    elif stream_type == 'srt':
        background_tasks.add_task(process_srt_stream, stream_id, db)
    elif stream_type == 'hls':
        background_tasks.add_task(process_hls_stream, stream_id, db)
    
    # Start cleanup task
    background_tasks.add_task(cleanup_old_segments, db, stream_id, delay + 60)
    
    return {"stream_id": stream_id}

@app.post("/stream/stop/{stream_id}")
async def stop_stream(
    stream_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if stream_id not in streams:
        raise HTTPException(status_code=404, detail="Stream not found")
    
    streams[stream_id].active = False
    
    db.query(TSSegment).filter(TSSegment.stream_id == stream_id).delete()
    await db.commit()
    
    del streams[stream_id]
    return {"status": "stopped"}

@app.get("/streams")
async def list_streams(current_user: User = Depends(get_current_user)):
    return {
        id: {
            "type": config.type,
            "source": config.source,
            "delay": config.delay,
            "output_type": config.output_type,
            "output_address": config.output_address
        }
        for id, config in streams.items()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
