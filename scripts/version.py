#!/usr/bin/env python3
"""Keeps the release version consistent across all files.

  scripts/version.py --check          fail if the version locations disagree
  scripts/version.py --set 1.2.0      update all locations (release notes must be added by hand)
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCATIONS = {
    "meson.build": r"(version: ')([^']+)(')",
    "pyproject.toml": r'(?m)^(version = ")([^"]+)(")',
    "snap/snapcraft.yaml": r"(?m)^(version: ')([^']+)(')",
    "src/ui/dialogs.py": r'(set_version\(")([^"]+)("\))',
}
METAINFO = ROOT / "io.github.ppgllrd.GNOME-Sign.metainfo.xml"
CHANGELOG = ROOT / "debian/changelog"


def read_versions():
    versions = {}
    for name, pattern in LOCATIONS.items():
        match = re.search(pattern, (ROOT / name).read_text())
        versions[name] = match.group(2) if match else None
    meta = re.search(r'<release version="([^"]+)"', METAINFO.read_text())
    versions["metainfo (newest release)"] = meta.group(1) if meta else None
    log = re.match(r"gnome-sign \(([^)-]+)", CHANGELOG.read_text())
    versions["debian/changelog"] = log.group(1) if log else None
    return versions


def check():
    versions = read_versions()
    for name, value in versions.items():
        print(f"{name}: {value}")
    if len(set(versions.values())) != 1 or None in versions.values():
        print("Version mismatch", file=sys.stderr)
        return 1
    return 0


def set_version(new):
    if not re.fullmatch(r"\d+\.\d+\.\d+", new):
        sys.exit("Version must look like 1.2.3")
    for name, pattern in LOCATIONS.items():
        path = ROOT / name
        text, count = re.subn(pattern, rf"\g<1>{new}\g<3>", path.read_text(), count=1)
        if count != 1:
            sys.exit(f"Could not update {name}")
        path.write_text(text)
    print("Updated version locations; add the metainfo <release> and debian/changelog entries for the new version.")


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--set", metavar="VERSION")
    args = parser.parse_args()
    if args.check:
        sys.exit(check())
    set_version(args.set)


if __name__ == "__main__":
    main()
