import logging
import json
import os
import sys
from datetime import datetime
from pathlib import Path

class JSONResearchHandler:
    def __init__(self, json_file):
        self.json_file = json_file
        self.research_data = {
            "timestamp": datetime.now().isoformat(),
            "events": [],
            "content": {
                "query": "",
                "sources": [],
                "context": [],
                "report": "",
                "costs": 0.0
            }
        }

    def log_event(self, event_type: str, data: dict):
        self.research_data["events"].append({
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "data": data
        })
        self._save_json()

    def update_content(self, key: str, value):
        self.research_data["content"][key] = value
        self._save_json()

    def _save_json(self):
        with open(self.json_file, 'w', encoding='utf-8') as f:
            json.dump(self.research_data, f, indent=2, ensure_ascii=False)

def setup_research_logging():
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Generate timestamp for log files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create log file paths
    log_file = logs_dir / f"research_{timestamp}.log"
    json_file = logs_dir / f"research_{timestamp}.json"
    
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
    
    # Configure file handler for research logs with UTF-8 encoding
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    
    # Get research logger and configure it
    research_logger = logging.getLogger('research')
    research_logger.setLevel(logging.INFO)
    
    # Remove any existing handlers to avoid duplicates
    research_logger.handlers.clear()
    
    # Add file handler
    research_logger.addHandler(file_handler)
    
    # Add safe stream handler for console output
    console_handler = SafeStreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    research_logger.addHandler(console_handler)
    
    # Prevent propagation to root logger to avoid duplicate logs
    research_logger.propagate = False
    
    # Create JSON handler
    json_handler = JSONResearchHandler(json_file)
    
    return str(log_file), str(json_file), research_logger, json_handler

# Create a function to get the logger and JSON handler
def get_research_logger():
    return logging.getLogger('research')

def get_json_handler():
    return getattr(logging.getLogger('research'), 'json_handler', None)
