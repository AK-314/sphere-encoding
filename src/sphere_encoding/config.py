"""Deterministic JSON configuration loading and serialisation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when configuration content is invalid or ambiguous."""


def _reject_duplicate_object(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}

    for key, value in pairs:
        if key in result:
            raise ConfigError(f"duplicate JSON key: {key!r}")
        result[key] = value

    return result


def _reject_non_finite_constant(value: str) -> None:
    raise ConfigError(f"non-finite JSON number is forbidden: {value}")


def canonical_json_dumps(value: Any) -> str:
    """Serialise JSON deterministically in compact canonical form."""
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise ConfigError(
            f"value is not valid deterministic JSON: {exc}"
        ) from exc


def pretty_json_dumps(value: Any) -> str:
    """Serialise JSON deterministically for human-readable files."""
    try:
        return (
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
    except (TypeError, ValueError) as exc:
        raise ConfigError(
            f"value is not valid deterministic JSON: {exc}"
        ) from exc


def load_json_config(file_path: str | Path) -> dict[str, Any]:
    """Load a UTF-8 JSON object and reject ambiguous JSON constructs."""
    source = Path(file_path)

    try:
        value = json.loads(
            source.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_object,
            parse_constant=_reject_non_finite_constant,
        )
    except ConfigError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigError(
            f"could not load JSON configuration {source}: {exc}"
        ) from exc

    if not isinstance(value, dict):
        raise ConfigError(
            "top-level JSON configuration must be an object"
        )

    return value


def config_sha256(config: Mapping[str, Any]) -> str:
    """Hash a configuration independently of insertion order."""
    serialised = canonical_json_dumps(dict(config)).encode("utf-8")
    return hashlib.sha256(serialised).hexdigest()
