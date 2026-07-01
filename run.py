"""Entry point: python run.py  (serves API + UI at http://127.0.0.1:8000)."""
import os
from pathlib import Path

import uvicorn


def _load_dotenv() -> None:
    """Load KEY=VALUE lines from a local, gitignored ``.env`` into the environment.

    Keeps secrets (e.g. ``OPENROUTER_API_KEY`` for the optional LLM narrator) out
    of the source and out of the repo. Existing environment variables win.
    """
    env = Path(__file__).with_name(".env")
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


if __name__ == "__main__":
    _load_dotenv()
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
