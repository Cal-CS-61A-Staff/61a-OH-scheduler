from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from . import paths

ENV_CLASS_NAME = "OH_SCHEDULER_CLASS_NAME"
ENV_CONFIG_PATH = "OH_SCHEDULER_CONFIG_PATH"


@dataclass(frozen=True)
class ConfigOption:
    class_name: str
    path: Path


def load_class_config_options(logger: Optional[logging.Logger] = None) -> list[ConfigOption]:
    """Collect available class configs from the configs directory."""
    options: list[ConfigOption] = []
    for config_path in sorted(paths.CONFIG_DIR.glob("*.json")):
        try:
            with config_path.open("r", encoding="utf-8") as config_file:
                raw_config = json.load(config_file)
        except (OSError, json.JSONDecodeError) as exc:
            if logger:
                logger.warning("Skipping config %s due to read error: %s", config_path.name, exc)
            continue

        class_name = raw_config.get("class")
        if not class_name:
            if logger:
                logger.warning("Skipping config %s because it lacks a 'class' attribute.", config_path.name)
            continue

        options.append(ConfigOption(class_name=str(class_name), path=config_path))

    options.sort(key=lambda option: (option.class_name.lower(), option.path.name.lower()))
    return options


def find_option_by_class(options: Iterable[ConfigOption], class_name: str) -> Optional[ConfigOption]:
    """Return the first config option whose class name matches the provided value."""
    class_lower = class_name.lower()
    for option in options:
        if option.class_name.lower() == class_lower:
            return option
    return None


def resolve_config_path(candidate: str | Path) -> Optional[Path]:
    """Resolve a config path relative to the repository root and ensure it exists."""
    path = Path(candidate)
    if not path.is_absolute():
        path = (paths.ROOT_DIR / path).resolve()
    if path.exists():
        return path
    return None
