import os
import glob
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import subprocess

DRIVE_FOLDER_ID = "1G13EJRk4Y4jGRz5dV-E-AmHZBi7dEHni"

# Escopo restrito: o script só pode interagir com arquivos que ele mesmo criar
SCOPES = ['https://www.googleapis.com/auth/drive.file']
INSTANCE_NAME = "GTNH 2.9-Beta2"
BACKUP_DIR = os.path.expanduser(f"~/.local/share/PrismLauncher/instances/{INSTANCE_NAME}/.minecraft/backups/")

def get_latest_backup(directory):
    list_of_files = glob.glob(f"{directory}/*.zip")
    if not list_of_files:
        print(f"Nenhum backup encontrado no diretório:\n{directory}")
        return None
    return max(list_of_files, key=os.path.getctime)

def generate_new_name():
    today = datetime.now().strftime("%d-%m-%y")
    clean_name = INSTANCE_NAME.replace(" ", "-")
    return f"{today}-{clean_name}.zip"

def authenticate_gdrive():
    creds = None
    # Verifica se já logamos antes (token salvo localmente)
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # Se não tem token ou expirou, abre o navegador para o login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Salva o token para não pedir login na próxima vez
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
    return build('drive', 'v3', credentials=creds)

def upload_to_drive(service, file_path, new_name):
    # O 'name' aqui altera o nome do arquivo diretamente na nuvem
    file_metadata = {
        'name': new_name,
        'parents': [DRIVE_FOLDER_ID]
    }
    media = MediaFileUpload(file_path, mimetype='application/zip', resumable=True)
    
    print(f"\n[Cloud] Iniciando upload de {new_name} para a pasta específica...")
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"[Cloud] Sucesso! ID no Drive: {file.get('id')}")

def notify_hyprland(title, message):
    """Envia uma notificação nativa para o desktop"""
    try:
        # -t 5000 define a duração para 5 segundos
        subprocess.run([
            "notify-send", 
            "-t", "5000", 
            "-a", "GTNH Cloud Sync", 
            title, 
            message
        ])
    except Exception as e:
        print(f"Erro ao enviar notificação: {e}")

if __name__ == "__main__":
    print("Iniciando varredura local...")
    latest_zip = get_latest_backup(BACKUP_DIR)
    
    if latest_zip:
        new_filename = generate_new_name()
        print(f"-> Último backup local encontrado: {os.path.basename(latest_zip)}")
        
        # Inicia a conexão com o Google
        service = authenticate_gdrive()
        upload_to_drive(service, latest_zip, new_filename)

if __name__ == "__main__":
    print("Iniciando varredura local...")
    latest_zip = get_latest_backup(BACKUP_DIR)
    
    if latest_zip:
        new_filename = generate_new_name()
        print(f"-> Último backup local encontrado: {os.path.basename(latest_zip)}")
        
        # Inicia a conexão e o upload
        service = authenticate_gdrive()
        upload_to_drive(service, latest_zip, new_filename)
        
        # Dispara a notificação de sucesso no Hyprland
        notify_hyprland("Backup Concluído!", f"Arquivo {new_filename} enviado para o Drive com sucesso.")
        print("\nProcesso concluído com sucesso!")
    else:
        # Notifica caso não encontre nenhum arquivo
        notify_hyprland("Falha no Backup", "Nenhum arquivo .zip encontrado na pasta da instância.")
