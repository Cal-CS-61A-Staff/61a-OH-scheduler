#!/usr/bin/env python3
"""
Bootstrap script for the OH Scheduler project.

Creates a virtual environment in .venv/ and installs the pinned dependencies
from configs/requirements.txt. Run this after cloning the repo:

    python setup_env.py
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
REQUIREMENTS = ROOT / "configs" / "requirements.txt"


def run(cmd: list[str]) -> None:
    """Run a command, displaying it first for transparency."""
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def ensure_venv(python: str) -> Path:
    """Create the virtual environment if it does not exist."""
    if (VENV_DIR / "pyvenv.cfg").exists():
        print(f"Virtual environment already present at {VENV_DIR}")
    else:
        print(f"Creating virtual environment at {VENV_DIR}...")
        run([python, "-m", "venv", str(VENV_DIR)])
    return VENV_DIR


def pip_executable(venv_path: Path) -> Path:
    """Return the path to the pip executable inside the venv."""
    if sys.platform == "win32":
        return venv_path / "Scripts" / "pip.exe"
    return venv_path / "bin" / "pip"


def main() -> None:
    parser = argparse.ArgumentParser(description="Set up the OH Scheduler development environment.")
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python interpreter to use when creating the virtual environment (default: current interpreter).",
    )
    args = parser.parse_args()

    if not REQUIREMENTS.exists():
        raise SystemExit(f"Missing dependency file: {REQUIREMENTS}")

    venv_path = ensure_venv(args.python)
    pip_path = pip_executable(venv_path)

    print("Upgrading pip/setuptools...")
    run([str(pip_path), "install", "--upgrade", "pip", "setuptools"])

    print(f"Installing dependencies from {REQUIREMENTS}...")
    run([str(pip_path), "install", "-r", str(REQUIREMENTS)])

    activation_hint = (
        f"source {venv_path / 'bin' / 'activate'}"
        if sys.platform != "win32"
        else f"{venv_path}\\Scripts\\activate"
    )
    print("\nSetup complete!")
    print(f"Activate the environment with:\n  {activation_hint}\n")
    print("Then run the scheduler via:\n  python schedule.py")


if __name__ == "__main__":
    main()
