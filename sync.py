import os
import glob
import hashlib
import subprocess
from datetime import datetime
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Drive API scope
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# Project paths (Absolute paths for global CLI execution)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(BASE_DIR, 'token.json')
CREDS_PATH = os.path.join(BASE_DIR, 'credentials.json')
ENV_PATH = os.path.join(BASE_DIR, '.env')

# Load environment variables from .env if present
load_dotenv(ENV_PATH)

# Instance and directory settings
INSTANCE_NAME = os.getenv("INSTANCE_NAME", "GTNH 2.9-Beta2")
BACKUP_DIR = os.path.expanduser(
    os.getenv(
        "BACKUP_DIR",
        f"~/.local/share/PrismLauncher/instances/{INSTANCE_NAME}/.minecraft/backups/"
    )
)
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID", "1G13EJRk4Y4jGRz5dV-E-AmHZBi7dEHni")
MAX_REMOTE_BACKUPS = int(os.getenv("MAX_REMOTE_BACKUPS", "10"))

CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB chunks for progress tracking


def get_latest_backup(directory):
    """Finds the most recent .zip file in the backup directory."""
    list_of_files = glob.glob(os.path.join(directory, "*.zip"))
    if not list_of_files:
        print(f"No backups found in directory:\n{directory}")
        return None
    return max(list_of_files, key=os.path.getctime)


def generate_new_name(instance_name=None, now=None):
    """Generates the filename using the DD-MM-YY-InstanceName format."""
    target_instance = instance_name if instance_name is not None else INSTANCE_NAME
    current_time = now if now is not None else datetime.now()
    today = current_time.strftime("%d-%m-%y")
    clean_name = target_instance.replace(" ", "-")
    return f"{today}-{clean_name}.zip"


