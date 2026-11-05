"""The translations as the build makes them (openexpress/catalogs.py): the languages are those of
po/LINGUAS, each with its po/<language>.po; the compiled catalogs (.mo) are made at the build
(the Flatpak's manifest, install-desktop, the tests) and never kept in the repository; the
template (po/openexpress.pot) holds every text of the files po/POTFILES lists, the metainfo's
too; the metainfo is translated through gettext from its template, its release notes left in
English. GNU gettext's tools are needed; made-up catalogs only where one is written."""

import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from openexpress import catalogs, i18n

ROOT = Path(__file__).resolve().parent.parent
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
needs_gettext = pytest.mark.skipif(not shutil.which("xgettext"), reason="gettext not installed")


def test_the_languages_are_those_of_linguas_each_with_its_po():
    languages = catalogs.languages()
    assert "pl" in languages
    assert sorted(p.stem for p in (ROOT / "po").glob("*.po")) == sorted(languages)


def test_linguas_takes_comments_and_several_languages_on_a_line(tmp_path):
    (tmp_path / "LINGUAS").write_text("# the languages\npl de\n\nfr  # French\n")
    assert catalogs.languages(tmp_path) == ["pl", "de", "fr"]


def test_the_tests_run_with_a_catalog_of_every_language_built_for_them():
    """tests/conftest.py builds them into a folder of its own: none in the repository."""
    shown = i18n.available_languages()
    assert shown == [i18n.SOURCE_LANGUAGE, *sorted(catalogs.languages())]
    repository_folder = Path(i18n.__file__).parent / "locale"
    assert repository_folder != i18n.LOCALE_DIR


def test_no_compiled_catalog_nor_built_metainfo_is_kept_in_the_repository():
    ignored = (ROOT / ".gitignore").read_text().splitlines()
    assert "openexpress/locale/" in ignored
    assert "openexpress/data/io.github.tomaszbojanowski.OpenExpress.metainfo.xml" in ignored
    assert catalogs.METAINFO_TEMPLATE.is_file()


def test_building_the_catalogs_says_that_gettext_is_needed(monkeypatch, tmp_path):
    monkeypatch.setattr(catalogs.shutil, "which", lambda name: None)
    with pytest.raises(catalogs.CatalogError, match="msgfmt"):
        catalogs.build(tmp_path)


@needs_gettext
def test_every_language_is_compiled_where_it_is_asked(tmp_path):
    built = catalogs.build(tmp_path)
    assert sorted(p.relative_to(tmp_path).parts[0] for p in built) == sorted(catalogs.languages())
    assert all(p.name == "openexpress.mo" and p.stat().st_size > 0 for p in built)


def test_potfiles_lists_every_file_with_texts_and_the_metainfo_template():
    listed = (ROOT / "po" / "POTFILES").read_text().split()
    assert listed == catalogs.potfiles()
    assert "openexpress/data/io.github.tomaszbojanowski.OpenExpress.metainfo.xml.in" in listed
    assert "openexpress/i18n.py" in listed and "openexpress/__main__.py" not in listed


def _msgids(pot: Path) -> set[tuple[str, str]]:
    """(context, text) of every entry of a template."""
    found, ctx, key, fields = set(), "", None, {}
    for block in pot.read_text(encoding="utf-8").split("\n\n")[1:]:
        fields, key = {}, None
        for line in block.splitlines():
            m = re.match(r'^(msgctxt|msgid) "(.*)"$', line)
            if m:
                key = m.group(1)
                fields[key] = m.group(2)
            elif line.startswith('"') and key in ("msgctxt", "msgid"):
                fields[key] += line[1:-1]
            elif not line.startswith('"'):
                key = None
        ctx = fields.get("msgctxt", "")
        if "msgid" in fields:
            found.add((ctx, fields["msgid"]))
    return found


