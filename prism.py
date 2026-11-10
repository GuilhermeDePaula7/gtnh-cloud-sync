import os
import re

DEFAULT_PRISM_INSTANCES_DIR = os.path.expanduser("~/.local/share/PrismLauncher/instances")


def discover_prism_instances(instances_dir=None):
    """Discovers available Prism Launcher instance folders."""
    base_dir = instances_dir if instances_dir is not None else DEFAULT_PRISM_INSTANCES_DIR
    if not os.path.isdir(base_dir):
        return []

    instances = []
    for entry in sorted(os.listdir(base_dir)):
        instance_path = os.path.join(base_dir, entry)
        cfg_path = os.path.join(instance_path, "instance.cfg")
        if os.path.isdir(instance_path) and os.path.isfile(cfg_path):
            instances.append(entry)

    return instances


def read_post_exit_command(instance_cfg_path):
    """Reads the current PostExitCommand from an instance.cfg file."""
    if not os.path.isfile(instance_cfg_path):
        return None

    with open(instance_cfg_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("PostExitCommand="):
                return line.strip().split("=", 1)[1]
    return ""


def update_post_exit_command(instance_cfg_path, command_str):
    """Sets or replaces the PostExitCommand in an instance.cfg file."""
    if not os.path.isfile(instance_cfg_path):
        raise FileNotFoundError(f"Configuration file not found: {instance_cfg_path}")

    with open(instance_cfg_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    found = False
    new_lines = []
    for line in lines:
        if line.startswith("PostExitCommand="):
            new_lines.append(f"PostExitCommand={command_str}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        new_lines.append(f"PostExitCommand={command_str}\n")

    with open(instance_cfg_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    return True


def install_prism_hook(instance_name=None, instances_dir=None, command_override=None):
    """Installs gtnh backup push into instance.cfg of a Prism Launcher instance."""
    from sync import INSTANCE_NAME
    target_instance = instance_name if instance_name is not None else INSTANCE_NAME
    base_dir = instances_dir if instances_dir is not None else DEFAULT_PRISM_INSTANCES_DIR
    instance_cfg = os.path.join(base_dir, target_instance, "instance.cfg")

    hook_cmd = command_override if command_override is not None else "gtnh backup push"

    update_post_exit_command(instance_cfg, hook_cmd)
    return instance_cfg
