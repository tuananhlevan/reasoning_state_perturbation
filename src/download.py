#!/usr/bin/env python3
"""Discover or download one unprocessed Drive archive."""
import argparse, hashlib, json, re
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from authenticate import get_credentials, load_env
FOLDER_MIME = "application/vnd.google-apps.folder"
ARCHIVE_SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")

def folder_id(value):
    parsed = urlparse(value); ids = parse_qs(parsed.query).get("id", [])
    if ids: return ids[0]
    parts = [part for part in parsed.path.split("/") if part]
    if "folders" in parts and parts.index("folders") + 1 < len(parts): return parts[parts.index("folders") + 1]
    if re.fullmatch(r"[A-Za-z0-9_-]+", value): return value
    raise ValueError("Expected a Drive folder URL or ID")

def service():
    from googleapiclient.discovery import build
    return build("drive", "v3", credentials=get_credentials(), cache_discovery=False)

def list_files(client, root):
    folders, files = [root], []
    while folders:
        parent, page = folders.pop(), None
        while True:
            result = client.files().list(q=f"'{parent}' in parents and trashed = false", fields="nextPageToken,files(id,name,mimeType,modifiedTime,md5Checksum,size)", pageSize=1000, pageToken=page, supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
            for item in result.get("files", []):
                folders.append(item["id"]) if item["mimeType"] == FOLDER_MIME else files.append(item)
            page = result.get("nextPageToken")
            if not page: break
    return sorted(files, key=lambda item: (item["name"], item["id"]))

def version(item): return item.get("md5Checksum") or f"{item.get('modifiedTime', '')}:{item.get('size', '')}"
def item_key(item): return hashlib.sha256(f"{item['id']}\0{version(item)}".encode()).hexdigest()
def successful(path):
    try: return json.loads(path.read_text(encoding="utf-8")).get("status") == "success"
    except (OSError, json.JSONDecodeError, AttributeError): return False

def discover(folder, checkpoints):
    all_files = list_files(service(), folder_id(folder))
    pending = [item for item in all_files if item["name"].lower().endswith(ARCHIVE_SUFFIXES) and not successful(checkpoints / "files" / f"{item_key(item)}.json")]
    return pending, len(all_files)

def download_file(item, destination):
    from googleapiclient.http import MediaIoBaseDownload
    destination.parent.mkdir(parents=True, exist_ok=True); partial = destination.with_suffix(".part")
    with partial.open("wb") as handle:
        loader, done = MediaIoBaseDownload(handle, service().files().get_media(fileId=item["id"], supportsAllDrives=True)), False
        while not done: _, done = loader.next_chunk()
    if not partial.stat().st_size: raise ValueError(f"Empty download: {item['name']}")
    partial.replace(destination)

def main():
    load_env(Path(".env"))
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("folder"); parser.add_argument("destination", type=Path); parser.add_argument("--checkpoint-dir", type=Path, default=Path("outputs/checkpoints")); args = parser.parse_args()
    pending, scanned = discover(args.folder, args.checkpoint_dir)
    if not pending: print(f"Scanned {scanned}; no pending archives."); return 0
    download_file(pending[0], args.destination); print(json.dumps(pending[0])); return 0
if __name__ == "__main__": raise SystemExit(main())
