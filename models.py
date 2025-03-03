from sqlalchemy import Column, Integer, String, LargeBinary, DateTime, Float
from datetime import datetime
from config import Base
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    hashed_password = Column(String(100))
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    @staticmethod
    def verify_password(plain_password, hashed_password):
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password):
        return pwd_context.hash(password)

class TSSegment(Base):
    __tablename__ = "ts_segments"

    id = Column(Integer, primary_key=True, index=True)
    stream_id = Column(String(50), index=True)
    segment_number = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow)
    data = Column(LargeBinary)
    duration = Column(Float)  # Duration in seconds
