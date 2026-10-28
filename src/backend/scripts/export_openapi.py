"""Export the service's OpenAPI document as a versioned contract.

The schema is generated from the application itself, so the committed document
can never describe an API the code does not implement. With ``--check`` the
script compares instead of writing and exits non-zero on drift, which lets CI
reject a change to the API surface whose contract was not regenerated.

Usage, from ``src/backend``:
    python scripts/export_openapi.py           # regenerate the contract
    python scripts/export_openapi.py --check   # fail if it is out of date
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_CONTRACT = Path(__file__).resolve().parents[3] / "docs" / "api" / "openapi.json"

# Schema generation needs a valid configuration but performs no network I/O, so
# a credential-free local placeholder satisfies the required settings.
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGODB_DB_NAME", "contract")

# The backend root is placed on the import path so the script runs from any
# working directory; the import follows the configuration it depends on.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import create_app  # noqa: E402


def render() -> str:
    schema = create_app().openapi()
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare against the committed contract instead of writing it",
    )
    args = parser.parse_args()

    document = render()
    if args.check:
        current = _CONTRACT.read_text(encoding="utf-8") if _CONTRACT.exists() else ""
        if current != document:
            print(
                f"{_CONTRACT.name} is out of date; regenerate it with "
                "`python scripts/export_openapi.py` and commit the result.",
                file=sys.stderr,
            )
            return 1
        print(f"{_CONTRACT.name} matches the application schema.")
        return 0

    _CONTRACT.parent.mkdir(parents=True, exist_ok=True)
    _CONTRACT.write_text(document, encoding="utf-8", newline="\n")
    print(f"Wrote {_CONTRACT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
