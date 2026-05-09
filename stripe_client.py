"""Shared Stripe client — reads the restricted key from env (set by .env locally or st.secrets on Cloud)."""
import os
from pathlib import Path

import stripe
from dotenv import dotenv_values, load_dotenv

# Local: load .env and override any empty shell-exported STRIPE_SECRET_KEY.
# Cloud: no .env present; env was already populated by secrets_loader.materialize_cloud_secrets().
if Path(".env").exists():
    load_dotenv(override=True)
    _KEY = dotenv_values(".env").get("STRIPE_SECRET_KEY", "").strip() or os.getenv("STRIPE_SECRET_KEY", "").strip()
else:
    _KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()


def get_client() -> stripe:
    if not _KEY:
        raise SystemExit("STRIPE_SECRET_KEY not set in .env")
    stripe.api_key = _KEY
    return stripe
