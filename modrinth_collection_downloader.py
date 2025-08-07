import sys
import argparse
import json
import os
import time
import random
import re
import socket
import traceback
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib import request, error

# Simulated CLI arguments for testing
sys.argv = [
    'download_modrinth.py',
    '-v', '1.21.8',
    '-l', 'fabric',
    '-c', 'J7JO9I99', #'xgQxKt59',
    '-f', '1.21.4'
]

LOG_DIR = "modrinth_collection_downloader"
INDEX_FILES = {
    "mod": "mods_index.json",
    "datapack": "datapacks_index.json",
    "resourcepack": "resourcepacks_index.json",
    "shaderpack": "shaderpacks_index.json",
    "shader": "shaderpacks_index.json",
}
LOG_FILES = {
    "downloaded": "downloaded_projects_logs.txt",
    "updated": "updated_projects_logs.txt",
    "no_version": "no_version_found_for_projects_logs.txt",
    "skipped": "already_existing_projects_logs.txt",
}

print_queue = queue.Queue()
input_queue = queue.Queue()
log_queue = queue.Queue()

def log_dispatcher():
    while True:
        try:
            item = log_queue.get(timeout=0.1)
            if item is None:
                break
            log_type, message = item
            path = os.path.join(LOG_DIR, LOG_FILES[log_type])
            with open(path, "a", encoding="utf-8") as f:
                # Optional: count lines if you want numbered entries
                count = sum(1 for _ in open(path, "r", encoding="utf-8")) if os.path.exists(path) else 0
                f.write(f"{count + 1}. {message}\n")
            log_queue.task_done()
        except queue.Empty:
            continue

def console_dispatcher():
    while True:
        # Prioritize input prompts
        try:
            prompt, response_queue = input_queue.get_nowait()
            response = input(prompt)
            response_queue.put(response)
            input_queue.task_done()
        except queue.Empty:
            try:
                msg = print_queue.get(timeout=0.1)
                if msg is None:
                    break
                print(msg)
                print_queue.task_done()
            except queue.Empty:
                continue

def safe_print(msg):
    print_queue.put(msg)

def safe_input(prompt):
    response_queue = queue.Queue()
    input_queue.put((prompt, response_queue))
    return response_queue.get()

class ModrinthClient:
    BASE_URL = "https://api.modrinth.com"
    MAX_RETRIES = 5
    RATE_LIMIT_DELAY = (0.4, 1.2)  # ✅ Respect Modrinth's pacing
    TIMEOUT = 10  # seconds

    def _request_with_retries(self, url, action="GET", dest=None):
        delay = random.uniform(*self.RATE_LIMIT_DELAY)
        for attempt in range(self.MAX_RETRIES):
            try:
                if action == "GET":
                    with request.urlopen(url, timeout=self.TIMEOUT) as response:
                        time.sleep(delay)
                        return json.loads(response.read())
                elif action == "DOWNLOAD":
                    request.urlretrieve(url, dest)
                    time.sleep(delay)
                    return
            except error.HTTPError as e:
                if e.code == 429:
                    wait = int(e.headers.get("Retry-After", 2))
                    safe_print(f"[⏳ Throttled] Retry-After: {wait}s | Attempt {attempt + 1}")
                    time.sleep(wait)
                    delay = random.uniform(*self.RATE_LIMIT_DELAY)  # Reset delay
                elif e.code == 408:
                    safe_print(f"[⌛ Server Timeout] HTTP 408 for {url} | Attempt {attempt + 1}")
                    delay = max(0.1, delay / 2)  # Reduce delay to send faster
                    time.sleep(self._retry_backoff(attempt))
                else:
                    safe_print(f"[❌ HTTP {action}] {e.code} for {url} | Attempt {attempt + 1}")
                    break
            except error.URLError as e:
                if isinstance(e.reason, socket.timeout):
                    safe_print(f"[⌛ Client Timeout] {url} | Attempt {attempt + 1}")
                else:
                    safe_print(f"[🌐 Network {action}] {e.reason} | Attempt {attempt + 1}")
                time.sleep(self._retry_backoff(attempt))
        safe_print(f"[🚫 Failed] {action} failed for {url} after {self.MAX_RETRIES} attempts.")
        return None

    def _retry_backoff(self, attempt):
        return min(2 ** attempt, 30)  # ✅ Exponential backoff capped at 30s

    def get(self, endpoint):
        return self._request_with_retries(self.BASE_URL + endpoint, action="GET")

    def download_file(self, url, filename):
        self._request_with_retries(url, action="DOWNLOAD", dest=filename)

    def get_mod_version(self, mod_id):
        return self.get(f"/v2/project/{mod_id}/version")

    def get_collection(self, collection_id):
        return self.get(f"/v3/collection/{collection_id}")

    def get_mod_details(self, mod_id):
        return self.get(f"/v2/project/{mod_id}")

modrinth = ModrinthClient()