@needs_gettext
def test_the_template_holds_every_text_of_the_code_and_the_metainfo(tmp_path):
    fresh = tmp_path / "openexpress.pot"
    catalogs.write_template(fresh)
    assert _msgids(fresh) == _msgids(ROOT / "po" / "openexpress.pot"), \
        "run tools/update-template.sh"
    texts = {text for _ctx, text in _msgids(fresh)}
    assert "Manage your Garmin watch on Linux" in texts  # the metainfo's summary
    assert "No telemetry" in texts and "Connect IQ apps" in texts
    # Not to translate: the name, the developer, the keywords, the release notes.
    assert not texts & {"openExpress", "Tomasz Bojanowski", "Garmin", "fenix"}
    assert not any(t.startswith("Clearer icons.") for t in texts)


def test_the_metainfo_template_has_no_translation_in_it():
    text = catalogs.METAINFO_TEMPLATE.read_text(encoding="utf-8")
    assert "xml:lang" not in text
    root = ET.fromstring(text)
    notes = root.findall("releases/release/description")
    assert notes and all(d.get("translate") == "no" for d in notes)


@needs_gettext
def test_the_metainfo_is_translated_into_polish_at_the_build(tmp_path):
    """The Polish of the summary, the description and the screenshots' captions, as the
    metainfo carried it before (19 texts), now from po/pl.po; the release notes in English."""
    out = catalogs.compose_metainfo(tmp_path / "metainfo.xml")
    root = ET.parse(out).getroot()
    polish = [e for e in root.iter() if e.get(XML_LANG) == "pl"]
    assert len(polish) == 19
    assert root.find("summary[@{http://www.w3.org/XML/1998/namespace}lang='pl']").text == (
        "Zarządzaj zegarkiem Garmin na Linuksie")
    assert {e.tag for e in polish} == {"summary", "p", "li", "caption"}
    assert not [e for e in root.iter() if e.get(XML_LANG) and e.tag != "summary"
                and e.get(XML_LANG) != "pl"]
    assert not root.findall(".//releases//*[@{http://www.w3.org/XML/1998/namespace}lang]")


@pytest.mark.skipif(not (shutil.which("appstreamcli") and shutil.which("msgfmt")),
                    reason="appstreamcli or msgfmt not installed")
def test_the_built_metainfo_is_valid(tmp_path):
    out = catalogs.compose_metainfo(tmp_path / "io.github.tomaszbojanowski.OpenExpress.metainfo.xml")
    done = subprocess.run(["appstreamcli", "validate", "--no-net", "--explain", str(out)],
                          capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stdout + done.stderr


def test_install_desktop_builds_the_catalogs_from_source_first(monkeypatch, capsys):
    from openexpress import background, cli, desktop

    order = []
    monkeypatch.setattr(background, "in_flatpak", lambda: False)
    monkeypatch.setattr(desktop, "flatpak_installed", lambda: False)
    monkeypatch.setattr(catalogs, "build", lambda *a, **kw: order.append("catalogs") or [])
    monkeypatch.setattr(desktop, "install",
                        lambda dry_run: (order.append(f"files, dry run {dry_run}"), ([], []))[1])
    assert cli.main(["install-desktop"]) == 0
    assert cli.main(["install-desktop", "--apply"]) == 0
    assert order == ["files, dry run True", "catalogs", "files, dry run False"]


def test_install_desktop_without_gettext_says_so_and_goes_on_in_english(monkeypatch, capsys):
    from openexpress import background, cli, desktop

    def no_gettext(*_a, **_kw):
        raise catalogs.CatalogError("made-up: msgfmt is missing")

    monkeypatch.setattr(background, "in_flatpak", lambda: False)
    monkeypatch.setattr(desktop, "flatpak_installed", lambda: False)
    monkeypatch.setattr(catalogs, "build", no_gettext)
    monkeypatch.setattr(desktop, "install", lambda dry_run: ([], []))
    assert cli.main(["install-desktop", "--apply"]) == 0
    assert "made-up: msgfmt is missing" in capsys.readouterr().err
