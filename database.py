from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from urllib.parse import quote_plus

PASSWORD = quote_plus("!THI@fou66*")

DATABASE_URL = f"postgresql://postgres:{PASSWORD}@localhost:5432/energy_cloud"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()