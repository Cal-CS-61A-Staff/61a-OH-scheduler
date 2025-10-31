#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys

from src import paths
from src.config_utils import (
    ENV_CLASS_NAME,
    ENV_CONFIG_PATH,
    find_option_by_class,
    load_class_config_options,
)


def run_scheduler(class_name: str | None) -> None:
    """Launch the scheduler with an optional preselected class configuration."""
    env = os.environ.copy()
    options = load_class_config_options(None)

    if class_name:
        matched = find_option_by_class(options, class_name)
        if matched:
            env[ENV_CLASS_NAME] = matched.class_name
            print(
                f"Launching scheduler for class '{matched.class_name}' "
                f"using config '{matched.path.name}'."
            )
        else:
            print(
                f"No config found for class '{class_name}'. "
                "Continuing with manual selection."
            )
    else:
        default_config = paths.CONFIG_DIR / "config.json"
        if default_config.exists():
            env[ENV_CONFIG_PATH] = str(default_config)
            default_option = next(
                (option for option in options if option.path == default_config), None
            )
            if default_option:
                env[ENV_CLASS_NAME] = default_option.class_name
                print(
                    f"Launching scheduler for default class '{default_option.class_name}' "
                    f"using config '{default_option.path.name}'."
                )

    subprocess.run(
        [sys.executable, "-m", "src.runner"],
        check=True,
        env=env,
        cwd=paths.ROOT_DIR,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch the Office Hours Scheduler.",
    )
    parser.add_argument(
        "-c",
        "-class",
        dest="class_name",
        help="Class name to schedule (matches the 'class' field in configs).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv or sys.argv[1:])
    run_scheduler(args.class_name)


if __name__ == "__main__":
    main()
