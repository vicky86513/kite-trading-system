"""
Shared Kite Connect authentication helper.

Handles login and caches the access token for the day so you don't have to
paste the request token every time you run a tracker script.
"""

import os
import json
from datetime import date

from dotenv import load_dotenv
from kiteconnect import KiteConnect

from . import config
from .logger import get_logger

load_dotenv()
log = get_logger("AUTH")

API_KEY = os.getenv("KITE_API_KEY")
API_SECRET = os.getenv("KITE_API_SECRET")

if not API_KEY or not API_SECRET:
    raise RuntimeError(
        "❌ API credentials missing!\n"
        "Please create a .env file with:\n"
        "  KITE_API_KEY=your_key\n"
        "  KITE_API_SECRET=your_secret"
    )

TOKEN_CACHE_FILE = config.KITE_SESSION_FILE


def load_cached_token():
    """Load cached access token if it's still valid (today's date)."""
    if not TOKEN_CACHE_FILE.exists():
        return None

    try:
        with open(TOKEN_CACHE_FILE) as f:
            cache = json.load(f)

        if cache.get("date") != str(date.today()):
            return None

        return cache.get("access_token")
    except (json.JSONDecodeError, IOError) as e:
        log.warning(f"Failed to load cached token: {e}")
        return None


def save_token_cache(access_token):
    """Save access token with today's date."""
    with open(TOKEN_CACHE_FILE, "w") as f:
        json.dump({"date": str(date.today()), "access_token": access_token}, f)


def get_kite_session():
    """
    Returns (kite, access_token).

    Reuses today's cached token if it's still valid, otherwise walks through
    the login flow once and caches the new token for the rest of the day.
    """
    kite = KiteConnect(api_key=API_KEY)

    cached_token = load_cached_token()
    if cached_token:
        kite.set_access_token(cached_token)
        try:
            kite.profile()  # cheap call just to validate the cached token
            log.info("✓ Using cached access token (no login needed today).")
            return kite, cached_token
        except Exception:
            log.warning("✗ Cached token expired/invalid, need to log in again.")

    # Need new token
    log.info(f"🔗 Login URL: {kite.login_url()}")
    request_token = input("Enter request token: ").strip()

    if not request_token:
        raise RuntimeError("Request token cannot be empty!")

    try:
        data = kite.generate_session(request_token, api_secret=API_SECRET)
        access_token = data["access_token"]
        kite.set_access_token(access_token)
        save_token_cache(access_token)
        log.info("✓ Authenticated successfully.")
        return kite, access_token
    except Exception as e:
        log.error(f"✗ Authentication failed: {e}")
        raise