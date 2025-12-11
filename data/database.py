from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, UniqueConstraint, Index
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from sqlalchemy.orm import class_mapper 
from datetime import datetime, timezone
from config import config
import sqlite3
import json
import logging

logger = logging.getLogger(__name__)

# --- Database Setup ---

# Use SQLite for simplicity as requested "sqlite:///./experimentation.db"
# To use Postgres postgresql://user:password@host:port/dbname'
SQLALCHEMY_DATABASE_URL =  config.database_url 

logger.info("SQLALCHEMY_DATABASE_URL: %s", SQLALCHEMY_DATABASE_URL)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Dependency to yield a new database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Serializer Mixin ---
class SerializerMixin:
    """Helper class to serialize/deserialize ORM object into JSON string"""

    def to_dict(self, include_relationships=True, exclude_relationships_key: list=list()):
        """
        Convert ORM object to dictionary, handling datetime and relationships.
        When include relationships is true, this will include data on different table
        make sure use exclude relationships key to prevent bloated result.
        """
        result = {}
        # Handle columns
        for c in self.__table__.columns:
            value = getattr(self, c.name)
            if isinstance(value, datetime):
                result[c.name] = value.isoformat()
            else:
                result[c.name] = value

        # Handle relationships
        if include_relationships:
            for rel in self.__mapper__.relationships:
                
                if exclude_relationships_key and rel.key in exclude_relationships_key:
                    continue

                value = getattr(self, rel.key)
                if value is None:
                    result[rel.key] = None
                elif isinstance(value, list):  # one-to-many
                    result[rel.key] = [v.to_dict(include_relationships=False) for v in value]
                else:  # many-to-one or one-to-one
                    result[rel.key] = value.to_dict(include_relationships=False)

        return result

    def to_json(self, include_relationships=True, exclude_relationships_key: list=list()):
        return json.dumps(self.to_dict(include_relationships=include_relationships, exclude_relationships_key=exclude_relationships_key))

    @classmethod
    def from_dict(cls, data, include_relationship=True):
        """Create ORM object from dictionary (relationships skipped for simplicity)."""
        fields = {}
        for c in cls.__table__.columns:
            if c.name in data:
                if isinstance(c.type, DateTime) and isinstance(data[c.name], str):
                    fields[c.name] = datetime.fromisoformat(data[c.name])
                else:
                    fields[c.name] = data[c.name]

        # 2. Process Relationships (Nested fields)
        if include_relationship:
            mapper = class_mapper(cls)
            for rel in mapper.relationships:
                rel_key = rel.key
                if rel_key in data and data[rel_key] is not None:
                    
                    # Get the target ORM class for the relationship
                    target_cls = rel.entity.class_

                    if isinstance(data[rel_key], list): 
                        # One-to-many: Convert list of dictionaries to list of target ORM objects
                        fields[rel_key] = [
                            target_cls.from_dict(item_data, include_relationship=True)
                            for item_data in data[rel_key]
                        ]
                    elif isinstance(data[rel_key], dict):
                        # Many-to-one or One-to-one: Convert dictionary to a single target ORM object
                        fields[rel_key] = target_cls.from_dict(data[rel_key], include_relationship=True)

        return cls(**fields)

    @classmethod
    def from_json(cls, json_str, include_relationship=True):
        data = json.loads(json_str)
        return cls.from_dict(data, include_relationship)
    
# --- SQLAlchemy Models ---
class Experiment(Base, SerializerMixin):
    __tablename__ = "experiments"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    variants = relationship("Variant", back_populates="experiment")
    assignments = relationship("Assignment", back_populates="experiment")

class Variant(Base, SerializerMixin):
    __tablename__ = "variants"
    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"))
    name = Column(String)
    allocation_percent = Column(Float)
    
    experiment = relationship("Experiment", back_populates="variants")

class Assignment(Base, SerializerMixin):
    __tablename__ = "assignments"
    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"))
    user_id = Column(String, index=True)
    variant_name = Column(String) # Stored redundantly for simpler queries
    assigned_at = Column(DateTime, default=datetime.now(timezone.utc))
    
    experiment = relationship("Experiment", back_populates="assignments")
    
    # Ensures a user is assigned only once per experiment (Idempotency check)
    # This will also create auto index
    __table_args__ = (UniqueConstraint('experiment_id', 'user_id', name='_exp_user_uc'),)

class Event(Base, SerializerMixin):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    type = Column(String, index=True) # e.g., 'purchase'
    timestamp = Column(DateTime, default=datetime.now(timezone.utc), index=True)
    # Stored as text/JSON or use a JSON type if supported by the final DB
    properties_json = Column(Text, nullable=True) 

    # Composite Index for Analytics (user, event type, and time range lookups)
    # This Index is correctly defined as requested: user_id, type, then timestamp
    __table_args__ = (
        Index('idx_user_type_ts', 'user_id', 'type', 'timestamp'),
    )

# Function to create tables
def create_tables():
    try:
        Base.metadata.create_all(bind=engine)
    except sqlite3.OperationalError as e:
        # Supress table exists error on sqlite3
        if e.sqlite_errorname != "table experiments already exists":
            raise e