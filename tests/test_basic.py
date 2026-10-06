import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from i18n import I18NManager, SUPPORTED_LANGUAGES
from stamp_creator import pango_to_html


def test_all_languages_have_same_keys():
    translations = I18NManager().translations
    assert set(translations) == set(SUPPORTED_LANGUAGES)
    reference = set(translations["en"])
    for lang, catalog in translations.items():
        assert set(catalog) == reference, lang


def test_unsupported_language_is_ignored():
    manager = I18NManager()
    manager.set_language("xx")
    assert manager.get_language() == "en"


def test_stamp_markup_is_escaped():
    html = pango_to_html('<span color="red;}<script>">a &lt;b&gt; &amp; c</span>')
    assert "<script>" not in html
    assert "a &lt;b&gt; &amp; c" in html


def test_every_used_translation_key_exists():
    import re
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "src"
    used = set()
    for path in src.rglob("*.py"):
        used |= set(re.findall(r"""\b_\(\s*["']([a-z0-9_]+)["']\s*\)""", path.read_text()))
    missing = used - set(I18NManager().translations["en"])
    assert not missing, sorted(missing)
