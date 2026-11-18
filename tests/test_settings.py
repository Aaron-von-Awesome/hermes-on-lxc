import pytest

import settings


def test_key_env_for():
    assert (
        settings.key_env_for("http://172.24.1.121:8080/v1")
        == "HERMES_CUSTOM_172_24_1_121_8080_API_KEY"
    )
    assert (
        settings.key_env_for("https://llm.example/v1")
        == "HERMES_CUSTOM_LLM_EXAMPLE_API_KEY"
    )
    assert (
        settings.key_env_for("http://u:p@172.24.1.121:8080/v1")
        == "HERMES_CUSTOM_172_24_1_121_8080_API_KEY"
    )
    assert settings.key_env_for("") == "HERMES_CUSTOM_API_KEY"


def test_load_variant(tmp_path):
    (tmp_path / "lab.py").write_text(
        'CONTAINER = "lab"\nBASE_URL = "http://h:1/v1"\n_private = 1\n'
    )
    v = settings.load_variant("lab", tmp_path)
    assert v == {
        "CONTAINER": "lab",
        "BASE_URL": "http://h:1/v1",
        "KEY_ENV": "HERMES_CUSTOM_H_1_API_KEY",
    }


def test_load_variant_unset_lists_variants(tmp_path):
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.py").write_text("")
    for name in (None, "", "missing"):
        with pytest.raises(RuntimeError, match="a, b"):
            settings.load_variant(name, tmp_path)


def test_load_variant_rejects_path(tmp_path):
    with pytest.raises(RuntimeError):
        settings.load_variant("../settings", tmp_path)


def test_hermius_maximus_values():
    assert settings.CONTAINER == "hermius-maximus"
    assert settings.DASHBOARD_PORT == 9119
    assert settings.KEY_ENV == "HERMES_CUSTOM_172_24_1_121_8080_API_KEY"


@pytest.mark.parametrize(
    "other",
    [
        'CONTAINER = "lab"\nDASHBOARD_PORT = 9120\n',
        'CONTAINER = "other"\nDASHBOARD_PORT = 9119\n',
    ],
)
def test_load_variant_rejects_duplicate(tmp_path, other):
    (tmp_path / "lab.py").write_text('CONTAINER = "lab"\nDASHBOARD_PORT = 9119\n')
    (tmp_path / "old.py").write_text(other)
    with pytest.raises(RuntimeError, match="old.py"):
        settings.load_variant("lab", tmp_path)


def test_load_variant_allows_distinct(tmp_path):
    (tmp_path / "lab.py").write_text('CONTAINER = "lab"\nDASHBOARD_PORT = 9119\n')
    (tmp_path / "old.py").write_text('CONTAINER = "old"\nDASHBOARD_PORT = 9120\n')
    assert settings.load_variant("lab", tmp_path)["CONTAINER"] == "lab"


def test_load_variant_ignores_broken_other(tmp_path):
    (tmp_path / "lab.py").write_text('CONTAINER = "lab"\nDASHBOARD_PORT = 9119\n')
    (tmp_path / "bad_import.py").write_text("import does_not_exist\n")
    (tmp_path / "bad_syntax.py").write_text("CONTAINER = ")
    assert settings.load_variant("lab", tmp_path)["CONTAINER"] == "lab"
