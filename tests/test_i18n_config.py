import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from config_manager import ConfigManager  # noqa: E402
from i18n import I18NManager, parse_po  # noqa: E402


def test_parse_po_handles_escapes_and_multiline():
    text = (
        'msgid ""\nmsgstr ""\n"Language: xx\\n"\n\n'
        'msgid "a"\nmsgstr "line1\\nline2 \\"q\\""\n\n'
        'msgid "b"\nmsgstr ""\n"part one "\n"part two"\n'
    )
    parsed = parse_po(text)
    assert "" not in parsed
    assert parsed["a"] == 'line1\nline2 "q"'
    assert parsed["b"] == "part one part two"


def test_translation_falls_back_to_english_then_key(tmp_path):
    (tmp_path / "en.po").write_text('msgid "k"\nmsgstr "English"\n')
    (tmp_path / "pt.po").write_text('msgid "other"\nmsgstr "Outro"\n')
    i18n = I18NManager("pt", po_dirs=[str(tmp_path)])
    assert i18n._("k") == "English"
    assert i18n._("other") == "Outro"
    assert i18n._("missing") == "missing"


def test_new_config_options_roundtrip(tmp_path):
    cfg = ConfigManager()
    cfg.config_file = str(tmp_path / "config.json")
    cfg.load()
    assert cfg.get_flag("review_before_signing") is True
    assert cfg.get_flag("online_validation") is False
    cfg.set_flag("certify_signatures", True)
    cfg.set_timestamp_url("https://tsa.example/ts")
    cfg.add_trusted_cert_path("/x/root.pem")
    cfg.add_trusted_cert_path("/x/root.pem")
    assert cfg.get_trusted_cert_paths() == ["/x/root.pem"]
    cfg.remove_trusted_cert_path("/x/root.pem")
    assert cfg.get_trusted_cert_paths() == []
    assert cfg.get_flag("certify_signatures") and cfg.get_timestamp_url() == "https://tsa.example/ts"
