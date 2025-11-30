import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class SignalHandler:
    def __init__(self, command_file: str = "signals/command.txt", status_file: str = "signals/status.json"):
        self.command_file = Path(command_file)
        self.status_file = Path(status_file)
        
        # Ensure directories exist
        self.command_file.parent.mkdir(parents=True, exist_ok=True)
        self.status_file.parent.mkdir(parents=True, exist_ok=True)

    def check_signal(self) -> Optional[str]:
        if self.command_file.exists():
            try:
                cmd = self.command_file.read_text().strip().upper()
                if cmd:
                    logger.info(f"Received signal: {cmd}")
                    # Clear command file after processing
                    self.command_file.write_text("")
                    return cmd
            except Exception as e:
                logger.error(f"Error reading signal: {e}")
        return None

    def update_status(self, status: str, extra_data: dict = None):
        data = {
            "status": status,
            "timestamp": None # Should be added by caller or here
        }
        if extra_data:
            data.update(extra_data)
            
        try:
            with open(self.status_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Error writing status: {e}")

    def send_signal(self, signal: str):
        """Used by the client (Streamlit) to send a signal."""
        try:
            self.command_file.write_text(signal)
            logger.info(f"Sent signal: {signal}")
        except Exception as e:
            logger.error(f"Error sending signal: {e}")