def initialize_logs():
    os.makedirs(LOG_DIR, exist_ok=True)
    for name in LOG_FILES.values():
        open(os.path.join(LOG_DIR, name), "w", encoding="utf-8").close()

def log_event(log_type, message):
    log_queue.put((log_type, message))

def normalize_filename(name):
    return re.sub(r"[^\w\-+.]", "_", name)

def load_index(index_type):
    filename = INDEX_FILES.get(index_type)
    if not filename:
        raise ValueError(f"Unknown index type: {index_type}")
    path = os.path.join(LOG_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_index(index_type, index):
    path = os.path.join(LOG_DIR, INDEX_FILES[index_type])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

def parse_version(v):
    return tuple(int(part) for part in v.split(".") if part.isdigit())

def scan_manual_additions(index_type):
    index = load_index(index_type)
    directory = resolve_target_directory(index_type)
    os.makedirs(directory, exist_ok=True)

    # Get actual files in directory
    actual_files = {
        fname for fname in os.listdir(directory)
        if fname.endswith(".jar") or fname.endswith(".zip")
    }

    # Remove stale entries from index
    stale_files = [fname for fname in index if fname not in actual_files]
    for stale in stale_files:
        safe_print(f"[🧹 REMOVED STALE] {stale} no longer exists in folder.")
        del index[stale]

    # Add new files not in index
    for fname in sorted(actual_files):
        if fname not in index:
            safe_print(f"[📦 MANUAL DETECTED] {fname} not in index.")
            mod_id = safe_input(f"🔍 Enter Modrinth project ID for '{fname}' (or leave blank to skip): ").strip()
            if mod_id:
                index[fname] = mod_id
                safe_print(f"[✅ ADDED  ] {fname} → {mod_id}")
            else:
                safe_print(f"[⏭️ SKIPPED] {fname} left unindexed.")

    save_index(index_type, index)

def format_version(v):
    """Formats a version tuple like (1, 21, 8) into a string '1.21.8'."""
    return ".".join(map(str, v))

def gv(v, target_version):
    # Returns the highest supported Minecraft version for sorting and display
    game_versions = [
        parse_version(ver)
        for ver in v.get("game_versions", [])
        if parse_version(ver) <= target_version
    ]
    return max(game_versions, default=None)

def is_compatible(v, loader, fallback, target, project_type):
    game_versions = [parse_version(ver) for ver in v.get("game_versions", [])]
    version_ok = any(
        fallback <= gv_ <= target
        for gv_ in game_versions
    )

    loaders = v.get("loaders", [])
    loader_ok = (
        project_type != "mod" or
        loader is None or
        loader in loaders or
        any(l in loaders for l in ["minecraft", "datapack"])
    )

    return version_ok and loader_ok

def get_latest_version(mod_id, mod_name, target_version, loader, fallback_bound, project_type):
    versions = modrinth.get_mod_version(mod_id)
    if not versions:
        safe_print(f"[⚠️ NOTICE] No versions found for '{mod_name}' (ID: {mod_id}).")
        return None, False

    compatible = [v for v in versions if is_compatible(v, loader, fallback_bound, target_version, project_type)]
    if not compatible:
        valid_versions = [v for v in versions if gv(v, target_version) is not None]
        if not valid_versions:
            return None, False
        return max(valid_versions, key=lambda v: gv(v, target_version)), False

    exact = next((v for v in compatible if target_version in [parse_version(ver) for ver in v.get("game_versions", [])]), None)
    if exact:
        return exact, True

    fallback = max(compatible, key=lambda v: gv(v, target_version))
    return fallback, True

def resolve_target_directory(project_type):
    p_type = "shaderpack" if project_type == "shader" else project_type
    return os.path.join(os.getcwd(), p_type + "s")

def should_use_fallback(version, target_version, mod_name, filename):
    fallback_display = format_version(gv(version, target_version))
    target_display = format_version(target_version)

    prompt = (
        f"[⚠️ FALLBCK] No exact match for '{mod_name}' "
        f"(target: {target_display}). Use fallback version {filename} "
        f"(supports Minecraft {fallback_display})? [y/N]: "
    )
    return safe_input(prompt).strip().lower() == "y"

def download_project(mod_id, args, seen_mods, file_lock):
    if mod_id in seen_mods:
        return
    seen_mods.add(mod_id)

    mod_details = modrinth.get_mod_details(mod_id)
    mod_name = mod_details.get("title", mod_id) if mod_details else mod_id
    project_type = mod_details.get("project_type")

    version, success = get_latest_version(mod_id, mod_name, args.version, args.loader, args.fallback_bound, project_type)
    if version and "datapack" in version.get("loaders", []):
        project_type = "datapack"
    if not success:
        versions = version.get("game_versions", [])
        closest_version = (format_version(max(map(parse_version, versions))) if versions else None)
        msg = f"[❌ FAILED ] No version found | Project: {mod_name} | Type: {project_type} | ID: {mod_id} | Closest Version {closest_version}"
        safe_print(msg)
        log_event("no_version", msg)
        return

    file = next((f for f in version.get("files", []) if f.get("primary")), None)
    if not file:
        safe_print(f"[❌ ERROR  ] No primary file found | Project: {mod_name} | Type: {project_type} | ID: {mod_id}")
        return

    filename = normalize_filename(file["filename"])
    target_dir = resolve_target_directory(project_type)
    if not target_dir:
        safe_print(f"[⚠️ SKIPPED] Project: {mod_name} | Type: {project_type} | Reason: Not included or unknown type")
        return

    # Prep work outside the lock
    os.makedirs(target_dir, exist_ok=True)
    filepath = os.path.join(target_dir, filename)
    game_versions = [parse_version(ver) for ver in version.get("game_versions", [])]

    # Lock the index lifecycle
    with file_lock:
        index = load_index(project_type)
    existing_id = index.get(filename)
    old_filename = next((fname for fname, mid in index.items() if mid == mod_id and fname != filename), None)

    # Fallback check
    if args.version not in game_versions and existing_id != mod_id:
        if not should_use_fallback(version, args.version, mod_name, filename):
            closest_version = format_version(max(game_versions))
            msg = f"[❌ FAILED ] Fallback declined for '{mod_name} | Type: {project_type} | ID: {mod_id} | Closest Version {closest_version}"
            safe_print(msg)
            log_event("no_version", msg)
            return

    # If already present, skip
    if existing_id == mod_id:
        msg = f"[⏩ SKIPPED] Already exists | Project: {mod_name} | Type: {project_type} | ID: {mod_id} | File: {filename}"
        safe_print(msg)
        log_event("skipped", msg)
        return

    # Outside the lock: download and file ops
    safe_print(f"{'[💹 UPDATE ]' if old_filename else '[✅ DWNLDNG]'} {filename} → {target_dir} | Type: {project_type}")
    modrinth.download_file(file["url"], filepath)

    if old_filename:
        old_path = os.path.join(target_dir, old_filename)
        if os.path.exists(old_path):
            safe_print(f"[🚫 REMOVING OLD VERSION] {old_filename} | Type: {project_type}")
            os.remove(old_path)

    # Final index update under lock
    with file_lock:
        index = load_index(project_type)  # Reload in case of concurrent changes
        if old_filename:
            index.pop(old_filename, None)
            log_event("updated",
                      f"[💹 UPDATED] Project updated | Project: {mod_name} | Type: {project_type} | ID: {mod_id} | File: {filename}")
        else:
            log_event("downloaded",
                      f"[✅ DWNLDNG] Project downloaded | Project: {mod_name} | Type: {project_type} | ID: {mod_id} | File: {filename}")

        index[filename] = mod_id
        save_index(project_type, index)

    # ✅ Recursively download required dependencies
    for dep in version.get("dependencies", []):
        if dep["dependency_type"] == "required":
            download_project(dep["project_id"], args, seen_mods, file_lock)

def main():
    parser = argparse.ArgumentParser(description="Download and update Modrinth collection content.")
    parser.add_argument("-c", "--collection", required=True)
    parser.add_argument("-v", "--version", type=parse_version, required=True)
    parser.add_argument("-l", "--loader", required=True)
    parser.add_argument("-f", "--fallback-bound", type=parse_version)
    args = parser.parse_args()

    dispatcher_thread = threading.Thread(target=console_dispatcher, daemon=True)
    dispatcher_thread.start()

    log_thread = threading.Thread(target=log_dispatcher, daemon=True)
    log_thread.start()

    file_lock = threading.Lock()

    # ✅ Ensure all target directories exist
    for project_type in ("mod", "datapack", "resourcepack", "shaderpack"):
        os.makedirs(resolve_target_directory(project_type), exist_ok=True)

    initialize_logs()

    # ✅ Scan for manually added content in all directories
    for project_type in ("mod", "datapack", "resourcepack", "shaderpack"):
        scan_manual_additions(project_type)

    collection = modrinth.get_collection(args.collection)
    if not collection:
        safe_print(f"[❌ ERROR] Collection ID '{args.collection}' not found.")
        return

    mods = collection.get("projects", [])
    safe_print(f"[📋 COLLECTION] Projects in collection: {mods}")
    seen_mods = set()

    # ✅ Use thread pool for concurrent downloads
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(lambda mod_id: download_project(mod_id, args, seen_mods, file_lock), mods)
    # for mod_id in mods:
    #     download_project(mod_id, args, seen_mods)

    print_queue.put(None)
    dispatcher_thread.join()

    log_queue.put(None)
    log_thread.join()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        tb = traceback.extract_tb(e.__traceback__)
        filenamed, lineno, func, text = tb[-1]
        print(f"[🔥 UNEXPECTED ERROR] {e} (Line {lineno} in {filenamed})")
    finally:
        input("\n✅ All tasks finished. Press Enter to exit...")