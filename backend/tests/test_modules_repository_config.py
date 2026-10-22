# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""backend/modules/repository.json - the module's limits (validated on load)."""

import json

import pytest
from pydantic import ValidationError

from app.modules.repository import config
from app.modules.repository.config import RepositoryConfig, load_config


def test_the_committed_file_is_valid():
    loaded = load_config(config.CONFIG_FILE)

    assert loaded.max_repositories_per_user >= 1
    assert loaded.max_image_bytes <= loaded.max_image_bytes_per_user


def test_the_committed_file_sets_every_limit_explicitly():
    committed = json.loads(config.CONFIG_FILE.read_text(encoding="utf-8"))

    assert set(committed) == set(RepositoryConfig.model_fields)


def test_a_missing_file_means_the_defaults(tmp_path, caplog):
    loaded = load_config(tmp_path / "missing.json")

    assert loaded == RepositoryConfig()
    assert "using the default limits" in caplog.text


def test_unknown_keys_are_refused(tmp_path):
    path = tmp_path / "repository.json"
    path.write_text(json.dumps({"max_repositores_per_user": 5}), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_config(path)


@pytest.mark.parametrize(
    "bad",
    [
        {"max_repositories_per_user": 0},
        {"max_tables_per_repository": "many"},
        {"max_attributes_per_table": 0},
        {"max_records_per_table": -1},
        {"max_image_bytes": 10},
        {"max_image_bytes": 5 * 1024 * 1024, "max_image_bytes_per_user": 1024 * 1024},
        {"unattached_image_hours": 0},
    ],
)
def test_invalid_values_are_refused(tmp_path, bad):
    path = tmp_path / "repository.json"
    path.write_text(json.dumps(bad), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_config(path)


def test_the_limits_dependency_reads_the_file_once():
    config.get_limits.cache_clear()

    assert config.get_limits() is config.get_limits()
