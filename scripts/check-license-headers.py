#!/usr/bin/env python3
# Copyright (c) 2026 DX-OSD contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Check that every source file we own carries an SPDX license header.

OLP PoF requires the OSI license to be stated in each code file. Vendored upstream
trees (`chatwoot/`, `crm/`) keep their own upstream license files and are not checked.

Usage: python scripts/check-license-headers.py   (exit code 1 lists the files missing a header)
"""
import subprocess
import sys

OWNED = ("frappe-custom/", "scripts/", "activepieces/", "docker/", "docker-compose")
CODE = (".py", ".sh", ".js", ".mjs", ".yml", ".yaml", ".toml", "Caddyfile")


def tracked():
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout
    return [p for p in out.splitlines() if p.startswith(OWNED) and p.endswith(CODE)]


def missing(paths):
    bad = []
    for path in paths:
        with open(path, encoding="utf-8", errors="replace") as f:
            if "SPDX-License-Identifier" not in f.read(600):
                bad.append(path)
    return bad


def main():
    paths = tracked()
    bad = missing(paths)
    for path in bad:
        print(f"missing SPDX header: {path}")
    print(f"{len(paths) - len(bad)}/{len(paths)} files have an SPDX header")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
