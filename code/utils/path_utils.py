from pathlib import Path
from typing import Union


def ensure_dir(path: Union[str, Path]) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_project_root(ref_file: str = __file__, levels_up: int = 2) -> Path:
    return Path(ref_file).resolve().parents[levels_up]


def get_latest_by_glob(glob_pattern: str):
    from glob import glob
    files = sorted(glob(glob_pattern))
    return files[-1] if files else None


def build_session_filename(prefix: str, room: str, session_ts: str, ext: str) -> str:
    room = room or "unknown_room"
    return f"{prefix}_{room}_{session_ts}.{ext.lstrip('.')}"