#!/usr/bin/env python3
"""Derive every package format's dependency input from requirements.lock.

Usage: scripts/sync-deps.py [--check]
Regenerates debian/requirements-venv.txt, requirements.txt and python-modules.json.
With --check, exits non-zero if any generated file is out of date (for CI).
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "requirements.lock"
FLATPAK = ROOT / "python-modules.json"
# Built from source inside the Flatpak (no wheels for the GNOME runtime); kept as-is from the existing manifest.
SOURCE_BUILT = {"pygobject", "pycairo"}
SKIP_ON_LINUX = {"tzdata"}
ARCHES = {"x86_64": "x86_64", "aarch64": "aarch64"}


def parse_lock():
    pkgs = []
    for m in re.finditer(r"^([A-Za-z0-9_.-]+)==([^\s;]+)", LOCK.read_text(), re.M):
        name = m.group(1).lower()
        if name not in SKIP_ON_LINUX:
            pkgs.append((name, m.group(2)))
    return pkgs


def pick(files, pkg):
    wheels = [f for f in files if f["packagetype"] == "bdist_wheel" and not f.get("yanked")]
    out = []
    for f in wheels:
        fn = f["filename"]
        if fn.endswith("-any.whl"):
            return [(f, None)]
    for arch in ARCHES:
        cands = [f for f in wheels if "manylinux" in f["filename"] and f["filename"].endswith(f"{arch}.whl")
                 and re.search(r"-(cp312|cp311|cp310|cp39|cp38|abi3)", f["filename"].replace("-abi3", "-cp312"))
                 and ("cp312" in f["filename"] or "abi3" in f["filename"])]
        if not cands:
            raise SystemExit(f"no {arch} wheel for {pkg}")
        out.append((sorted(cands, key=lambda f: f["filename"])[-1], arch))
    return out


def build_flatpak(pkgs):
    old = json.loads(FLATPAK.read_text())
    sources = [s for s in old["sources"] if any(k in s["url"] for k in ("pygobject", "pycairo"))]
    for name, ver in pkgs:
        url = f"https://pypi.org/pypi/{name}/{ver}/json"
        with urllib.request.urlopen(url) as r:
            files = json.load(r)["urls"]
        for f, arch in pick(files, name):
            s = {"type": "file", "url": f["url"], "sha256": f["digests"]["sha256"]}
            if arch:
                s["only-arches"] = [arch]
            sources.append(s)
    names = sorted({n for n, _ in pkgs} | {"pygobject", "pycairo"})
    old["sources"] = sources
    old["build-commands"] = [
        'pip3 install --verbose --exists-action=i --no-index --find-links="file://${PWD}" '
        "--prefix=${FLATPAK_DEST} --no-build-isolation " + " ".join(names)
    ]
    return json.dumps(old, indent=4) + "\n"


def main():
    check = "--check" in sys.argv
    pkgs = parse_lock()
    lock_text = LOCK.read_text()
    outputs = {
        ROOT / "debian/requirements-venv.txt": lock_text,
        ROOT / "requirements.txt": "# Generated from pyproject.toml; do not edit. See scripts/sync-deps.py\n"
        + "".join(f"{n}=={v}\n" for n, v in pkgs),
    }
    if not check or "--flatpak" in sys.argv:
        outputs[FLATPAK] = build_flatpak(pkgs)
    stale = []
    for path, text in outputs.items():
        if path.exists() and path.read_text() == text:
            continue
        stale.append(path.name)
        if not check:
            path.write_text(text)
    if check and stale:
        sys.exit(f"Out of date, run scripts/sync-deps.py: {', '.join(stale)}")
    print("updated:" if not check else "ok", ", ".join(stale))


if __name__ == "__main__":
    main()
