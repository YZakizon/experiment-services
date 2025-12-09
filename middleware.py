from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from contextvars import ContextVar

import logging
import uuid

# Define the ContextVar to store the request ID
request_id_context: ContextVar[str] = ContextVar("request_id", default="N/A")

logger = logging.getLogger(__name__)

# --- Middleware Implementation ---

class RequestIDMiddleware(BaseHTTPMiddleware):
    @classmethod
    def request_id_context(cls):
        return request_id_context
    
    async def dispatch(self, request: Request, call_next):
        
        # Generate a unique ID (shortened for readability in logs)
        new_request_id = str(uuid.uuid4())[:8]
        
        # Store the token (ContextVar token) to be used for reset later
        token = request_id_context.set(new_request_id)
        
        # Log the start of the request, INCLUDING THE METHOD AND PATH
        http_method = request.method
        path_uri = request.url.path
        
        # logger.info("%s %s Request started", http_method, path_uri)
        
        try:
            # 1. Process the request normally
            response = await call_next(request)
            
            # Optional: Add the Request ID to the response header
            response.headers["X-Request-ID"] = new_request_id
            
        except Exception as e:
            # Log any exceptions with the context intact
            logger.exception("Unhandled error during request processing.")
            raise e
            
        finally:
            # 2. CRITICAL: Reset the context variable when the request is done
            # logger.info("%s %s Request finished", http_method, path_uri)
            request_id_context.reset(token)

        return response