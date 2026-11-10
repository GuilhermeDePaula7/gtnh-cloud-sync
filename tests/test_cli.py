from unittest.mock import MagicMock, patch
import pytest

import cli
import sync


class TestFormatSize:
    def test_formats_various_byte_sizes(self):
        assert cli.format_size(None) == "Unknown size"
        assert cli.format_size("invalid") == "Unknown size"
        assert cli.format_size(500) == "500.0 B"
        assert cli.format_size(1024) == "1.0 KB"
        assert cli.format_size(1024 * 1024 * 5) == "5.0 MB"
        assert cli.format_size(1024 * 1024 * 1024 * 2.5) == "2.5 GB"


class TestCliBackupPush:
    @patch("sync.main", return_value=True)
    def test_push_success_returns_zero(self, mock_main):
        exit_code = cli.cli_entrypoint(["backup", "push"])
        assert exit_code == 0
        mock_main.assert_called_once()

    @patch("sync.main", return_value=True)
    def test_start_alias_triggers_push(self, mock_main):
        exit_code = cli.cli_entrypoint(["backup", "start"])
        assert exit_code == 0
        mock_main.assert_called_once()

    @patch("sync.main", return_value=False)
    def test_push_failure_returns_one(self, mock_main):
        exit_code = cli.cli_entrypoint(["backup", "push"])
        assert exit_code == 1


class TestCliBackupList:
    @patch("sync.authenticate_gdrive")
    @patch("sync.list_remote_backups", return_value=[])
    def test_list_empty(self, mock_list, mock_auth, capsys):
        exit_code = cli.cli_entrypoint(["backup", "list"])
        assert exit_code == 0
        assert "No backups found" in capsys.readouterr().out

    @patch("sync.authenticate_gdrive")
    @patch("sync.list_remote_backups")
    def test_list_with_backups(self, mock_list, mock_auth, capsys):
        mock_list.return_value = [
            {
                "id": "file_123",
                "name": "10-11-26-GTNH.zip",
                "size": 10485760,
                "createdTime": "2026-11-10T15:00:00Z"
            }
        ]
        exit_code = cli.cli_entrypoint(["backup", "list"])
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "10-11-26-GTNH.zip" in out
        assert "10.0 MB" in out
        assert "file_123" in out


class TestCliBackupPull:
    @patch("sync.download_file_from_drive")
    @patch("sync.authenticate_gdrive")
    @patch("sync.list_remote_backups")
    def test_pull_latest_by_default(self, mock_list, mock_auth, mock_download, tmp_path, capsys):
        mock_list.return_value = [
            {"id": "latest_id", "name": "latest.zip"},
            {"id": "older_id", "name": "older.zip"}
        ]
        out_dir = str(tmp_path / "downloads")

        exit_code = cli.cli_entrypoint(["backup", "pull", "-o", out_dir])
        assert exit_code == 0
        mock_download.assert_called_once_with(
            mock_auth.return_value,
            "latest_id",
            f"{out_dir}/latest.zip"
        )
        assert "Selecting latest backup" in capsys.readouterr().out

    @patch("sync.download_file_from_drive")
    @patch("sync.authenticate_gdrive")
    @patch("sync.list_remote_backups")
    def test_pull_specific_id(self, mock_list, mock_auth, mock_download, tmp_path):
        mock_list.return_value = [
            {"id": "id_1", "name": "b1.zip"},
            {"id": "id_2", "name": "b2.zip"}
        ]
        out_dir = str(tmp_path)
        exit_code = cli.cli_entrypoint(["backup", "pull", "--id", "id_2", "-o", out_dir])
        assert exit_code == 0
        mock_download.assert_called_once_with(
            mock_auth.return_value,
            "id_2",
            f"{out_dir}/b2.zip"
        )

    @patch("sync.authenticate_gdrive")
    @patch("sync.list_remote_backups")
    def test_pull_not_found(self, mock_list, mock_auth, capsys):
        mock_list.return_value = [{"id": "id_1", "name": "b1.zip"}]
        exit_code = cli.cli_entrypoint(["backup", "pull", "--name", "non_existent.zip"])
        assert exit_code == 1
        assert "not found" in capsys.readouterr().out

    @patch("sync.authenticate_gdrive")
    @patch("sync.list_remote_backups", return_value=[])
    def test_pull_empty_drive(self, mock_list, mock_auth, capsys):
        exit_code = cli.cli_entrypoint(["backup", "pull"])
        assert exit_code == 1
        assert "No backups available" in capsys.readouterr().out


class TestCliPrismSubcommands:
    @patch("prism.discover_prism_instances", return_value=["GTNH 2.9-Beta2", "OtherPack"])
    def test_prism_instances_lists_found(self, mock_disc, capsys):
        exit_code = cli.cli_entrypoint(["prism", "instances"])
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "GTNH 2.9-Beta2" in out
        assert "OtherPack" in out

    @patch("prism.discover_prism_instances", return_value=[])
    def test_prism_instances_empty(self, mock_disc, capsys):
        exit_code = cli.cli_entrypoint(["prism", "instances"])
        assert exit_code == 0
        assert "No instances found" in capsys.readouterr().out

    @patch("prism.install_prism_hook", return_value="/tmp/instance.cfg")
    def test_prism_install_hook_success(self, mock_install, capsys):
        exit_code = cli.cli_entrypoint(["prism", "install-hook", "-i", "CustomGTNH"])
        assert exit_code == 0
        mock_install.assert_called_once_with(instance_name="CustomGTNH", command_override="gtnh backup push")
        assert "Successfully configured" in capsys.readouterr().out

    @patch("prism.install_prism_hook", side_effect=FileNotFoundError("not found"))
    def test_prism_install_hook_failure(self, mock_install, capsys):
        exit_code = cli.cli_entrypoint(["prism", "install-hook", "-i", "Missing"])
        assert exit_code == 1
        assert "[Error]" in capsys.readouterr().out

    @patch("os.path.isfile", return_value=True)
    @patch("prism.read_post_exit_command", return_value="gtnh backup push")
    def test_prism_status_configured(self, mock_read, mock_isfile, capsys):
        exit_code = cli.cli_entrypoint(["prism", "status", "-i", "CustomGTNH"])
        assert exit_code == 0
        assert "PostExitCommand: 'gtnh backup push'" in capsys.readouterr().out

    @patch("os.path.isfile", return_value=False)
    def test_prism_status_missing(self, mock_isfile, capsys):
        exit_code = cli.cli_entrypoint(["prism", "status", "-i", "Unknown"])
        assert exit_code == 1
        assert "Config not found" in capsys.readouterr().out


class TestCliEntrypointHelp:
    def test_no_args_shows_help(self, capsys):
        exit_code = cli.cli_entrypoint([])
        assert exit_code == 1
