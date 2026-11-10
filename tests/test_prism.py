import os
import pytest

import prism


class TestDiscoverPrismInstances:
    def test_returns_empty_when_dir_missing(self, tmp_path):
        assert prism.discover_prism_instances(str(tmp_path / "missing")) == []

    def test_discovers_valid_instances(self, tmp_path):
        inst1 = tmp_path / "GTNH 2.9-Beta2"
        inst1.mkdir()
        (inst1 / "instance.cfg").write_text("InstanceType=OneSix\n")

        inst2 = tmp_path / "Vanilla 1.20"
        inst2.mkdir()
        (inst2 / "instance.cfg").write_text("InstanceType=OneSix\n")

        # Directory without instance.cfg should be ignored
        (tmp_path / "random_folder").mkdir()

        # Regular file should be ignored
        (tmp_path / "some_file.txt").write_text("hello")

        instances = prism.discover_prism_instances(str(tmp_path))
        assert instances == ["GTNH 2.9-Beta2", "Vanilla 1.20"]


class TestReadPostExitCommand:
    def test_returns_none_if_file_missing(self, tmp_path):
        assert prism.read_post_exit_command(str(tmp_path / "missing.cfg")) is None

    def test_returns_empty_string_when_not_set(self, tmp_path):
        cfg = tmp_path / "instance.cfg"
        cfg.write_text("InstanceType=OneSix\nname=GTNH\n")
        assert prism.read_post_exit_command(str(cfg)) == ""

    def test_reads_existing_post_exit_command(self, tmp_path):
        cfg = tmp_path / "instance.cfg"
        cfg.write_text("InstanceType=OneSix\nPostExitCommand=gtnh backup push\n")
        assert prism.read_post_exit_command(str(cfg)) == "gtnh backup push"


class TestUpdatePostExitCommand:
    def test_raises_error_if_cfg_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            prism.update_post_exit_command(str(tmp_path / "missing.cfg"), "echo 1")

    def test_appends_when_not_present(self, tmp_path):
        cfg = tmp_path / "instance.cfg"
        cfg.write_text("InstanceType=OneSix\nname=GTNH\n")

        prism.update_post_exit_command(str(cfg), "gtnh backup push")
        content = cfg.read_text()
        assert "PostExitCommand=gtnh backup push\n" in content
        assert "InstanceType=OneSix\n" in content

    def test_replaces_existing_entry(self, tmp_path):
        cfg = tmp_path / "instance.cfg"
        cfg.write_text("InstanceType=OneSix\nPostExitCommand=old_command\nname=GTNH\n")

        prism.update_post_exit_command(str(cfg), "gtnh backup push")
        content = cfg.read_text()
        assert "PostExitCommand=gtnh backup push\n" in content
        assert "old_command" not in content


class TestInstallPrismHook:
    def test_installs_hook_into_instance(self, tmp_path):
        inst_dir = tmp_path / "MyInstance"
        inst_dir.mkdir()
        cfg = inst_dir / "instance.cfg"
        cfg.write_text("name=MyInstance\n")

        res_path = prism.install_prism_hook(
            instance_name="MyInstance",
            instances_dir=str(tmp_path),
            command_override="gtnh backup push"
        )

        assert res_path == str(cfg)
        assert prism.read_post_exit_command(str(cfg)) == "gtnh backup push"
