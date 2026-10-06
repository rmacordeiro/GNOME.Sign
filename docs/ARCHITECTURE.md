# Architecture

GNOME-Sign is a GTK4/libadwaita application. Logic that does not need a display lives in GTK-free modules so it can be unit tested.

| Area | Files | Role |
|------|-------|------|
| Application controller | `src/main.py` | GTK application, actions, wiring between UI and services |
| Window and widgets | `src/ui/` | Main window, preferences, stamp editor, dialogs, sidebar |
| Signing | `src/services/signing_service.py` | pyHanko signing: visible/invisible, certification, RFC 3161 timestamps |
| Validation | `src/services/validation_service.py` | Signature validation, trust roots, optional online checks |
| Documents | `src/services/document_service.py` | Search, thumbnails, display-to-PDF coordinate conversion (rotation, CropBox) |
| Background work | `src/services/tasks.py` | `run_in_thread` with cancellation; results delivered on the GTK main loop |
| Models | `src/models.py` | `SearchResult`, `SignatureDetails` (including warnings) |
| Config | `src/config_manager.py` | JSON preferences in the user config directory |
| Certificates | `src/certificate_manager.py` | PKCS#12 handling; passwords in libsecret |
| Translations | `src/i18n.py`, `po/*.po` | Key based catalogs with English fallback |

## Packaging
`meson.build` installs the sources and `po/` for the Debian, Flatpak and Snap builds. Dependencies come from one lock file (`requirements.lock`), and `scripts/sync-deps.py` generates the per-format files.

## Supported runtimes
Python 3.12 or newer, GTK 4.10+, libadwaita 1.2+. Flatpak uses the GNOME runtime; Snap uses core24 and the gnome extension; Debian packages ship a virtualenv with the locked Python modules.

## Known limitations
- Stamp text is drawn unrotated on rotated pages (placement is correct).
- Settings are stored in JSON, not GSettings; certificate references are absolute paths.
- No zoom or fit-page modes yet.

## Licences (informational, not legal advice)
GNOME-Sign is AGPL-3.0-or-later. PyMuPDF is AGPL-3.0 (or commercial), which is compatible with this project's licence. pyHanko, certvalidator and cryptography use permissive licences (MIT / Apache-2.0 / BSD). Review dependency licences again when adding or upgrading packages.
