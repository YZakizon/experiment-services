import json
import logging
import os
from typing import List, Any
# Import the actual ORM classes for reconstruction. In a real app, 
# you would decide whether to cache ORM objects or Pydantic schemas here.
from data.database import Variant, Experiment, Assignment
from config import config

logger = logging.getLogger(__name__)

# --- Configuration Constants ---
EXPERIMENT_CACHE_TTL = 60 # 1 hour for experiment details
ASSIGNMENT_CACHE_TTL = 60    # 1 minute for user assignments

# --- Valkey/Redis Backend Implementations ---

class _MockValkeyBackend:
    """Simulates the low-level Valkey/Redis client (in-memory)."""
    def __init__(self):
        self._cache = {}
    
    def get(self, key: str) -> str | None:
        logger.debug("cache mock get: %s", key)
        return self._cache.get(key)
        
    def set(self, key: str, value: str, ex: int):
        # In a real setup, 'ex' handles expiration. Here, we just store.
        logger.debug("cache mock set: %s, value: %s", key, value)
        self._cache[key] = value

class RealValkeyBackend:
    """Real implementation using redis-py client (compatible with Valkey)."""
    def __init__(self, host: str, port: int, db: int = 0, password: str | None = None):
        try:
            import redis
        except ImportError:
            logger.error("Redis module not found. Install it with `pip install redis`.")
            raise

        try:
            self.client = redis.Redis(
                host=host, 
                port=port, 
                db=db, 
                password=password, 
                decode_responses=True,
                socket_timeout=2.0
            )
            self.client.ping()
        except Exception as e:
            logger.error("Failed to connect to Valkey/Redis: %s", e)
            raise

    def get(self, key: str) -> str | None:
        try:
            logger.debug("cache valkey get: %s", key)
            return self.client.get(key)
        except Exception as e:
            logger.error("Valkey GET error for key %s: %s", key, e)
            return None

    def set(self, key: str, value: str, ex: int):
        try:
            logger.debug("cache valkey set: %s, value: %s", key, value)
            self.client.set(key, value, ex=ex)
        except Exception as e:
            logger.error("Valkey SET error for key %s: %s", key, e)



# --- Dedicated Cache Client Class ---

class CacheClient:
    """High-level client for managing application cache operations."""

    def __init__(self, backend):
        self.backend = backend
        logger.debug("CacheClient backend: %s", self.backend)

    # --- Experiment Caching ---

    def get_experiment(self, experiment_id: int) -> Experiment | None:
        key = f"exp:{experiment_id}"
        json_str = self.backend.get(key)
        if json_str:
            logger.debug("cache get experiment id: %d: key: %s, json_str: %s", experiment_id, key, json_str)
            experiment = Experiment.from_json(json_str=json_str)
            logger.debug("cache get experiment id: %d: experiment obj: %s", experiment_id, experiment.to_json())
            return experiment
        
        return None

    def set_experiment(self, experiment: Experiment):
        key = f"exp:{experiment.id}"
        json_str = experiment.to_json(exclude_relationships_key=["assignments"])
        if json_str:
            logger.debug("cache set experiment id: %d: key: %s, json_str: %s", experiment.id, key, json_str)
            self.backend.set(key, json_str, ex=EXPERIMENT_CACHE_TTL)
            logger.debug("Experiment %d cached.", experiment.id)

        return None

    # --- Assignment Caching ---

    def get_assignment(self, experiment_id: int, user_id: str) -> Assignment | None:
        key = f"asn:{experiment_id}:{user_id}"
        json_str = self.backend.get(key)
        if json_str:
            return Assignment.from_json(json_str=json_str)
        
        return None

    def set_assignment(self, assignment: Assignment):
        key = f"asn:{assignment.experiment_id}:{assignment.user_id}"
        json_str = assignment.to_json()
        if json_str:
            self.backend.set(key, json_str, ex=ASSIGNMENT_CACHE_TTL)
            logger.debug("Assignment for user %s (EID %d) cached.", 
                         assignment.user_id, assignment.experiment_id)
            
        return None

# --- Initialize Backend and Default Client ---
valkey_host = config.valkey_host
valkey_port = config.valkey_port

logger.info("valkey_host: %s, port: %d", valkey_host, valkey_port)

if valkey_host:
    try:
        VALKEY_BACKEND = RealValkeyBackend(host=valkey_host, port=valkey_port)
    except Exception:
        logger.info("Falling back to Mock Valkey Backend due to connection failure.")
        VALKEY_BACKEND = _MockValkeyBackend()
else:
    logger.info("VALKEY_HOST not set. Using Mock Valkey Backend.")
    VALKEY_BACKEND = _MockValkeyBackend()

# Initialize a default client (singleton)
_DEFAULT_CACHE_CLIENT = CacheClient(backend=VALKEY_BACKEND)

def get_cache_client():
    return _DEFAULT_CACHE_CLIENT

def get_mock_cache_client():
    return CacheClient(backend=_MockValkeyBackend())