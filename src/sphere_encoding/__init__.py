"""Infrastructure for reproducible sphere-encoding experiments."""

from sphere_encoding.config import (
    ConfigError,
    canonical_json_dumps,
    config_sha256,
    load_json_config,
    pretty_json_dumps,
)
from sphere_encoding.hashing import sha256_bytes, sha256_file
from sphere_encoding.provenance import (
    ProvenanceError,
    atomic_write_bytes,
    atomic_write_text,
    build_manifest,
    capture_environment,
    capture_repository,
    repository_is_clean,
    write_manifest,
)

__all__ = [
    "ConfigError",
    "ProvenanceError",
    "atomic_write_bytes",
    "atomic_write_text",
    "build_manifest",
    "canonical_json_dumps",
    "capture_environment",
    "capture_repository",
    "config_sha256",
    "load_json_config",
    "pretty_json_dumps",
    "repository_is_clean",
    "sha256_bytes",
    "sha256_file",
    "write_manifest",
]

__version__ = "0.1.0"