def compute_md5(file_path):
    """Computes the MD5 checksum of a local file."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def is_backup_already_uploaded(service, file_path, folder_id=None):
    """Checks if a file with the exact same MD5 checksum already exists in the Drive folder."""
    target_folder = folder_id if folder_id is not None else DRIVE_FOLDER_ID
    local_md5 = compute_md5(file_path)
    query = (
        f"'{target_folder}' in parents and "
        f"md5Checksum = '{local_md5}' and "
        f"trashed = false"
    )
    response = service.files().list(
        q=query,
        spaces='drive',
        fields='files(id, name, md5Checksum)',
        pageSize=1
    ).execute()
    files = response.get('files', [])
    if files:
        return files[0]
    return None


def authenticate_gdrive(token_path=None, creds_path=None):
    """Handles Google Drive OAuth2 authentication."""
    target_token = token_path if token_path is not None else TOKEN_PATH
    target_creds = creds_path if creds_path is not None else CREDS_PATH
    creds = None
    if os.path.exists(target_token):
        creds = Credentials.from_authorized_user_file(target_token, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(target_creds, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(target_token, 'w') as token:
            token.write(creds.to_json())

    return build('drive', 'v3', credentials=creds)


def upload_to_drive(service, file_path, new_name, folder_id=None):
    """Uploads the file to a specific Google Drive folder with chunked progress reporting."""
    target_folder = folder_id if folder_id is not None else DRIVE_FOLDER_ID
    file_metadata = {
        'name': new_name,
        'parents': [target_folder]
    }
    media = MediaFileUpload(
        file_path,
        mimetype='application/zip',
        chunksize=CHUNK_SIZE,
        resumable=True
    )

    print(f"\n[Cloud] Starting upload of {new_name}...")
    request = service.files().create(body=file_metadata, media_body=media, fields='id')

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            progress = int(status.progress() * 100)
            print(f"[Cloud] Upload progress: {progress}%")

    file_id = response.get('id')
    print(f"[Cloud] Success! Drive ID: {file_id}")
    return file_id


def notify_hyprland(title, message):
    """Sends a native desktop notification."""
    try:
        subprocess.run([
            "notify-send",
            "-t", "5000",
            "-a", "GTNH Cloud Sync",
            title,
            message
        ], check=False)
    except Exception as e:
        print(f"Error sending notification: {e}")


def list_remote_backups(service, folder_id=None):
    """Lists non-trashed zip backups in the Drive folder sorted newest first."""
    target_folder = folder_id if folder_id is not None else DRIVE_FOLDER_ID
    query = (
        f"'{target_folder}' in parents and "
        f"mimeType = 'application/zip' and "
        f"trashed = false"
    )
    results = []
    page_token = None

    while True:
        response = service.files().list(
            q=query,
            spaces='drive',
            fields='nextPageToken, files(id, name, createdTime, size)',
            orderBy='createdTime desc',
            pageSize=100,
            pageToken=page_token
        ).execute()

        results.extend(response.get('files', []))
        page_token = response.get('nextPageToken')
        if not page_token:
            break

    return results


def enforce_retention_policy(service, folder_id=None, max_backups=None):
    """Ensures at most max_backups remain in Drive; deletes older ones."""
    limit = max_backups if max_backups is not None else MAX_REMOTE_BACKUPS
    if limit <= 0:
        return []

    remote_files = list_remote_backups(service, folder_id=folder_id)
    if len(remote_files) <= limit:
        return []

    files_to_delete = remote_files[limit:]
    deleted = []

    print(f"\n[Retention] Found {len(remote_files)} backups (limit: {limit}). Cleaning up {len(files_to_delete)} old backup(s)...")
    for item in files_to_delete:
        file_id = item['id']
        file_name = item.get('name', 'unnamed')
        try:
            service.files().delete(fileId=file_id).execute()
            deleted.append(item)
            print(f"[Retention] Deleted old backup: {file_name} (ID: {file_id})")
        except Exception as e:
            print(f"[Retention] Error deleting old backup {file_name} ({file_id}): {e}")

    return deleted


def download_file_from_drive(service, file_id, destination_path):
    """Downloads a file from Google Drive to destination_path in chunks."""
    from googleapiclient.http import MediaIoBaseDownload
    import io

    request = service.files().get_media(fileId=file_id)
    os.makedirs(os.path.dirname(os.path.abspath(destination_path)), exist_ok=True)

    with open(destination_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request, chunksize=CHUNK_SIZE)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                print(f"[Download] Progress: {progress}%")

    print(f"[Download] Finished saving to {destination_path}")
    return destination_path


def main(backup_dir=None, drive_folder_id=None, instance_name=None, max_backups=None):
    """Main entry point for the backup synchronization workflow."""
    target_backup_dir = backup_dir if backup_dir is not None else BACKUP_DIR
    target_folder_id = drive_folder_id if drive_folder_id is not None else DRIVE_FOLDER_ID
    target_instance = instance_name if instance_name is not None else INSTANCE_NAME
    target_max = max_backups if max_backups is not None else MAX_REMOTE_BACKUPS

    print(f"Starting local scan in {target_backup_dir}...")
    latest_zip = get_latest_backup(target_backup_dir)

    if not latest_zip:
        notify_hyprland("Backup Failed", "No .zip file found in the instance folder.")
        return False

    new_filename = generate_new_name(instance_name=target_instance)
    print(f"-> Latest local backup found: {os.path.basename(latest_zip)}")

    service = authenticate_gdrive()

    existing_file = is_backup_already_uploaded(service, latest_zip, target_folder_id)
    if existing_file:
        existing_name = existing_file.get('name', new_filename)
        print(f"[Cloud] Skipping upload: backup already exists on Drive as '{existing_name}' (ID: {existing_file.get('id')}).")
        enforce_retention_policy(service, target_folder_id, target_max)
        notify_hyprland("Backup Already Synced", f"Latest backup is already on Google Drive ({existing_name}).")
        return True

    upload_to_drive(service, latest_zip, new_filename, target_folder_id)
    enforce_retention_policy(service, target_folder_id, target_max)

    notify_hyprland("Backup Completed!", f"File {new_filename} successfully uploaded to Google Drive.")
    print("\nProcess completed successfully!")
    return True


if __name__ == "__main__":
    main()
