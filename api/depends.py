from fastapi import Depends
from services.cache import get_cache_client
from auth.security import get_current_client # Assuming this is your auth dependency
from data.database import get_db

# --- DEPENDENCY INJECTION SETUP ---
# Dependencies must be defined here or imported from the main app's dependencies
CLIENT_AUTH = Depends(get_current_client)
DB_DEPENDENCY = Depends(get_db) # Assumed to be imported from data.database
CACHE_CLIENT = Depends(get_cache_client) # Assumed to be imported from services.cache
