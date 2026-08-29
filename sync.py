import os
import glob
import subprocess
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Drive API scope
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# Instance and directory settings
INSTANCE_NAME = "GTNH 2.9-Beta2"
BACKUP_DIR = os.path.expanduser(f"~/.local/share/PrismLauncher/instances/{INSTANCE_NAME}/.minecraft/backups/")
DRIVE_FOLDER_ID = "COLE_O_SEU_ID_AQUI" # Keep your ID here

def get_latest_backup(directory):
    """Finds the most recent .zip file in the backup directory."""
    list_of_files = glob.glob(f"{directory}/*.zip")
    if not list_of_files:
        print(f"No backups found in directory:\n{directory}")
        return None
    return max(list_of_files, key=os.path.getctime)

def generate_new_name():
    """Generates the filename using the DD-MM-YY-InstanceName format."""
    today = datetime.now().strftime("%d-%m-%y")
    clean_name = INSTANCE_NAME.replace(" ", "-")
    return f"{today}-{clean_name}.zip"

def authenticate_gdrive():
    """Handles Google Drive OAuth2 authentication."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
    return build('drive', 'v3', credentials=creds)

def upload_to_drive(service, file_path, new_name):
    """Uploads the file to a specific Google Drive folder."""
    file_metadata = {
        'name': new_name,
        'parents': [DRIVE_FOLDER_ID]
    }
    media = MediaFileUpload(file_path, mimetype='application/zip', resumable=True)
    
    print(f"\n[Cloud] Starting upload of {new_name}...")
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"[Cloud] Success! Drive ID: {file.get('id')}")

def notify_hyprland(title, message):
    """Sends a native desktop notification."""
    try:
        subprocess.run([
            "notify-send", 
            "-t", "5000", 
            "-a", "GTNH Cloud Sync", 
            title, 
            message
        ])
    except Exception as e:
        print(f"Error sending notification: {e}")

if __name__ == "__main__":
    print("Starting local scan...")
    latest_zip = get_latest_backup(BACKUP_DIR)
    
    if latest_zip:
        new_filename = generate_new_name()
        print(f"-> Latest local backup found: {os.path.basename(latest_zip)}")
        
        service = authenticate_gdrive()
        upload_to_drive(service, latest_zip, new_filename)
        
        notify_hyprland("Backup Completed!", f"File {new_filename} successfully uploaded to Google Drive.")
        print("\nProcess completed successfully!")
    else:
        notify_hyprland("Backup Failed", "No .zip file found in the instance folder.")
