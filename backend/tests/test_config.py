from app import config


def test_load_env_file_sets_missing_values_and_keeps_existing_ones(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("# comment\n\nPM_NEW=from-file\nPM_EXISTING=from-file\nnot a pair\n", encoding="utf-8")
    monkeypatch.setattr(config, "ENV_PATH", env_file)
    monkeypatch.delenv("PM_NEW", raising=False)
    monkeypatch.setenv("PM_EXISTING", "from-environment")

    config.load_env_file()

    assert config.os.environ["PM_NEW"] == "from-file"
    assert config.os.environ["PM_EXISTING"] == "from-environment"
    monkeypatch.delenv("PM_NEW")


def test_load_env_file_ignores_a_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ENV_PATH", tmp_path / "absent.env")

    config.load_env_file()
