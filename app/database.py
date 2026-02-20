import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import URL
from dotenv import load_dotenv 
load_dotenv()
url_object = URL.create(
    "postgresql",
    username=os.getenv("POSTGREUSER"),
    password=os.getenv("POSTGREPASSWORD"),
    host=os.getenv("POSTGRESHOST"),
    port=5432,
    database=os.getenv("POSTGREDB")
)

engine = create_engine(url_object,echo=True)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
