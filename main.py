from fastapi import FastAPI
import os
from pydantic import BaseModel
from typing import List
from sqlalchemy.exc import IntegrityError

SECRET_KEY = os.environ.get("SECRET_KEY")

print("TYPE SECRET_KEY =", type(SECRET_KEY))
print("VALUE SECRET_KEY =", SECRET_KEY)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
print("DEBUG SECRET_KEY =", SECRET_KEY)


from database import engine, SessionLocal, Base
from models import Measurement, Device

from models import User

from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

app = FastAPI()



SECRET_KEY = os.getenv("SECRET_KEY")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# 🔥 IMPORTANT : crée les tables automatiquement
Base.metadata.create_all(bind=engine)


class MeasurementSchema(BaseModel):
    point_id: int
    value: float
    timestamp: str


class BatchRequest(BaseModel):
    device_token: str
    measurements: List[MeasurementSchema]


@app.post("/api/measurements/batch")
def receive_batch(batch: BatchRequest):
    db = SessionLocal()
    
    device = db.query(Device).filter(Device.device_token == batch.device_token).first()
    client_id = device.client_id

    if not device:
        db.close()
        print("Device inconnu :", batch.device_token)
        return {"success": False, "error": "Invalid device token"}


    inserted = 0

    measurements_to_insert = []

    for m in batch.measurements:
        measurement = Measurement(
            point_id=m.point_id,
            value=m.value,
            timestamp=m.timestamp,
            device_token=batch.device_token,
            client_id=client_id
        )
        measurements_to_insert.append(measurement)

    try:
        db.add_all(measurements_to_insert)
        db.commit()
        inserted = len(measurements_to_insert)
    except IntegrityError:
        db.rollback()

    db.close()

    print(f"Insertion OK : {inserted} nouvelles mesures")

    return {"success": True}


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


@app.get("/create-user-once")
def create_user_once():
    db = SessionLocal()

    # Supprimer si existe
    existing = db.query(User).filter(User.email == "admin@test.com").first()
    if existing:
        db.delete(existing)
        db.commit()

    hashed = pwd_context.hash("admin123")

    user = User(
        email="admin@test.com",
        hashed_password=hashed,
        client_id=1
    )

    db.add(user)
    db.commit()
    db.close()

    return {"message": "User created"}


@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    db = SessionLocal()

    user = db.query(User).filter(User.email == form_data.username).first()

    if not user:
        db.close()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(form_data.password, user.hashed_password):
        db.close()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(
        data={"sub": user.email, "client_id": user.client_id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    db.close()

    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/admin/add-role-column")
def add_role_column():
    db = SessionLocal()
    db.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
    db.commit()
    db.close()
    return {"status": "role column added"}
