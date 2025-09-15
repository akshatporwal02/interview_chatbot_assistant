import os
from pathlib import Path
from typing import Optional


def _repo_root_from_utils() -> Path:
    # utils -> code -> repo root
    return Path(__file__).resolve().parents[2]


def load_dotenv(env_path: Optional[Path] = None) -> None:
    """Minimal .env loader to avoid external dependency.
    Supports simple KEY=VALUE lines, ignores comments and blanks.
    Does not override existing environment variables.
    """
    path = env_path or (_repo_root_from_utils() / ".env")
    if not path.exists():
        return
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if "=" not in s:
                continue
            k, v = s.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            # Do not override existing env
            os.environ.setdefault(k, v)
    except Exception:
        # Fail-safe: never crash app due to .env parse
        pass


def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.environ.get(name, default)


def get_daily_api_key() -> Optional[str]:
    return get_env("DAILY_API_KEY")

def get_openai_api_key() -> Optional[str]:
    return get_env("OPENAI_API_KEY")    

# Email configuration helpers
def get_email_sender() -> Optional[str]:
    return get_env("EMAIL_SENDER")

def get_email_app_password() -> Optional[str]:
    return get_env("EMAIL_APP_PASSWORD")

def get_email_default_receiver() -> Optional[str]:
    return get_env("EMAIL_RECEIVER")