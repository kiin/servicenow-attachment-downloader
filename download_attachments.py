import os
import re
import sys
import getpass
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv


# ==========================================
# Paths
# ==========================================

def app_dir() -> Path:
    """Folder containing the .exe when frozen by PyInstaller, else this script's folder."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


# Load .env from next to the .exe / script, regardless of the current directory
load_dotenv(app_dir() / ".env")


# ==========================================
# Configuration
# ==========================================

def get_setting(name, prompt, secret=False):
    """Read a setting from the environment / .env, or ask for it interactively."""
    value = os.getenv(name, "").strip()
    if value:
        return value
    if not sys.stdin or not sys.stdin.isatty():
        raise SystemExit(f"Missing required setting: {name} (set it in .env or the environment)")
    value = (getpass.getpass(prompt) if secret else input(prompt)).strip()
    if not value:
        raise SystemExit(f"{name} is required.")
    return value


def normalise_instance(instance):
    instance = instance.strip().rstrip("/")
    if not instance.startswith(("http://", "https://")):
        instance = "https://" + instance
    return instance


INSTANCE = normalise_instance(get_setting("SN_INSTANCE", "ServiceNow instance URL: "))
USERNAME = get_setting("SN_USERNAME", "Username: ")
PASSWORD = get_setting("SN_PASSWORD", "Password: ", secret=True)

DOWNLOAD_DIR = os.path.expanduser(
    os.getenv("DOWNLOAD_DIR", "~/Downloads/ServiceNowAttachments")
)

# ServiceNow encoded query against sys_attachment, e.g. table_name=incident
QUERY = os.getenv("QUERY", "")

# Records per request (page size)
LIMIT = int(os.getenv("LIMIT", 100))

# Stop after this many attachments in total (0 = no limit)
MAX_RECORDS = int(os.getenv("MAX_RECORDS", 0))


# ==========================================
# Setup
# ==========================================

session = requests.Session()
session.auth = HTTPBasicAuth(USERNAME, PASSWORD)
session.headers.update({"Accept": "application/json"})

# Characters Windows does not allow in file names
INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_file_name(name):
    name = os.path.basename(name.replace("\\", "/"))
    name = INVALID_CHARS.sub("_", name).strip(" .")
    return name or "unnamed"


# ==========================================
# Get attachment list (paged)
# ==========================================

def get_attachments():

    url = f"{INSTANCE}/api/now/attachment"

    # Stable ordering so paging doesn't skip or repeat records
    query = f"{QUERY}^ORDERBYsys_id" if QUERY else "ORDERBYsys_id"

    attachments = []
    offset = 0

    while True:
        params = {
            "sysparm_query": query,
            "sysparm_limit": LIMIT,
            "sysparm_offset": offset,
            "sysparm_fields": "sys_id,file_name",
        }

        response = session.get(url, params=params, timeout=60)
        response.raise_for_status()

        data = response.json().get("result", [])
        attachments.extend(data)

        print(f"Retrieved {len(attachments)} attachments...")

        if MAX_RECORDS and len(attachments) >= MAX_RECORDS:
            return attachments[:MAX_RECORDS]

        if len(data) < LIMIT:
            return attachments

        offset += LIMIT


# ==========================================
# Download attachment
# ==========================================

def download_attachment(attachment):
    """Returns True on success (or already downloaded), False on failure."""

    sys_id = attachment["sys_id"]
    file_name = safe_file_name(attachment.get("file_name", ""))

    # Include sys_id to prevent filename collisions
    destination = os.path.join(DOWNLOAD_DIR, f"{sys_id}_{file_name}")

    if os.path.exists(destination):
        print(f"Skipped (already exists): {file_name}")
        return True

    url = f"{INSTANCE}/api/now/attachment/{sys_id}/file"
    partial = destination + ".part"

    try:
        # The file endpoint returns binary content, not JSON
        response = session.get(url, stream=True, timeout=120, headers={"Accept": "*/*"})
        response.raise_for_status()

        with open(partial, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)

        # Only move into place once complete, so failed runs leave no half files
        os.replace(partial, destination)
        print(f"Downloaded: {file_name}")
        return True

    except (requests.RequestException, OSError) as error:
        print(f"Failed: {file_name} - {error}")
        if os.path.exists(partial):
            os.remove(partial)
        return False


# ==========================================
# Main
# ==========================================

def main():

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    print(f"Instance: {INSTANCE}")
    print(f"Saving to: {DOWNLOAD_DIR}\n")
    print("Querying ServiceNow attachments...")

    try:
        attachments = get_attachments()
    except requests.HTTPError as error:
        status = error.response.status_code if error.response is not None else "?"
        if status == 401:
            print("Login failed (401): check SN_USERNAME / SN_PASSWORD.")
        elif status == 403:
            print("Access denied (403): the user needs read access to sys_attachment.")
        else:
            print(f"Request failed ({status}): {error}")
        return 1
    except requests.RequestException as error:
        print(f"Could not reach {INSTANCE}: {error}")
        return 1

    print(f"\nFound {len(attachments)} attachments.\n")

    failures = 0
    for index, attachment in enumerate(attachments, start=1):
        print(f"[{index}/{len(attachments)}] ", end="")
        if not download_attachment(attachment):
            failures += 1

    print(f"\nDownload completed. {len(attachments) - failures} ok, {failures} failed.")
    return 1 if failures else 0


def pause_if_double_clicked():
    """Keep the console window open when the .exe is launched from Explorer."""
    if getattr(sys, "frozen", False) and sys.stdin and sys.stdin.isatty() \
            and not os.getenv("NO_PAUSE"):
        input("\nPress Enter to close...")


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    except KeyboardInterrupt:
        print("\nCancelled.")
    except SystemExit as exit_error:
        print(exit_error)
    finally:
        pause_if_double_clicked()
    sys.exit(exit_code)
