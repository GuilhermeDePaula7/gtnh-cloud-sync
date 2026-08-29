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
* **☁️ Google Drive Integration:** Utilizes Google OAuth2 for secure, headless uploads to a specific Drive folder.
* **🔔 Native Notifications:** Integrates with `libnotify` to trigger desktop pop-ups (compatible with Hyprland, Sway, etc.).

---

## 🛠️ Installation & Setup

### 1. Clone the repository
```bash
git clone [https://github.com/GuilhermeDePaula7/gtnh-cloud-sync.git](https://github.com/GuilhermeDePaula7/gtnh-cloud-sync.git)
cd gtnh-cloud-sync

2. Set up the Environment
Bash

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

3. Configure Google Drive API

    Go to the Google Cloud Console.

    Create a new project and enable the Google Drive API.

    Go to OAuth consent screen, select External, and add your email as a Test User.

    Go to Credentials > Create Credentials > OAuth client ID > Desktop app.

    Download the JSON file, rename it to credentials.json, and place it in the root of this project.

4. Update Script Variables

Open sync.py and replace DRIVE_FOLDER_ID with the actual ID of your target Google Drive folder. You can also adjust the INSTANCE_NAME if your Prism Launcher folder is named differently.
5. Set up the CLI Command

Create an executable script in your local binaries folder (e.g., ~/.local/bin/gtnh) to trigger the Python script globally:
Bash

#!/bin/bash
if [ "$1" == "backup" ] && [ "$2" == "start" ]; then
    ~/path/to/gtnh-cloud-sync/venv/bin/python ~/path/to/gtnh-cloud-sync/sync.py
else
    echo "Usage: gtnh backup start"
fi

Run chmod +x ~/.local/bin/gtnh to make it executable.
💻 Usage

Run the following command from anywhere in your terminal:
Bash

gtnh backup start

    Note: The first time you run this command, a browser window will open asking you to authenticate with your Google account. A token.json file will be generated locally, and all future backups will run silently in the background.
