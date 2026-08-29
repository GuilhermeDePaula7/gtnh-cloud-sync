import os
import glob
from datetime import datetime

# Caminho padrão do Prism Launcher no Arch Linux
INSTANCE_NAME = "GTNH"
BACKUP_DIR = os.path.expanduser(f"~/.local/share/PrismLauncher/instances/{GTNH2.9-Beta2}/.minecraft/backups/")

def get_latest_backup(directory):
    """Procura o arquivo .zip mais recente na pasta de backups."""
    list_of_files = glob.glob(f"{directory}/*.zip")
    if not list_of_files:
        print("Nenhum backup encontrado no diretório!")
        return None
    
    # Retorna o arquivo com a data de criação (ctime) mais recente
    latest_file = max(list_of_files, key=os.path.getctime)
    return latest_file

def generate_new_name():
    """Gera o nome no padrão DD-MM-AA-NomeDaInstancia"""
    today = datetime.now().strftime("%d-%m-%y")
    return f"{today}-{INSTANCE_NAME}.zip"

if __name__ == "__main__":
    print("Iniciando varredura local...")
    latest_zip = get_latest_backup(BACKUP_DIR)
    
    if latest_zip:
        new_filename = generate_new_name()
        print(f"-> Último backup encontrado: {os.path.basename(latest_zip)}")
        print(f"-> Será renomeado para: {new_filename}")
        # O próximo passo será anexar a função de upload aqui
