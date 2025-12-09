import os
import log
from dotenv import load_dotenv

# Load .env file into environment
load_dotenv()


class Config:
    def __init__(self):
        self.valkey_host = os.getenv("VALKEY_HOST", "127.0.0.1")
        self.valkey_port = int(os.getenv("VALKEY_PORT", 6379))
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./experimentation.db")
        self.log_level = os.getenv("LOG_LEVEL", default="INFO")
        self.valid_tokens = os.getenv("VALID_TOKENS", [])
        
        # Call setup_logging when the application starts
        log.setup_logging(self.log_level)

    def __repr__(self):
        return f"<Settings host={self.valkey_host} port={self.valkey_port}>"
    
config = Config()

