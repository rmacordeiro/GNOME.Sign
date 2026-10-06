# Contributing

Thanks for helping improve GNOME-Sign.

## Setup
```bash
python3 -m venv --system-site-packages .venv && . .venv/bin/activate
pip install -r requirements.lock pytest ruff mypy pip-audit
```
PyGObject, GTK 4 and libadwaita come from your system packages.

## Before opening a pull request
```bash
ruff check .
mypy
python -m pytest -q
python scripts/sync-deps.py --check
python scripts/version.py --check
```

## Dependencies
`pyproject.toml` is the source of truth and `requirements.lock` is the hashed lock. After changing either, run `python scripts/sync-deps.py` to regenerate `requirements.txt`, the Debian requirements and the Flatpak `python-modules.json`.

## Translations
Texts live in `po/<lang>.po` (`msgid` is the key used in code, `msgstr` the text). To add a language copy `po/gnome-sign.pot` to `po/<lang>.po`, translate it, add it to `SUPPORTED_LANGUAGES` in `src/i18n.py` and to `po_sources` in `meson.build`. Keep placeholders such as `{}`. A test checks that all catalogs share the same keys.

## Releases
Run `python scripts/version.py --set X.Y.Z`, then add the `<release>` entry in the metainfo, the `debian/changelog` entry and `CHANGELOG.md`.

## Screenshots
Store them in `screenshoots/` at about 1000 px wide, update the URLs in the metainfo file, and use the current release's look.

## Code layout
See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Keep crypto and PDF logic in the GTK-free `src/services` modules so it can be tested without a display.
