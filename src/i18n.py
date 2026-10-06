import os

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = {"es": "Español", "en": "English", "pt": "Português"}

_ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}


def _unquote(token):
    """Decodes one quoted PO string literal."""
    body = token.strip()[1:-1]
    out, i = [], 0
    while i < len(body):
        if body[i] == "\\" and i + 1 < len(body):
            out.append(_ESCAPES.get(body[i + 1], body[i + 1]))
            i += 2
        else:
            out.append(body[i])
            i += 1
    return "".join(out)


def parse_po(text):
    """Parses a PO file into {msgid: msgstr}, skipping the header and untranslated entries.

    Supports multi-line strings and the usual escapes; plural forms and contexts are not used by this project.
    """
    catalog, msgid, msgstr, current = {}, None, None, None

    def flush():
        if msgid and msgstr:
            catalog[msgid] = msgstr

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("msgid "):
            flush()
            msgid, msgstr, current = _unquote(line[6:]), None, "id"
        elif line.startswith("msgstr "):
            msgstr, current = _unquote(line[7:]), "str"
        elif line.startswith('"'):
            if current == "id" and msgid is not None:
                msgid += _unquote(line)
            elif current == "str" and msgstr is not None:
                msgstr += _unquote(line)
    flush()
    return catalog


def default_po_dirs():
    """Installed layout (po/ next to this file) first, then the source checkout (../po)."""
    here = os.path.dirname(os.path.abspath(__file__))
    return [os.path.join(here, "po"), os.path.join(here, "..", "po")]


def load_catalogs(po_dirs=None):
    """Loads every supported language from <dir>/<lang>.po using the first directory that has it."""
    catalogs = {}
    for lang in SUPPORTED_LANGUAGES:
        catalogs[lang] = {}
        for directory in po_dirs or default_po_dirs():
            path = os.path.join(directory, f"{lang}.po")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    catalogs[lang] = parse_po(f.read())
                break
    return catalogs


class I18NManager:
    """Translates message keys using the .po catalogs in the po/ directory."""
    def __init__(self, initial_language=DEFAULT_LANGUAGE, po_dirs=None):
        self.language = initial_language
        self.translations = load_catalogs(po_dirs)

    def set_language(self, lang_code):
        """Sets the current language for translations."""
        if lang_code in self.translations: self.language = lang_code

    def get_language(self):
        """Returns the current language code."""
        return self.language

    def _(self, key):
        """Translates a key into the current language, falling back to English and then to the key itself."""
        return self.translations.get(self.language, {}).get(key) or self.translations.get(DEFAULT_LANGUAGE, {}).get(key, key)
