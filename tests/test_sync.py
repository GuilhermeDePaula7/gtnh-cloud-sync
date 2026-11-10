import os
import hashlib
from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest

import sync


class TestGetLatestBackup:
    def test_returns_none_when_directory_empty(self, tmp_path):
        assert sync.get_latest_backup(str(tmp_path)) is None

    def test_ignores_non_zip_files(self, tmp_path):
        (tmp_path / "notes.txt").write_text("not a zip")
        (tmp_path / "backup.tar.gz").write_bytes(b"data")
        assert sync.get_latest_backup(str(tmp_path)) is None

    def test_returns_most_recent_zip_file(self, tmp_path):
        older = tmp_path / "older.zip"
        newer = tmp_path / "newer.zip"
        older.write_bytes(b"old_content")
        newer.write_bytes(b"new_content")

        with patch("os.path.getctime") as mock_ctime:
            mock_ctime.side_effect = lambda p: 100.0 if p.endswith("older.zip") else 200.0
            result = sync.get_latest_backup(str(tmp_path))

        assert result == str(newer)


class TestGenerateNewName:
    def test_formats_date_and_replaces_spaces(self):
        fixed_date = datetime(2026, 11, 10, 15, 30)
        name = sync.generate_new_name(instance_name="GTNH 2.9 Beta2", now=fixed_date)
        assert name == "10-11-26-GTNH-2.9-Beta2.zip"

    def test_uses_default_instance_name(self, monkeypatch):
        monkeypatch.setattr(sync, "INSTANCE_NAME", "My Custom Instance")
        fixed_date = datetime(2026, 1, 5)
        name = sync.generate_new_name(now=fixed_date)
        assert name == "05-01-26-My-Custom-Instance.zip"


class TestComputeMd5:
    def test_computes_correct_md5_checksum(self, tmp_path):
        sample_file = tmp_path / "sample.zip"
        payload = b"gtnh-world-backup-payload" * 1024
        sample_file.write_bytes(payload)

        expected_md5 = hashlib.md5(payload).hexdigest()
        assert sync.compute_md5(str(sample_file)) == expected_md5


class TestIsBackupAlreadyUploaded:
    def test_returns_existing_file_when_md5_matches(self, tmp_path):
        backup_file = tmp_path / "backup.zip"
        backup_file.write_bytes(b"identical-backup-content")
        expected_md5 = hashlib.md5(b"identical-backup-content").hexdigest()

        mock_service = MagicMock()
        mock_list = mock_service.files.return_value.list
        mock_list.return_value.execute.return_value = {
            "files": [{"id": "drive_123", "name": "10-11-26-GTNH.zip", "md5Checksum": expected_md5}]
        }

        result = sync.is_backup_already_uploaded(mock_service, str(backup_file), folder_id="folder_abc")

        assert result == {"id": "drive_123", "name": "10-11-26-GTNH.zip", "md5Checksum": expected_md5}
        called_query = mock_list.call_args.kwargs["q"]
        assert "'folder_abc' in parents" in called_query
        assert f"md5Checksum = '{expected_md5}'" in called_query

    def test_returns_none_when_no_matching_file_on_drive(self, tmp_path):
        backup_file = tmp_path / "backup.zip"
        backup_file.write_bytes(b"new-backup-content")

        mock_service = MagicMock()
        mock_service.files.return_value.list.return_value.execute.return_value = {"files": []}

        result = sync.is_backup_already_uploaded(mock_service, str(backup_file), folder_id="folder_abc")
        assert result is None


