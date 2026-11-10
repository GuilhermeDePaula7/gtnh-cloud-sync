# 🚀 GTNH Cloud Sync

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white)
![Google Drive](https://img.shields.io/badge/Google_Drive-API-1FA463?style=for-the-badge&logo=google-drive&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-Arch%20%2F%20CachyOS-1793d1?style=for-the-badge&logo=arch-linux&logoColor=white)

A lightweight, automated Command Line Interface (CLI) tool designed to securely back up local Prism Launcher Minecraft instances (specifically GregTech: New Horizons) directly to Google Drive. 

Built for Linux environments, it features automated timestamp formatting, data retention, and native desktop notifications.

---

## ✨ Features

* **🔍 Automated Discovery:** Scans the Prism Launcher directory for the most recent `.zip` backup.
* **🏷️ Smart Renaming:** Automatically formats the uploaded file as `DD-MM-YY-InstanceName.zip`.
* **⚡ Duplicate Detection:** Computes local file MD5 hash to prevent duplicate uploads to Google Drive.
* **☁️ Google Drive Integration:** Utilizes Google OAuth2 for secure uploads with chunked progress tracking.
* **🗑️ Automatic Retention:** Keeps only the last `N` backups on Google Drive, automatically purging older ones to save storage.
* **🔔 Native Notifications:** Integrates with `libnotify` to trigger desktop pop-ups (compatible with Hyprland, Sway, etc.).

---

## 🛠️ Installation & Setup

### 1. Clone the repository
```bash
git clone https://github.com/GuilhermeDePaula7/gtnh-cloud-sync.git
cd gtnh-cloud-sync
```

### 2. Set up the Environment
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Google Drive API
1. Go to the Google Cloud Console.
2. Create a new project and enable the Google Drive API.
3. Go to **OAuth consent screen**, select **External**, and add your email as a **Test User**.
4. Go to **Credentials > Create Credentials > OAuth client ID > Desktop app**.
5. Download the JSON file, rename it to `credentials.json`, and place it in the root of this project.

### 4. Configure Environment Variables (`.env`)
Copy `.env.example` to `.env` and fill in your Google Drive folder ID and Prism Launcher instance name:
```bash
cp .env.example .env
```

### 5. Install the CLI
Install the package in editable mode within your environment:
```bash
pip install -e .
```
This registers the `gtnh` command directly. (Alternatively, you can install globally with `pipx install .` or link `venv/bin/gtnh` into `~/.local/bin/`).

---

## 💻 Usage

```bash
# Upload the latest backup to Google Drive (with duplicate check & retention)
gtnh backup push
# (alias: gtnh backup start)

# List all backups available in Google Drive
gtnh backup list

# Download the latest backup from Google Drive to your instance folder
gtnh backup pull

# Download a specific backup by file ID or name
gtnh backup pull --id "<DRIVE_FILE_ID>"
gtnh backup pull --name "10-11-26-GTNH-2.9-Beta2.zip"

# Download to a custom directory
gtnh backup pull -o ~/Downloads

# List local Prism Launcher instances
gtnh prism instances

# Check current post-exit hook status
gtnh prism status

# Automatically configure Prism Launcher to backup every time you close Minecraft
gtnh prism install-hook
```

> **Note:** The first time you run a command requiring Google Drive access, a browser window will open asking you to authenticate. A `token.json` file will be generated locally, and all future commands will run silently in the background.

---

## 🎮 Prism Launcher Auto-Sync Hook

To automatically trigger a backup to Google Drive every time you close GregTech: New Horizons:

```bash
gtnh prism install-hook
```

This writes `PostExitCommand=gtnh backup push` into the instance's `instance.cfg`. When the game exits, Prism Launcher executes the command in the background, syncing your world and notifying you natively via Hyprland/Sway.

---

## 🧪 Running Tests

To run the automated test suite:
```bash
./venv/bin/pytest -v
```
