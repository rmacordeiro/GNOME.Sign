import json

import config_manager


def _load_config_with_base_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(
        config_manager.GLib, "get_user_config_dir", lambda: str(tmp_path)
    )
    cfg = config_manager.ConfigManager()
    cfg.load()
    return cfg


def test_load_sets_defaults_for_missing_keys(tmp_path, monkeypatch):
    config_dir = tmp_path / "gnomesign"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.json"
    config_path.write_text(
        json.dumps({"recent_files": ["/tmp/doc.pdf"]}), encoding="utf-8"
    )

    cfg = _load_config_with_base_dir(tmp_path, monkeypatch)

    assert cfg.get_recent_files() == ["/tmp/doc.pdf"]
    assert cfg.get_last_folder()
    assert cfg.get_language() == "en"
    assert cfg.get_signature_templates()
    assert cfg.get_active_template_id()


def test_recent_files_are_deduplicated_and_capped(tmp_path, monkeypatch):
    cfg = _load_config_with_base_dir(tmp_path, monkeypatch)

    for index in range(12):
        cfg.add_recent_file(f"/tmp/file-{index}.pdf")
    cfg.add_recent_file("/tmp/file-5.pdf")

    recent = cfg.get_recent_files()
    assert len(recent) == cfg.MAX_RECENT_FILES
    assert recent[0] == "/tmp/file-5.pdf"