class TestAuthenticateGdrive:
    @patch("sync.build")
    @patch("sync.Credentials.from_authorized_user_file")
    def test_uses_existing_valid_token(self, mock_from_file, mock_build, tmp_path):
        token_file = tmp_path / "token.json"
        token_file.write_text("{}")

        mock_creds = MagicMock(valid=True)
        mock_from_file.return_value = mock_creds

        sync.authenticate_gdrive(token_path=str(token_file), creds_path=str(tmp_path / "creds.json"))

        mock_from_file.assert_called_once_with(str(token_file), sync.SCOPES)
        mock_build.assert_called_once_with("drive", "v3", credentials=mock_creds)

    @patch("sync.build")
    @patch("sync.Request")
    @patch("sync.Credentials.from_authorized_user_file")
    def test_refreshes_expired_token(self, mock_from_file, mock_request, mock_build, tmp_path):
        token_file = tmp_path / "token.json"
        token_file.write_text("{}")

        mock_creds = MagicMock(valid=False, expired=True, refresh_token="refresh_tok")
        mock_creds.to_json.return_value = '{"refreshed": true}'
        mock_from_file.return_value = mock_creds

        sync.authenticate_gdrive(token_path=str(token_file), creds_path=str(tmp_path / "creds.json"))

        mock_creds.refresh.assert_called_once_with(mock_request.return_value)
        assert token_file.read_text() == '{"refreshed": true}'
        mock_build.assert_called_once_with("drive", "v3", credentials=mock_creds)

    @patch("sync.build")
    @patch("sync.InstalledAppFlow.from_client_secrets_file")
    def test_runs_oauth_flow_when_no_token_exists(self, mock_flow_cls, mock_build, tmp_path):
        token_file = tmp_path / "token.json"
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text("{}")

        mock_creds = MagicMock()
        mock_creds.to_json.return_value = '{"new_token": true}'
        mock_flow_cls.return_value.run_local_server.return_value = mock_creds

        sync.authenticate_gdrive(token_path=str(token_file), creds_path=str(creds_file))

        mock_flow_cls.assert_called_once_with(str(creds_file), sync.SCOPES)
        assert token_file.read_text() == '{"new_token": true}'
        mock_build.assert_called_once_with("drive", "v3", credentials=mock_creds)


class TestUploadToDrive:
    @patch("sync.MediaFileUpload")
    def test_uploads_in_chunks_and_returns_file_id(self, mock_media_cls, tmp_path, capsys):
        backup_file = tmp_path / "world.zip"
        backup_file.write_bytes(b"zipdata")

        mock_status_50 = MagicMock()
        mock_status_50.progress.return_value = 0.5

        mock_request = MagicMock()
        mock_request.next_chunk.side_effect = [
            (mock_status_50, None),
            (None, {"id": "uploaded_id_999"})
        ]

        mock_service = MagicMock()
        mock_service.files.return_value.create.return_value = mock_request

        file_id = sync.upload_to_drive(
            mock_service,
            str(backup_file),
            "10-11-26-GTNH.zip",
            folder_id="folder_xyz"
        )

        assert file_id == "uploaded_id_999"
        mock_service.files.return_value.create.assert_called_once_with(
            body={"name": "10-11-26-GTNH.zip", "parents": ["folder_xyz"]},
            media_body=mock_media_cls.return_value,
            fields="id"
        )
        captured = capsys.readouterr().out
        assert "[Cloud] Upload progress: 50%" in captured
        assert "uploaded_id_999" in captured


class TestDownloadFileFromDrive:
    @patch("googleapiclient.http.MediaIoBaseDownload")
    def test_downloads_in_chunks_and_writes_file(self, mock_downloader_cls, tmp_path, capsys):
        dest = tmp_path / "downloads" / "recovered.zip"

        mock_status = MagicMock()
        mock_status.progress.return_value = 1.0

        mock_downloader = MagicMock()
        mock_downloader.next_chunk.return_value = (mock_status, True)
        mock_downloader_cls.return_value = mock_downloader

        mock_service = MagicMock()

        result_path = sync.download_file_from_drive(mock_service, "remote_id_123", str(dest))

        assert result_path == str(dest)
        mock_service.files.return_value.get_media.assert_called_once_with(fileId="remote_id_123")
        assert "[Download] Finished saving" in capsys.readouterr().out


class TestNotifyHyprland:
    @patch("subprocess.run")
    def test_calls_notify_send(self, mock_run):
        sync.notify_hyprland("Test Title", "Test Message")
        mock_run.assert_called_once_with(
            ["notify-send", "-t", "5000", "-a", "GTNH Cloud Sync", "Test Title", "Test Message"],
            check=False
        )

    @patch("subprocess.run", side_effect=FileNotFoundError("notify-send not installed"))
    def test_handles_exception_gracefully(self, mock_run, capsys):
        sync.notify_hyprland("Title", "Body")
        assert "Error sending notification" in capsys.readouterr().out


