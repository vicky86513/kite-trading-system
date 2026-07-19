"""
Docker-friendly authentication handler.

When running in Docker, trackers can't prompt for user input.
This module handles both interactive and non-interactive auth.
"""

import os
import json
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from kiteconnect import KiteConnect

from . import config
from .logger import get_logger

load_dotenv()
log = get_logger("AUTH")

API_KEY = os.getenv("KITE_API_KEY")
API_SECRET = os.getenv("KITE_API_SECRET")
REQUEST_TOKEN_FILE = config.CACHE_DIR / "request_token.txt"
TOKEN_CACHE_FILE = config.KITE_SESSION_FILE

if not API_KEY or not API_SECRET:
    raise RuntimeError(
        "❌ API credentials missing!\n"
        "Please set environment variables:\n"
        "  KITE_API_KEY=your_key\n"
        "  KITE_API_SECRET=your_secret"
    )


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


def load_stored_request_token():
    """Load previously saved request token from file."""
    if not REQUEST_TOKEN_FILE.exists():
        return None
    
    try:
        with open(REQUEST_TOKEN_FILE) as f:
            token = f.read().strip()
        if token:
            return token
    except Exception as e:
        log.warning(f"Failed to load stored request token: {e}")
    
    return None


def save_request_token(request_token):
    """Save request token for future use."""
    try:
        REQUEST_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(REQUEST_TOKEN_FILE, "w") as f:
            f.write(request_token.strip())
        log.info(f"✓ Request token saved to {REQUEST_TOKEN_FILE}")
    except Exception as e:
        log.error(f"Failed to save request token: {e}")


def get_login_instructions():
    """Return login instructions for user."""
    kite = KiteConnect(api_key=API_KEY)
    login_url = kite.login_url()
    
    instructions = f"""
╔════════════════════════════════════════════════════════════════════════╗
║                  🔐 KITE AUTHENTICATION REQUIRED                       ║
╚════════════════════════════════════════════════════════════════════════╝

Your cached session has expired or this is first run.

🔗 LOGIN URL (open in browser):
   {login_url}

Steps:
1. Click the link above or open it in your browser
2. Login with your Zerodha credentials
3. You'll be redirected - copy the 'request_token' from the URL
4. It looks like: rt_xxxxxxxxxxxx
5. Save it in: {REQUEST_TOKEN_FILE}
   OR pass via: KITE_REQUEST_TOKEN environment variable
   OR provide when prompted

Example:
   export KITE_REQUEST_TOKEN=rt_xxxxxxxxxxxx
   python -m src.trackers.nifty_tracker

Or create {REQUEST_TOKEN_FILE} with the token.

"""
    return instructions, login_url


def get_kite_session_interactive():
    """
    Interactive authentication (with user input).
    Used for local development/testing.
    """
    kite = KiteConnect(api_key=API_KEY)

    cached_token = load_cached_token()
    if cached_token:
        kite.set_access_token(cached_token)
        try:
            kite.profile()
            log.info("✓ Using cached access token (no login needed today).")
            return kite, cached_token
        except Exception:
            log.warning("✗ Cached token expired/invalid, need to log in again.")

    instructions, login_url = get_login_instructions()
    print(instructions)
    
    request_token = input("Enter request token (rt_xxxxx): ").strip()

    if not request_token:
        raise RuntimeError("❌ Request token cannot be empty!")

    try:
        data = kite.generate_session(request_token, api_secret=API_SECRET)
        access_token = data["access_token"]
        kite.set_access_token(access_token)
        save_token_cache(access_token)
        save_request_token(request_token)
        log.info("✓ Authenticated successfully.")
        return kite, access_token
    except Exception as e:
        log.error(f"✗ Authentication failed: {e}")
        raise


def get_kite_session_docker():
    """
    Docker-friendly authentication (non-interactive).
    Uses environment variables or saved token files.
    """
    kite = KiteConnect(api_key=API_KEY)

    # Try cached token first
    cached_token = load_cached_token()
    if cached_token:
        kite.set_access_token(cached_token)
        try:
            kite.profile()
            log.info("✓ Using cached access token (no login needed today).")
            return kite, cached_token
        except Exception:
            log.warning("✗ Cached token expired/invalid.")

    # Try environment variable
    request_token = os.getenv("KITE_REQUEST_TOKEN")
    if request_token:
        log.info("Using request token from KITE_REQUEST_TOKEN env var")
    else:
        # Try saved file
        request_token = load_stored_request_token()
        if request_token:
            log.info(f"Using request token from {REQUEST_TOKEN_FILE}")

    if not request_token:
        instructions, login_url = get_login_instructions()
        log.error(instructions)
        raise RuntimeError(
            "❌ No valid request token found!\n"
            "Please provide via:\n"
            "  1. Environment: export KITE_REQUEST_TOKEN=rt_xxxxx\n"
            f"  2. File: {REQUEST_TOKEN_FILE}\n"
            "  3. Docker: -e KITE_REQUEST_TOKEN=rt_xxxxx"
        )

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


def get_kite_session():
    """
    Auto-detect environment and use appropriate auth method.
    
    - Docker: Uses non-interactive (env vars or token files)
    - Local: Uses interactive (prompts for input)
    """
    is_docker = os.path.exists("/.dockerenv")
    
    if is_docker:
        log.info("🐳 Running in Docker - using non-interactive auth")
        return get_kite_session_docker()
    else:
        log.info("💻 Running locally - using interactive auth")
        return get_kite_session_interactive()