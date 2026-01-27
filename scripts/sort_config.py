#!/usr/bin/env python3
"""Utility to inspect, validate and merge project env files.

Usage:
  python scripts/sort_config.py         # show current merged view
  python scripts/sort_config.py --write  # write merged variables to .env (root)
  python scripts/sort_config.py --target app/.env --write  # write to app/.env

Priority (highest -> lowest):
  1. OS environment variables
  2. `app/.env` (if present)
  3. `ops.env.example` (if present)
  4. `.env.example`

The script prints a table showing where each variable comes from and its value.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Dict, Tuple
import dataclasses
import importlib
import re


def parse_env_file(path: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        out[key.strip()] = val.strip()
    return out


def merge_sources(sources: Tuple[Tuple[str, Dict[str, str]], ...]) -> Dict[str, Tuple[str, str]]:
    """Merge sources in order; return mapping key -> (source_name, value)."""
    result: Dict[str, Tuple[str, str]] = {}
    for name, mapping in sources:
        for k, v in mapping.items():
            # don't overwrite higher-priority values
            if k in result:
                continue
            result[k] = (name, v)
    return result


def format_row(key: str, origin: str, value: str) -> str:
    v = value
    if len(v) > 80:
        v = v[:77] + "..."
    return f"{key:40} {origin:12} {v}"


def _coerce_type(name: str, value: str, hint: str) -> Tuple[bool, str]:
    """Attempt to coerce `value` to hint type. Return (ok, normalized_str)."""
    try:
        if hint == "int":
            int(value)
            return True, str(int(value))
        if hint == "bool":
            if value.lower() in {"1", "true", "t", "yes", "on"}:
                return True, "True"
            if value.lower() in {"0", "false", "f", "no", "off"}:
                return True, "False"
            return False, value
        # default: string
        return True, value
    except Exception:
        return False, value


def main() -> int:
    ap = argparse.ArgumentParser(description="Inspect and merge env files for SYSGrow")
    ap.add_argument("--write", action="store_true", help="Write merged output to target file")
    ap.add_argument("--target", default=".env", help="Target path to write merged file (default: .env)")
    ap.add_argument("--show-all", action="store_true", help="Show all variables including those only in examples")
    ap.add_argument("--validate", action="store_true", help="Validate required keys and basic types")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    example = root / ".env.example"
    ops_example = root / "ops.env.example"
    app_env = root / "app" / ".env"

    src_example = parse_env_file(example)
    src_ops = parse_env_file(ops_example)
    src_app = parse_env_file(app_env)
    src_env = {k: v for k, v in os.environ.items()}

    # Priority: env > app_env > ops > example
    merged = merge_sources((("env", src_env), ("app/.env", src_app), ("ops.example", src_ops), ("example", src_example)))

    # Print header
    print("Key".ljust(40), "Origin".ljust(12), "Value")
    print("-" * 100)
    keys = sorted(set(list(src_example.keys()) + list(src_ops.keys()) + list(src_app.keys()) + list(src_env.keys())))
    for k in keys:
        if k in merged:
            origin, val = merged[k]
            if not args.show_all and origin == "example" and k not in src_app and k not in src_env:
                # skip pure-example keys unless show_all
                continue
            print(format_row(k, origin, val))
        else:
            # key not present anywhere (shouldn't happen because we built keys from sources)
            print(format_row(k, "(missing)", ""))

    # Validation: derive schema from app/config.py when possible
    if args.validate:
        print("\nValidation:\n")
        errors = []

        def build_schema_from_appconfig() -> Dict[str, str]:
            """Try to import AppConfig and parse app/config.py source to map env var names to basic types."""
            schema: Dict[str, str] = {}
            # Attempt to import the module and dataclass
            try:
                mod = importlib.import_module("app.config")
                AppConfig = getattr(mod, "AppConfig", None)
            except Exception:
                AppConfig = None

            src_text = ""
            try:
                src_path = Path(mod.__file__) if AppConfig is not None else None
                if src_path and src_path.exists():
                    src_text = src_path.read_text(encoding="utf-8")
            except Exception:
                src_text = ""

            if AppConfig is not None:
                for f in dataclasses.fields(AppConfig):
                    name = f.name
                    # search for explicit os.getenv/_env_bool/_env_int references for this field
                    hint = "str"
                    t = getattr(f.type, "__name__", str(f.type))
                    if "int" in t.lower():
                        hint = "int"
                    elif "bool" in t.lower():
                        hint = "bool"
                    elif "float" in t.lower():
                        hint = "float"

                    env_names = []
                    if src_text:
                        # look for patterns like '<name>: .* = field(default_factory=lambda: os.getenv("VAR"'
                        pat1 = re.compile(rf"{re.escape(name)}\s*:.*=\s*field\(default_factory=lambda:.*os\.getenv\(\s*\"([A-Z0-9_]+)\"",
                                          flags=re.IGNORECASE)
                        m1 = pat1.search(src_text)
                        if m1:
                            env_names.append(m1.group(1))
                        # look for _env_bool("VAR") or _env_int("VAR") uses
                        pat2 = re.compile(rf"{re.escape(name)}\s*:.*=\s*field\(default_factory=lambda:.*_env_(?:bool|int|int_multi)\(\s*(\(?[\"\'A-Z0-9_,\s\)]+)",
                                          flags=re.IGNORECASE)
                        m2 = pat2.search(src_text)
                        if m2:
                            # extract first quoted name if present
                            found = re.findall(r'"([A-Z0-9_]+)"|\'([A-Z0-9_]+)\'', m2.group(1))
                            if found:
                                # found is list of tuples from the alternation; pick non-empty
                                for a, b in found:
                                    env_names.append(a or b)

                    # fallback: try an uppercased env name matching common patterns
                    if not env_names:
                        candidate = name.upper()
                        if not candidate.startswith("SYSGROW_"):
                            candidate = f"SYSGROW_{candidate}"
                        env_names = [candidate]

                    # register schema entries for discovered env names
                    for en in env_names:
                        schema[en] = hint

            # If import failed or no AppConfig, fallback to example files
            if not schema:
                # use a small default set as fallback
                schema = {
                    "SYSGROW_SECRET_KEY": "str",
                    "SYSGROW_DATABASE_PATH": "str",
                    "SYSGROW_ENABLE_MQTT": "bool",
                    "SYSGROW_MQTT_PORT": "int",
                    "SYSGROW_PORT": "int",
                    "SYSGROW_HOST": "str",
                }

            return schema

        schema = build_schema_from_appconfig()

        for key, hint in schema.items():
            if key not in merged:
                errors.append(f"Missing required variable: {key}")
                continue
            origin, val = merged[key]
            ok, norm = _coerce_type(key, val, "int" if hint == "int" else ("bool" if hint == "bool" else "str"))
            if not ok:
                errors.append(f"Invalid type for {key}: expected {hint}, got '{val}' (from {origin})")

        if errors:
            for e in errors:
                print("- ", e)
            print("\nValidation failed. Fix the variables above or run without --validate to inspect.")
        else:
            print("All required variables present with expected basic types.")

    if args.write:
        target = Path(args.target)
        out_lines = []
        for k in sorted(merged.keys()):
            origin, val = merged[k]
            out_lines.append(f"{k}={val}")
        content = "\n".join(out_lines) + "\n"
        target.write_text(content, encoding="utf-8")
        print(f"Wrote merged {len(out_lines)} keys to {target}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
