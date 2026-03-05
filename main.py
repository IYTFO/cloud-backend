from fastapi import FastAPI
import os
from pydantic import BaseModel
from typing import List
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

from security import hash_password, verify_password

SECRET_KEY = os.environ.get("SECRET_KEY")

print("TYPE SECRET_KEY =", type(SECRET_KEY))
print("VALUE SECRET_KEY =", SECRET_KEY)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
print("DEBUG SECRET_KEY =", SECRET_KEY)


from database import engine, SessionLocal, Base
from models import Measurement, Device, User, Client


from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

app = FastAPI()



SECRET_KEY = os.getenv("SECRET_KEY")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# 🔥 IMPORTANT : crée les tables automatiquement
Base.metadata.create_all(bind=engine)


class MeasurementSchema(BaseModel):
    point_id: int
    value: float
    timestamp: str

class DeviceCreate(BaseModel):
    name: str
    device_token: str
    client_id: int

class ClientCreate(BaseModel):
    name: str
    
class BatchRequest(BaseModel):
    device_token: str
    measurements: List[MeasurementSchema]


@app.post("/api/measurements/batch")
def receive_batch(batch: BatchRequest):
    db = SessionLocal()
    

    device = db.query(Device).filter(Device.device_token == batch.device_token).first()

    if not device:
        db.close()
        print("Device inconnu :", batch.device_token)
        return {"success": False, "error": "Invalid device token"}

    client_id = device.client_id

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


    hashed = hash_password("admin123")

    user = User(
        email="admin@test.com",
        hashed_password=hashed,
        client_id=1,
        role="admin"
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
        data={
            "sub": user.email,
            "client_id": user.client_id,
            "role": user.role
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    db.close()

    return {"access_token": access_token, "token_type": "bearer"}




def get_current_user(token: str = Depends(oauth2_scheme)):
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        user = {
            "email": payload.get("sub"),
            "client_id": payload.get("client_id"),
            "role": payload.get("role")
        }

        return user

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
def require_admin(user = Depends(get_current_user)):
    
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    return user

@app.post("/admin/create-client")
def create_client(data: ClientCreate, user=Depends(require_admin)):

    db = SessionLocal()

    existing = db.query(Client).filter(Client.name == data.name).first()

    if existing:
        db.close()
        raise HTTPException(status_code=400, detail="Client already exists")

    client = Client(
        name=data.name
    )

    db.add(client)
    db.commit()
    db.refresh(client)

    db.close()

    return {
        "message": "Client created",
        "client_id": client.id
    }

@app.get("/admin/test")
def admin_test(user = Depends(require_admin)):

    return {
        "message": "Admin access granted",
        "user": user
    }


@app.get("/admin/make-me-admin")
def make_me_admin():
    
    
    db = SessionLocal()

    user = db.query(User).filter(User.email == "admin@test.com").first()

    if not user:
        return {"error": "user not found"}

    user.role = "admin"
    db.commit()
    db.close()

    return {"message": "User is now admin"}


@app.post("/admin/create-device")
def create_device(data: DeviceCreate, user=Depends(require_admin)):

    db = SessionLocal()

    existing = db.query(Device).filter(Device.device_token == data.device_token).first()

    if existing:
        db.close()
        raise HTTPException(status_code=400, detail="Device already exists")

    device = Device(
        name=data.name,
        device_token=data.device_token,
        client_id=data.client_id
    )

    db.add(device)
    db.commit()
    db.refresh(device)

    db.close()

    return {
        "message": "Device created",
        "device_id": device.id
    }
  
    
@app.get("/admin/clients")
def list_clients(user=Depends(require_admin)):

    db = SessionLocal()

    clients = db.query(Client).all()

    result = []

    for c in clients:
        result.append({
            "id": c.id,
            "name": c.name,
            "created_at": c.created_at
        })

    db.close()

    return result

@app.get("/measurements")
def get_measurements(
    point_id: int,
    limit: int = 500,
    user=Depends(get_current_user)
):

    db = SessionLocal()

    measurements = db.query(Measurement).filter(
        Measurement.point_id == point_id,
        Measurement.client_id == user["client_id"]
    ).order_by(
        Measurement.timestamp.desc()
    ).limit(limit).all()

    result = []

    for m in measurements:
        result.append({
            "point_id": m.point_id,
            "value": m.value,
            "timestamp": m.timestamp
        })

    db.close()

    return result