#!/usr/bin/env python3
"""Report Vietnamese dashboard translation coverage against English source keys."""

import json
import re
import sys
from pathlib import Path


LOCALES = Path(__file__).resolve().parents[1] / "chatwoot/app/javascript/dashboard/i18n/locale"


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def leaves(value, prefix=""):
    for key, child in value.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(child, dict):
            yield from leaves(child, path)
        elif isinstance(child, str):
            yield path, child
        # DashboardLocaleCatalog indexes string leaves in objects only. Arrays
        # such as report grouping options are structured UI data, not keys.


def catalog(locale):
    result = {}
    owners = {}
    directory = LOCALES / locale
    imports = re.findall(r"^import \w+ from '\./(\w+\.json)';$", (directory / "index.js").read_text(), re.M)
    for filename in imports:
        path = directory / filename
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
        if not isinstance(data, dict):
            raise ValueError(f"translation root must be an object: {path}")
        entries = dict(leaves(data))
        for key, value in entries.items():
            if key in owners:
                raise ValueError(f"duplicate effective key {key}: {owners[key]} and {path.name}")
            owners[key] = path.name
            result[key] = value
        yield path.name, entries


def main():
    english_files = dict(catalog("en"))
    vietnamese_files = dict(catalog("vi"))
    english = {key: value for entries in english_files.values() for key, value in entries.items()}
    vietnamese = {key: value for entries in vietnamese_files.values() for key, value in entries.items()}
    print("file                         english  missing  identical")
    for filename, entries in english_files.items():
        missing = sum(key not in vietnamese for key in entries)
        identical = sum(vietnamese.get(key) == value for key, value in entries.items())
        print(f"{filename:<28} {len(entries):>7} {missing:>8} {identical:>10}")
    print(f"TOTAL                        {len(english):>7} {sum(key not in vietnamese for key in english):>8} "
          f"{sum(vietnamese.get(key) == value for key, value in english.items()):>10}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"Catalog error: {error}", file=sys.stderr)
        sys.exit(1)
