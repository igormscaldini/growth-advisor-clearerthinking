"""Bridges Streamlit Cloud secrets to the rest of the codebase.

On Streamlit Cloud, credentials live in `st.secrets` (managed via the app's UI).
On local machines, they live in `.env` + `secrets/*.json` files.

This module materializes Streamlit secrets into:
  - environment variables (so existing `os.getenv(...)` calls work unchanged)
  - on-disk files at /tmp/secrets/ (so existing file-based loaders work unchanged)

Call `materialize_cloud_secrets()` once at app startup, before any client modules
are imported. Safe to call multiple times and outside Streamlit context (no-op).
"""
from __future__ import annotations

import os
from pathlib import Path

# Plain string secrets to mirror into environment variables
_ENV_KEYS = (
    "GA4_PROPERTY_ID",
    "GSC_SITE_URL",
    "SHEETS_NEWSLETTER_FEEDBACK_ID",
    "STRIPE_SECRET_KEY",
    "GOOGLE_ADS_DEVELOPER_TOKEN",
    "GOOGLE_ADS_CUSTOMER_ID",
    "GOOGLE_ADS_LOGIN_CUSTOMER_ID",
    "BEEHIIV_API_KEY",
    "BEEHIIV_PUB_CLEARER_THINKING",
    "BEEHIIV_PUB_12_LEVERS",
    "BEEHIIV_PUB_TRANSPARENT_REPLICATIONS",
)

# JSON blobs to materialize as on-disk files
_FILE_KEYS = {
    "OAUTH_CLIENT_JSON": ("oauth-client.json", "GA4_OAUTH_CLIENT_FILE"),
    "GOOGLE_TOKEN_JSON": ("ga4-token.json", "GA4_TOKEN_FILE"),
}


def materialize_cloud_secrets() -> bool:
    """Pull values from `st.secrets` into env vars + /tmp/secrets/. Returns True if cloud secrets were found."""
    try:
        import streamlit as st
    except ImportError:
        return False

    try:
        # Accessing st.secrets without a Streamlit runtime or secrets file raises.
        # Use a cheap probe before doing anything expensive.
        _ = dict(st.secrets)
    except Exception:
        return False

    found_any = False

    for key in _ENV_KEYS:
        if key in st.secrets:
            val = str(st.secrets[key]).strip()
            if val:
                os.environ[key] = val
                found_any = True

    if any(k in st.secrets for k in _FILE_KEYS):
        tmp_dir = Path("/tmp/secrets")
        tmp_dir.mkdir(exist_ok=True)
        for secret_key, (filename, env_var) in _FILE_KEYS.items():
            if secret_key in st.secrets:
                blob = str(st.secrets[secret_key]).strip()
                if blob:
                    path = tmp_dir / filename
                    path.write_text(blob)
                    os.environ[env_var] = str(path)
                    found_any = True

    return found_any


def materialize_ci_secrets() -> bool:
    """Write the OAuth JSON blobs GitHub Actions passes as env vars to secrets/.

    The CI counterpart of `materialize_cloud_secrets`: on Actions the credentials
    arrive as env vars, but every Google client here loads them from a file. Reuses
    the `_FILE_KEYS` mapping so the secret-name-to-filename mapping lives in one
    place. No-op locally, where the files already exist. Returns True if it wrote any.
    """
    root = Path(__file__).parent
    wrote_any = False

    for secret_key, (filename, _env_var) in _FILE_KEYS.items():
        blob = os.environ.get(secret_key, "").strip()
        if not blob:
            continue
        target = root / "secrets" / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(blob)
        wrote_any = True

    return wrote_any
