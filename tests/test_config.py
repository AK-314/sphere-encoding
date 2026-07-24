from __future__ import annotations

import json

import pytest

from sphere_encoding.config import (
    ConfigError,
    canonical_json_dumps,
    config_sha256,
    load_json_config,
    pretty_json_dumps,
)


def test_canonical_json_dumps_sorts_keys_recursively() -> None:
    value = {"z": 1, "a": {"y": 2, "b": 3}}

    assert canonical_json_dumps(value) == (
        '{"a":{"b":3,"y":2},"z":1}'
    )


def test_pretty_json_dumps_is_sorted_and_newline_terminated() -> None:
    text = pretty_json_dumps({"z": 1, "a": 2})

    assert text == '{\n  "a": 2,\n  "z": 1\n}\n'


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), float("-inf")],
)
def test_canonical_json_rejects_non_finite_numbers(
    value: float,
) -> None:
    with pytest.raises(ConfigError, match="deterministic JSON"):
        canonical_json_dumps({"value": value})


def test_load_json_config_reads_utf8_object(tmp_path) -> None:
    file_path = tmp_path / "config.json"
    file_path.write_text(
        '{"label": "σφαῖρα", "seed": 0}',
        encoding="utf-8",
    )

    assert load_json_config(file_path) == {
        "label": "σφαῖρα",
        "seed": 0,
    }


def test_load_json_config_rejects_duplicate_keys(tmp_path) -> None:
    file_path = tmp_path / "config.json"
    file_path.write_text(
        '{"seed": 0, "seed": 1}',
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="duplicate JSON key"):
        load_json_config(file_path)


def test_load_json_config_rejects_non_object_root(tmp_path) -> None:
    file_path = tmp_path / "config.json"
    file_path.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(ConfigError, match="top-level"):
        load_json_config(file_path)


def test_load_json_config_rejects_non_finite_number(
    tmp_path,
) -> None:
    file_path = tmp_path / "config.json"
    file_path.write_text('{"value": NaN}', encoding="utf-8")

    with pytest.raises(ConfigError, match="non-finite"):
        load_json_config(file_path)


def test_config_sha256_is_independent_of_insertion_order() -> None:
    first = {
        "alpha": 1,
        "beta": {"x": 2, "y": 3},
    }
    second = json.loads(
        '{"beta": {"y": 3, "x": 2}, "alpha": 1}'
    )

    assert config_sha256(first) == config_sha256(second)
