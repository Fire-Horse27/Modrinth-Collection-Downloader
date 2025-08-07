# Modrinth Collection Downloader

## Purpose

The Modrinth Collection Downloader is a Python-based tool designed to automate the downloading and updating of content from Modrinth collections. It supports mods, datapacks, resource packs, and shader packs, ensuring compatibility with specified Minecraft versions and loaders.

---

## Features

- **Automated Downloads and Updates**  
  Fetches and updates projects from Modrinth collections.

- **Version Compatibility**  
  Ensures downloaded content matches specified Minecraft versions and loaders.

- **Fallback Handling**  
  If no exact version match is found, the script can fall back to a compatible version upon confirmation within a specified bound.

- **Manual Additions**  
  Detects and indexes manually added files.

- **Concurrency**  
  Utilizes threading and thread pools for efficient downloads.

- **Logging**  
  Maintains detailed logs for downloaded, updated, skipped, and failed projects.

---

## Requirements

- Python 3.6 or higher  
- Internet connection

---

## Installation

Download the Python script directly from the repository:

```bash
wget https://raw.githubusercontent.com/Fire-Horse27/Modrinth-Collection-Downloader/main/modrinth_collection_downloader.py -O modrinth_collection_downloader.py
```

Or copy and paste the code into a local python file.

Place script in the same folder as your mods folder.

## No Dependencies

No external dependencies are required beyond standard Python libraries.

## Usage Overview

Although the script includes command-line argument parsing, these values are overridden internally. You should modify the script directly to set your desired parameters.

To run the script:

```bash
python modrinth_collection_downloader.py
```

Downloaded projects will be saved in their corresponding folders located alongside ```modrinth_collection_downloader.py```

## Script Configuration

Inside the script, locate the section where `sys.argv` values are manually set. Update them as follows:

```python
sys.argv = [
    '-c', 'J7JO9I99',       # Replace with your desired collection ID
    '-v', '1.21.8',         # Replace with your target Minecraft version
    '-l', 'fabric',         # Replace with your preferred loader type
    '-f', '1.21.4'          # Optional: fallback version bound
]
```

## Arguments Explained

- **collection**  
  The Modrinth collection ID to download. This identifies the group of projects to fetch. To find this ID, navigate to the desired collection on the modrinth website and copy the unique ID located at the end of the URL: https://modrinth.com/collection/```J7JO9I99```

- **version**  
  The target Minecraft version (e.g., `1.21.8`). Used to filter compatible project versions.

- **loader**  
  The loader type (e.g., `fabric`, `forge`). Ensures compatibility with your modding environment.

- **fallback_bound** *(optional)*  
  A lower version bound to fall back to if no exact match is found. Helps maintain compatibility when newer versions are unavailable. (For example, most mods from 1.21.6 and 1.21.7 are compatible with 1.21.8. Thus, you'd want to set the fallback bound to 1.21.6) Fallback versions are not downloaded automatically. Confirmation will be asked before each one.

---

## How It Works

### Initialization

- Creates necessary directories and initializes log files.
- Scans for manually added files and updates the index.

### Collection Fetching

- Retrieves the specified Modrinth collection and its projects.

### Project Downloading

- Downloads compatible versions of projects based on the specified Minecraft version and loader.
- Handles dependencies recursively.

### Logging

- Logs events such as downloads, updates, skips, and failures.

### Concurrency

- Uses a thread pool for efficient downloading.

---

## Logs

Logs are stored in the `modrinth_collection_downloader` directory:

- `downloaded_projects_logs.txt`  
  Logs of successfully downloaded projects.

- `updated_projects_logs.txt`  
  Logs of updated projects.

- `no_version_found_for_projects_logs.txt`  
  Logs of projects with no compatible version found.

- `already_existing_projects_logs.txt`  
  Logs of projects that were skipped because they already exist.

---

## License

This project is licensed under the **GNU General Public License v3.0**.

You are free to use, modify, and distribute this software under the terms of the GPL. See the LICENSE file for full details.

Inspired and loosely structured from https://github.com/SushiSanCat/ModrinthCollectionDownloader/blob/main/modrinth_collection_downloader.py

---

Feel free to contribute or report issues on the [GitHub repository](https://github.com/Fire-Horse27/Modrinth-Collection-Downloader).
