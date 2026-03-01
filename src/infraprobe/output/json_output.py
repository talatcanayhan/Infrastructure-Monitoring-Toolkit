"""JSON output formatter for InfraProbe.

Provides machine-readable JSON output for all commands,
enabling piping to jq, scripts, and other tools.
"""

import json
from dataclasses import asdict, is_dataclass
from typing import Any

from rich.console import Console

console = Console()


def _serialize(obj: Any) -> Any:
    """Recursively convert dataclasses and special types to dicts."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(item) for item in obj]
    return obj


def print_json(data: Any) -> None:
    """Print data as formatted JSON to stdout."""
    serialized = _serialize(data)
    console.print_json(json.dumps(serialized, default=str))
