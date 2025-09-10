import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, TextIO

# Preserve original streams so they can be restored if needed
_original_stdout = sys.stdout
_original_stderr = sys.stderr

class Tee:
    """A stream that writes to two underlying streams (e.g., console and file)."""
    def __init__(self, stream_a: TextIO, stream_b: TextIO):
        self.a = stream_a
        self.b = stream_b
        # Propagate encoding for libraries that probe this attribute
        self.encoding = getattr(stream_a, "encoding", "utf-8")

    def write(self, data: str) -> int:
        self.a.write(data)
        self.b.write(data)
        return len(data)

    def flush(self) -> None:
        try:
            self.a.flush()
        finally:
            self.b.flush()

    def isatty(self) -> bool:
        # We are not a real TTY; helps some libraries avoid ANSI control assumptions
        return False


def init_terminal_logging(room_name: Optional[str] = None, log_dir: Optional[Path] = None) -> Path:
    """
    Initialize terminal logging to a file while preserving console output.

    - Creates code/session_data/terminal_logs if not provided.
    - File name format: terminal_log_{room}_{YYYY-MM-DD_HH-MM-SS}.log
    - Redirects sys.stdout and sys.stderr to a Tee of (console, file).

    Returns the created log file path.
    """
    if log_dir is None:
        # __file__ is code/utils/terminal_log.py → parents[1] is the 'code' directory
        project_code_dir = Path(__file__).resolve().parents[1]
        log_dir = project_code_dir / "session_data" / "terminal_logs"
   
    log_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_room = (room_name or "session").replace(" ", "_")
    log_path = log_dir / f"terminal_log_{safe_room}_{ts}.log"

    # Line-buffered text file for prompt flushing
    file_handle = open(log_path, "w", encoding="utf-8", buffering=1)

    # Create tee streams so output is visible in console and written to file
    sys.stdout = Tee(_original_stdout, file_handle)
    sys.stderr = Tee(_original_stderr, file_handle)

    return log_path


def stop_terminal_logging() -> None:
    """Restore original stdout/stderr streams."""
    sys.stdout = _original_stdout
    sys.stderr = _original_stderr