# Security Policy

## Supported versions
Only the latest release receives security fixes.

## Reporting a vulnerability
Please do **not** open a public issue. Use GitHub's private vulnerability reporting: <https://github.com/rmacordeiro/GNOME.Sign/security/advisories/new>. Include the version, packaging format (deb, Flatpak, Snap) and steps to reproduce. You can expect an acknowledgement within a few days.

## Scope notes
- Certificate passwords are stored in the system keyring (libsecret), never in the configuration file.
- Online certificate-status checks are off by default.
- Dependencies are pinned and hash-locked; `pip-audit` runs in CI.
