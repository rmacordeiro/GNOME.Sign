# Changelog

Release notes for each version are also kept in the AppStream metadata and `debian/changelog`.
Run `scripts/version.py --check` to verify that all version locations agree.

## 1.1.0
- Signature details show algorithm, coverage, trusted timestamp, certificate chain and warnings.
- New signing options: RFC 3161 timestamps, certification and invisible signatures.
- Review-before-signing summary; signing runs off the UI thread.
- Optional online revocation checks (with privacy notice) and user-provided trusted certificates.
- Correct visible-signature placement on rotated and cropped pages.
- Keyboard control of the signature box, accessible names for header buttons, Adwaita confirmation dialogs.
- Translations moved to `po/*.po` files.

## 1.0.5
- Validation, search and thumbnails no longer block the UI; cached signature preview; GTK-free services and tests.

## 1.0.4
- Fix stamp template deletion; add missing translations; single locked dependency source.

## 1.0.3
- Security hardening (trust roots, no implicit network fetching, safe output creation, pinned dependencies and workflows).

## 1.0.2
- Portuguese translation.
