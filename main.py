from dotenv import load_dotenv
import logging
from pathlib import Path

# Create logs directory if it doesn't exist
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Configure logging with UTF-8 encoding to handle Unicode characters
import sys

# Create a safe stream handler that handles Unicode encoding errors
class SafeStreamHandler(logging.StreamHandler):
    """Stream handler that safely handles Unicode encoding errors cross-platform (Windows, Linux, macOS)."""
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            # Try to write with UTF-8, fallback to error handling if needed
            try:
                if hasattr(stream, 'buffer'):
                    # For stdout/stderr, use buffer with UTF-8
                    stream.buffer.write(msg.encode('utf-8', errors='replace'))
                    stream.buffer.write(self.terminator.encode('utf-8'))
                    stream.buffer.flush()
                else:
                    stream.write(msg)
                    stream.write(self.terminator)
                    stream.flush()
            except (UnicodeEncodeError, AttributeError):
                # Fallback: replace problematic characters
                safe_msg = msg.encode('ascii', errors='replace').decode('ascii')
                stream.write(safe_msg)
                stream.write(self.terminator)
                stream.flush()
        except Exception:
            self.handleError(record)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # File handler for general application logs with UTF-8 encoding
        logging.FileHandler('logs/app.log', encoding='utf-8'),
        # Safe stream handler for console output
        SafeStreamHandler(sys.stdout)
    ]
)

# Suppress verbose fontTools logging
logging.getLogger('fontTools').setLevel(logging.WARNING)
logging.getLogger('fontTools.subset').setLevel(logging.WARNING)
logging.getLogger('fontTools.ttLib').setLevel(logging.WARNING)

# Create logger instance
logger = logging.getLogger(__name__)

load_dotenv()

from backend.server.server import app

if __name__ == "__main__":
    import uvicorn
    import os
    
    # Get server host and port from environment variables, with defaults
    # Use SERVER_HOST and SERVER_PORT to avoid conflict with database HOST/PORT
    host = os.getenv("SERVER_HOST", os.getenv("HOST", "0.0.0.0"))
    port = int(os.getenv("SERVER_PORT", os.getenv("PORT", 8000)))
    
    logger.info(f"Starting server on {host}:{port} with 1 worker...")
    uvicorn.run(
        "backend.server.server:app",
        host=host,
        port=port,
        log_level="info",
        workers=1,
        proxy_headers=True,
        forwarded_allow_ips="*"
    )
