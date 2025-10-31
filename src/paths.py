from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "configs"
ARTIFACT_DIR = ROOT_DIR / ".artifacts"
NPY_DIR = ARTIFACT_DIR / "numpy"
PICKLE_DIR = ARTIFACT_DIR / "pickles"
CREDS_DIR = ROOT_DIR / "credentials"
LOG_DIR = ARTIFACT_DIR / "logs"


def ensure_directories() -> None:
    """Ensure runtime directories exist before reading or writing artifacts."""
    ARTIFACT_DIR.mkdir(exist_ok=True, parents=True)
    NPY_DIR.mkdir(exist_ok=True, parents=True)
    PICKLE_DIR.mkdir(exist_ok=True, parents=True)
    CREDS_DIR.mkdir(exist_ok=True, parents=True)
    LOG_DIR.mkdir(exist_ok=True, parents=True)
