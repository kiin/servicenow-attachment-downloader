# ServiceNow Attachment Downloader

Downloads attachments from a ServiceNow instance via the Attachment API.

## Download

Grab `sn-attachment-downloader.exe` from the [Releases](../../releases) page (or the latest build under the Actions tab).

## Setup

1. Put `sn-attachment-downloader.exe` in a folder.
2. Copy `.env.example` to `.env` in the same folder and fill in your instance, user and query.
   Leave `SN_PASSWORD` empty to be prompted at runtime.
3. Double-click the exe (or run it from a terminal).

## Settings

| Variable | Required | Default | Description |
|---|---|---|---|
| `SN_INSTANCE` | Yes | | Instance URL, e.g. `https://yourinstance.service-now.com` |
| `SN_USERNAME` | Yes | | ServiceNow user |
| `SN_PASSWORD` | Yes | | Password (prompted if not set) |
| `DOWNLOAD_DIR` | No | `~/Downloads/ServiceNowAttachments` | Output folder |
| `QUERY` | No | all attachments | Encoded query on `sys_attachment`, e.g. `table_name=incident` |
| `LIMIT` | No | `100` | Page size per request |
| `MAX_RECORDS` | No | `0` (no cap) | Stop after this many attachments |
| `NO_PAUSE` | No | | Set to skip "Press Enter to close" |

Real environment variables take precedence over `.env`.

## Build locally

```powershell
pip install -r requirements.txt pyinstaller
python -m PyInstaller --onefile --console --clean --name sn-attachment-downloader download_attachments.py
```

## Releasing

Pushes to `main` build the exe as a workflow artifact. Pushing a tag like `v1.0.0` also publishes a GitHub Release with the exe attached.
