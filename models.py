from sqlalchemy import Column, Integer, Float, String, DateTime, UniqueConstraint
from datetime import datetime
from database import Base


class Measurement(Base):
    __tablename__ = "measurements"

    id = Column(Integer, primary_key=True, index=True)
    point_id = Column(Integer, index=True, nullable=False)
    value = Column(Float, nullable=False)
    timestamp = Column(String, index=True, nullable=False)
    device_token = Column(String, index=True, nullable=False)
    client_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("point_id", "timestamp", name="unique_point_timestamp"),
    )
        
class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    device_token = Column(String, unique=True, index=True, nullable=False)
    client_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    client_id = Column(Integer, nullable=False)

    role = Column(String, default="user")

    created_at = Column(DateTime, default=datetime.utcnow)