class TestRetentionPolicy:
    def test_list_remote_backups_paginates_and_sorts(self):
        mock_service = MagicMock()
        mock_list = mock_service.files.return_value.list

        page1 = {
            "files": [{"id": "1", "name": "newest.zip", "createdTime": "2026-11-10T12:00:00Z"}],
            "nextPageToken": "token_page2"
        }
        page2 = {
            "files": [{"id": "2", "name": "older.zip", "createdTime": "2026-11-09T12:00:00Z"}]
        }
        mock_list.return_value.execute.side_effect = [page1, page2]

        backups = sync.list_remote_backups(mock_service, folder_id="folder_123")

        assert len(backups) == 2
        assert backups[0]["id"] == "1"
        assert backups[1]["id"] == "2"
        assert mock_list.call_count == 2
        assert mock_list.call_args_list[0].kwargs["pageToken"] is None
        assert mock_list.call_args_list[1].kwargs["pageToken"] == "token_page2"

    def test_enforce_retention_skips_when_limit_zero_or_negative(self):
        mock_service = MagicMock()
        deleted = sync.enforce_retention_policy(mock_service, max_backups=0)
        assert deleted == []
        mock_service.files.return_value.list.assert_not_called()

    @patch("sync.list_remote_backups")
    def test_enforce_retention_does_nothing_if_count_within_limit(self, mock_list):
        mock_service = MagicMock()
        mock_list.return_value = [
            {"id": "1", "name": "b1.zip"},
            {"id": "2", "name": "b2.zip"}
        ]

        deleted = sync.enforce_retention_policy(mock_service, max_backups=5)

        assert deleted == []
        mock_service.files.return_value.delete.assert_not_called()

    @patch("sync.list_remote_backups")
    def test_enforce_retention_deletes_excess_older_backups(self, mock_list, capsys):
        mock_service = MagicMock()
        mock_delete = mock_service.files.return_value.delete
        mock_delete.return_value.execute.return_value = {}

        mock_list.return_value = [
            {"id": "1", "name": "b1.zip"},
            {"id": "2", "name": "b2.zip"},
            {"id": "3", "name": "b3.zip"},
            {"id": "4", "name": "b4.zip"}
        ]

        deleted = sync.enforce_retention_policy(mock_service, max_backups=2)

        assert len(deleted) == 2
        assert [d["id"] for d in deleted] == ["3", "4"]
        assert mock_delete.call_count == 2
        mock_delete.assert_any_call(fileId="3")
        mock_delete.assert_any_call(fileId="4")
        assert "[Retention] Deleted old backup: b3.zip" in capsys.readouterr().out


class TestMainWorkflow:
    @patch("sync.notify_hyprland")
    @patch("sync.get_latest_backup", return_value=None)
    def test_main_notifies_failure_when_no_backup_found(self, mock_get_latest, mock_notify):
        assert sync.main() is False
        mock_notify.assert_called_once_with("Backup Failed", "No .zip file found in the instance folder.")

    @patch("sync.enforce_retention_policy")
    @patch("sync.upload_to_drive")
    @patch("sync.notify_hyprland")
    @patch("sync.is_backup_already_uploaded", return_value={"id": "existing_1", "name": "10-11-26-GTNH.zip"})
    @patch("sync.authenticate_gdrive")
    @patch("sync.get_latest_backup", return_value="/tmp/latest.zip")
    def test_main_skips_upload_when_duplicate_detected(
        self, mock_latest, mock_auth, mock_is_uploaded, mock_notify, mock_upload, mock_retention
    ):
        assert sync.main() is True
        mock_upload.assert_not_called()
        mock_retention.assert_called_once_with(mock_auth.return_value, sync.DRIVE_FOLDER_ID, sync.MAX_REMOTE_BACKUPS)
        mock_notify.assert_called_once_with(
            "Backup Already Synced",
            "Latest backup is already on Google Drive (10-11-26-GTNH.zip)."
        )

    @patch("sync.enforce_retention_policy")
    @patch("sync.upload_to_drive", return_value="new_drive_id")
    @patch("sync.notify_hyprland")
    @patch("sync.is_backup_already_uploaded", return_value=None)
    @patch("sync.authenticate_gdrive")
    @patch("sync.generate_new_name", return_value="10-11-26-GTNH.zip")
    @patch("sync.get_latest_backup", return_value="/tmp/latest.zip")
    def test_main_uploads_enforces_retention_and_notifies(
        self, mock_latest, mock_gen_name, mock_auth, mock_is_uploaded, mock_notify, mock_upload, mock_retention
    ):
        assert sync.main() is True
        mock_upload.assert_called_once_with(
            mock_auth.return_value,
            "/tmp/latest.zip",
            "10-11-26-GTNH.zip",
            sync.DRIVE_FOLDER_ID
        )
        mock_retention.assert_called_once_with(mock_auth.return_value, sync.DRIVE_FOLDER_ID, sync.MAX_REMOTE_BACKUPS)
        mock_notify.assert_called_once_with(
            "Backup Completed!",
            "File 10-11-26-GTNH.zip successfully uploaded to Google Drive."
        )
