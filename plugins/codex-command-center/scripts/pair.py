#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from client import CommandCenterClient  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pair Codex Command Center with a browser workspace.",
    )
    parser.add_argument("code", help="One-time code shown by Pair Codex")
    parser.add_argument(
        "--url", default=os.getenv("COMMAND_CENTER_URL", "http://127.0.0.1:8000"),
        help="Command Center base URL",
    )
    args = parser.parse_args()
    os.environ["COMMAND_CENTER_URL"] = args.url
    os.environ["COMMAND_CENTER_PAIR_CODE"] = args.code
    client = CommandCenterClient()
    client.login()
    print("Paired Codex Command Center. The revocable token is stored with user-only permissions.")
    print("Next: run scripts/architecture.py lint . and explicitly sync when ready.")


if __name__ == "__main__":
    main()
