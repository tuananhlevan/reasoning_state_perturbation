#!/usr/bin/env python3
"""Validate reusable Google Drive OAuth credentials from .env."""
import argparse, json, os
from pathlib import Path
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

def load_env(path=Path(".env")):
    if not path.is_file(): return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        key, value = line.split("=", 1); os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

def get_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    token, client = os.getenv("GDRIVE_TOKEN_JSON", "").strip(), os.getenv("GDRIVE_CREDENTIALS_JSON", "").strip()
    current = Credentials.from_authorized_user_info(json.loads(token), SCOPES) if token else None
    if current and current.valid: return current
    if current and current.expired and current.refresh_token: current.refresh(Request()); return current
    if not client: raise RuntimeError("GDRIVE_CREDENTIALS_JSON is missing from .env")
    current = InstalledAppFlow.from_client_config(json.loads(client), SCOPES).run_local_server(port=0)
    raise RuntimeError("Initial consent completed. Set GDRIVE_TOKEN_JSON in .env to: " + current.to_json())

def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--env", type=Path, default=Path(".env")); args = parser.parse_args(); load_env(args.env)
    try: get_credentials()
    except Exception as exc: parser.error(str(exc))
    print("Google Drive authentication is valid; refresh is non-interactive."); return 0
if __name__ == "__main__": raise SystemExit(main())
