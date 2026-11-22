"""One-time Google sign-in for the task bot's Docs, Sheets and Slides (task_google.py).

Asks for ONE permission, drive.file: "see, edit, create and delete only the specific Google
Drive files you use with this app". The bot can create files and edit those, and cannot see
anything else in Igor's Drive. Saves secrets/taskbot-google-token.json and, with --github,
stores it as the TASKBOT_GOOGLE_TOKEN_JSON secret so the bot can use it on GitHub Actions.

    .venv/bin/python auth_taskbot_google.py --github
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from task_google import SCOPES, TOKEN_FILE

CLIENT_FILE = Path(__file__).parent / "secrets" / "oauth-client.json"


def main() -> None:
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_FILE), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline",
                                  authorization_prompt_message="Opening the browser for Google sign-in...",
                                  success_message="Done. You can close this tab.")
    if not creds.refresh_token:
        raise SystemExit("Google returned no refresh token; nothing saved.")
    TOKEN_FILE.write_text(creds.to_json())
    print(f"Saved {TOKEN_FILE.relative_to(Path(__file__).parent)}")
    if "--github" in sys.argv:
        subprocess.run(["gh", "secret", "set", "TASKBOT_GOOGLE_TOKEN_JSON"], input=creds.to_json(),
                       text=True, check=True, capture_output=True)
        print("Saved as the TASKBOT_GOOGLE_TOKEN_JSON GitHub secret")


if __name__ == "__main__":
    main()
