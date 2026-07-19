#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import architecture  # noqa: E402
from client import CommandCenterClient  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Check service and architecture health.")
    parser.add_argument("repository", nargs="?", default=".")
    args = parser.parse_args()
    client = CommandCenterClient()
    status = client.request("GET", "/api/v1/status")
    architecture_status: dict = {
        "degraded": True,
        "degraded_reasons": ["architecture_manifest_missing"],
    }
    try:
        payload = architecture.inventory(Path(args.repository))
        architecture_status = architecture.status(client, payload)
    except FileNotFoundError:
        pass
    print(json.dumps({
        "ok": True,
        "service": client.base,
        "authenticated": True,
        "memories": status.get("memories", 0),
        "documents": status.get("documents", 0),
        "degraded": status.get("degraded", False),
        "architecture": architecture_status,
    }, indent=2))


if __name__ == "__main__":
    main()
