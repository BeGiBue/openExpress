"""The help of the commands: the folders they use by default as the program finds them (in the
Documents folder of the user's XDG folders, with ~ for the home folder), a folder option of
`activities export` by the name the other commands give it, the file of `fit inspect` in
capitals as the other commands name what they take."""

from pathlib import Path

import pytest

from openexpress import cli, paths


def help_of(capsys, *argv) -> str:
    with pytest.raises(SystemExit) as stopped:
        cli.main([*argv, "--help"])
    assert stopped.value.code == 0
    return capsys.readouterr().out


@pytest.fixture
def dokumenty(monkeypatch):
    """The backups where the program finds them on a Polish desktop: in Garmin in its XDG
    Documents folder, ~/Dokumenty."""
    monkeypatch.setattr(paths, "default_backup_dir",
                        lambda: Path.home() / "Dokumenty" / "Garmin" / "Backups")


def test_the_default_folders_are_said_as_the_program_finds_them(capsys, dokumenty):
    for argv in (("backup",), ("activities",)):
        said = help_of(capsys, *argv)
        assert "~/Dokumenty/Garmin/Backups" in said and "Documents" not in said
    export = help_of(capsys, "activities", "export")
    assert "~/Dokumenty/Garmin/GPX" in export and "~/Dokumenty/Garmin/Backups" in export
    assert "Documents" not in export


def test_a_folder_outside_the_home_folder_is_said_whole(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "default_backup_dir", lambda: Path("/srv/garmin/Backups"))
    assert "(default: /srv/garmin/Backups)" in help_of(capsys, "backup")


def test_the_backups_of_an_export_have_the_name_of_the_backups_of_the_list(capsys):
    export = help_of(capsys, "activities", "export")
    assert "EXPORT_BACKUPS" not in export and "--backups BACKUPS" in export
    assert "--backups BACKUPS" in help_of(capsys, "activities")


def test_the_file_of_fit_inspect_in_capitals(capsys):
    said = help_of(capsys, "fit", "inspect")
    assert "usage: openexpress fit inspect [-h] FILE" in said
    assert "\n  FILE " in said and " file\n" not in said


def test_a_path_is_shown_with_a_tilde_for_the_home_folder():
    assert paths.shown_path(Path.home() / "Dokumenty" / "Garmin") == "~/Dokumenty/Garmin"
    assert paths.shown_path(Path("/srv/garmin")) == "/srv/garmin"
