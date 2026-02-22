**Configuration & Environment Files**

This project uses environment variables for runtime configuration. There are three places you may find configuration values:

- `app/.env` — Per-environment values (recommended to keep out of VCS for secrets).
- `.env.example` — Template with defaults and explanations. Use this to create your own `.env`.
- `ops.env.example` — Optional operational tuning values for staging/production.

Priority when merging (highest to lowest):

1. OS environment variables
2. `app/.env`
3. `ops.env.example`
4. `.env.example`

Recommended workflow

1. Copy `.env.example` to `.env` (or `app/.env`) and set secrets and platform-specific values.
2. For Raspberry Pi deployments, install with the `[raspberry]` extras: `pip install .[raspberry]`.
3. Use `scripts/sort_config.py --validate` to verify required variables and types.

Examples

Write merged env to `app/.env`:

```bash
python scripts/sort_config.py --target app/.env --write
```

Validate current configuration:

```bash
python scripts/sort_config.py --validate
```

Notes

- Keep secret values (like `SYSGROW_SECRET_KEY`, `SYSGROW_AES_KEY`) out of the repository. Use environment variables on CI and production.
- Platform-specific optional dependencies are exposed as extras in `pyproject.toml` (`raspberry`, `zigbee`, `windows`, `linux`, `adafruit`).
