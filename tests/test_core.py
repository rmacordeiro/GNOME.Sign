import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


from certificate_manager import CertificateManager
from config_manager import ConfigManager
from i18n import DEFAULT_LANGUAGE
from paths import generate_output_path


@pytest.fixture
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from gi.repository import GLib
    monkeypatch.setattr(GLib, "get_user_config_dir", lambda: str(tmp_path))
    cfg = ConfigManager()
    cfg.load()
    return cfg


def test_default_templates_created(config):
    assert config.get_signature_templates()
    assert config.get_active_template()["id"] in [t["id"] for t in config.get_signature_templates()]


def test_delete_active_template_falls_back(config):
    templates = config.get_signature_templates()
    first, second = templates[0]["id"], templates[1]["id"]
    config.set_active_template_id(first)
    assert config.delete_template(first) is True
    assert config.get_active_template_id() != first
    assert config.get_active_template() is not None
    assert config.get_template_by_id(second) is not None


def test_cannot_delete_last_template_or_unknown(config):
    assert config.delete_template("does-not-exist") is False
    ids = [t["id"] for t in config.get_signature_templates()]
    for tid in ids[:-1]:
        assert config.delete_template(tid) is True
    assert config.delete_template(ids[-1]) is False
    assert len(config.get_signature_templates()) == 1


def test_unsupported_language_falls_back(config):
    config.config_data["language"] = "xx"
    config.save()
    config.load()
    assert config.get_language() == DEFAULT_LANGUAGE


def test_recent_files_are_unique_and_capped(config):
    for i in range(ConfigManager.MAX_RECENT_FILES + 5):
        config.add_recent_file(f"/tmp/f{i}.pdf")
    config.add_recent_file("/tmp/f10.pdf")
    recent = config.get_recent_files()
    assert len(recent) == ConfigManager.MAX_RECENT_FILES
    assert recent[0] == "/tmp/f10.pdf"
    assert len(set(recent)) == len(recent)


def test_output_path_generation(tmp_path):
    src = tmp_path / "doc.pdf"
    assert generate_output_path(str(src)) == str(tmp_path / "doc-signed.pdf")
    (tmp_path / "doc-signed.pdf").write_bytes(b"x")
    assert generate_output_path(str(src)) == str(tmp_path / "doc-signed-1.pdf")
    (tmp_path / "doc-signed-1.pdf").write_bytes(b"x")
    assert generate_output_path(str(src)) == str(tmp_path / "doc-signed-2.pdf")


def test_certificate_password_check(p12_file):
    manager = CertificateManager()
    assert manager.test_certificate(p12_file, "secret") == "Test Signer"
    assert manager.test_certificate(p12_file, "wrong") is None
    assert manager.get_credentials("/nonexistent.p12", "secret") == (None, None)
