import argparse
import os
import sys
from datetime import datetime

import sync


def format_size(bytes_num):
    """Formats file size in human readable format."""
    if bytes_num is None:
        return "Unknown size"
    try:
        bytes_num = float(bytes_num)
    except (ValueError, TypeError):
        return "Unknown size"

    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_num < 1024.0:
            return f"{bytes_num:.1f} {unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.1f} TB"


def handle_backup_push(args):
    """Triggers the backup upload workflow."""
    success = sync.main()
    return 0 if success else 1


def handle_backup_list(args):
    """Lists backups stored in Google Drive."""
    print("[Cloud] Fetching remote backups list...")
    service = sync.authenticate_gdrive()
    backups = sync.list_remote_backups(service, folder_id=sync.DRIVE_FOLDER_ID)

    if not backups:
        print("[Cloud] No backups found in the Google Drive folder.")
        return 0

    print(f"\nFound {len(backups)} backup(s) on Google Drive (Folder ID: {sync.DRIVE_FOLDER_ID}):\n")
    print(f"{'#':<3} {'Name':<35} {'Size':<12} {'Created At':<25} {'ID'}")
    print("-" * 90)

    for idx, item in enumerate(backups, 1):
        name = item.get('name', 'unnamed')
        size_str = format_size(item.get('size'))
        created = item.get('createdTime', 'N/A')
        file_id = item.get('id', 'N/A')
        print(f"{idx:<3} {name:<35} {size_str:<12} {created:<25} {file_id}")

    return 0


def handle_backup_pull(args):
    """Downloads a backup from Google Drive."""
    service = sync.authenticate_gdrive()
    backups = sync.list_remote_backups(service, folder_id=sync.DRIVE_FOLDER_ID)

    if not backups:
        print("[Cloud] No backups available to download.")
        return 1

    target_file = None
    if args.file_id:
        for b in backups:
            if b.get('id') == args.file_id:
                target_file = b
                break
        if not target_file:
            print(f"[Error] File with ID '{args.file_id}' not found in Drive backup folder.")
            return 1
    elif args.file_name:
        for b in backups:
            if b.get('name') == args.file_name:
                target_file = b
                break
        if not target_file:
            print(f"[Error] File named '{args.file_name}' not found in Drive backup folder.")
            return 1
    else:
        # Default: download latest
        target_file = backups[0]
        print(f"[Cloud] No specific file provided. Selecting latest backup: '{target_file.get('name')}'.")

    file_id = target_file['id']
    file_name = target_file.get('name', 'downloaded_backup.zip')

    dest_dir = args.output_dir if args.output_dir else sync.BACKUP_DIR
    dest_path = os.path.join(os.path.expanduser(dest_dir), file_name)

    print(f"[Cloud] Downloading '{file_name}' to '{dest_path}'...")
    sync.download_file_from_drive(service, file_id, dest_path)
    print(f"[Success] Backup downloaded successfully to: {dest_path}")
    return 0


def build_parser():
    """Builds and returns the argparse CLI parser."""
    parser = argparse.ArgumentParser(
        prog="gtnh",
        description="GTNH Cloud Sync: Manage Prism Launcher Minecraft backups with Google Drive"
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Available commands")

    # backup subcommand
    backup_parser = subparsers.add_parser("backup", help="Manage backups")
    backup_sub = backup_parser.add_subparsers(dest="action", help="Backup action")

    # gtnh backup push (or start)
    push_parser = backup_sub.add_parser("push", aliases=["start"], help="Upload the latest local backup to Drive")
    push_parser.set_defaults(func=handle_backup_push)

    # gtnh backup list
    list_parser = backup_sub.add_parser("list", help="List remote backups in Drive")
    list_parser.set_defaults(func=handle_backup_list)

    # gtnh backup pull
    pull_parser = backup_sub.add_parser("pull", aliases=["restore"], help="Download a backup from Drive")
    pull_parser.add_argument("--id", dest="file_id", help="Drive file ID to download")
    pull_parser.add_argument("--name", dest="file_name", help="Filename in Drive to download")
    pull_parser.add_argument(
        "--output-dir",
        "-o",
        dest="output_dir",
        help=f"Destination directory (defaults to instance backup dir: {sync.BACKUP_DIR})"
    )
    pull_parser.set_defaults(func=handle_backup_pull)

    # prism subcommand
    prism_parser = subparsers.add_parser("prism", help="Prism Launcher integration")
    prism_sub = prism_parser.add_subparsers(dest="action", help="Prism actions")

    # gtnh prism instances
    instances_parser = prism_sub.add_parser("instances", help="List discovered Prism Launcher instances")
    instances_parser.set_defaults(func=handle_prism_instances)

    # gtnh prism install-hook
    hook_parser = prism_sub.add_parser("install-hook", help="Configure automatic backup on Prism Launcher game exit")
    hook_parser.add_argument("--instance", "-i", dest="instance_name", help="Target instance name")
    hook_parser.add_argument("--command", "-c", dest="command", help="Custom command (defaults to 'gtnh backup push')")
    hook_parser.set_defaults(func=handle_prism_install_hook)

    # gtnh prism status
    status_parser = prism_sub.add_parser("status", help="Show current PostExitCommand status for instance")
    status_parser.add_argument("--instance", "-i", dest="instance_name", help="Target instance name")
    status_parser.set_defaults(func=handle_prism_status)

    return parser


def handle_prism_instances(args):
    """Lists Prism Launcher instances."""
    import prism
    instances = prism.discover_prism_instances()
    if not instances:
        print(f"[Prism] No instances found in: {prism.DEFAULT_PRISM_INSTANCES_DIR}")
        return 0

    print(f"\n[Prism] Discovered {len(instances)} instance(s) in {prism.DEFAULT_PRISM_INSTANCES_DIR}:\n")
    for name in instances:
        marker = " (Active in .env)" if name == sync.INSTANCE_NAME else ""
        print(f" - {name}{marker}")
    return 0


def handle_prism_install_hook(args):
    """Installs post-exit command in Prism Launcher instance.cfg."""
    import prism
    instance = args.instance_name if args.instance_name else sync.INSTANCE_NAME
    hook_cmd = args.command if args.command else "gtnh backup push"

    try:
        cfg_path = prism.install_prism_hook(instance_name=instance, command_override=hook_cmd)
        print(f"[Prism] Successfully configured post-exit hook for '{instance}'!")
        print(f"[Prism] Updated config: {cfg_path}")
        print(f"[Prism] Configured command: '{hook_cmd}'")
        return 0
    except FileNotFoundError as e:
        print(f"[Error] {e}")
        print(f"[Tip] Verify that the instance '{instance}' exists in {prism.DEFAULT_PRISM_INSTANCES_DIR}")
        return 1


def handle_prism_status(args):
    """Checks the post-exit command in Prism Launcher instance.cfg."""
    import prism
    instance = args.instance_name if args.instance_name else sync.INSTANCE_NAME
    cfg_path = os.path.join(prism.DEFAULT_PRISM_INSTANCES_DIR, instance, "instance.cfg")

    if not os.path.isfile(cfg_path):
        print(f"[Prism] Config not found for instance '{instance}' at: {cfg_path}")
        return 1

    current_cmd = prism.read_post_exit_command(cfg_path)
    print(f"[Prism] Instance: {instance}")
    print(f"[Prism] Config file: {cfg_path}")
    if current_cmd:
        print(f"[Prism] PostExitCommand: '{current_cmd}'")
    else:
        print(f"[Prism] PostExitCommand: None (Not configured)")
    return 0


def cli_entrypoint(argv=None):
    """Main CLI entrypoint function."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(cli_entrypoint())
