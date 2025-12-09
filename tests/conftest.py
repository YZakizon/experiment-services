import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from data.database import Base, get_db, Experiment, Event
from main import app  # import your FastAPI app
from services.cache import get_mock_cache_client
from config import config
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# In-memory SQLite for tests
# SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
config.valid_tokens = ["fake-client-token"]
# config.database_url = SQLALCHEMY_DATABASE_URL

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables once
Base.metadata.create_all(bind=engine)

# Dependency override for DB
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Override client auth
def override_get_current_client():
    return "fake-client-token"

# app.dependency_overrides["get_current_client"] = override_get_current_client


def override_get_cache_client():
    return get_mock_cache_client()

app.dependency_overrides["get_cache_client"] = override_get_cache_client

@pytest.fixture(autouse=True, scope="session")
def setup_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
