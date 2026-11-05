"""The translations as files: the template of the texts (po/openexpress.pot, from the files
po/POTFILES lists), the compiled catalogs (.mo) of the languages of po/LINGUAS and the metainfo
translated from its template. The catalogs and the metainfo are made at the build (the Flatpak's
manifest, install-desktop from source, the tests), never kept in the repository. GNU gettext's
xgettext and msgfmt do the work.

    python3 -m openexpress.catalogs             the catalogs and the metainfo (the build)
    python3 -m openexpress.catalogs --template  po/POTFILES and po/openexpress.pot

Has: nothing of the window (a module of the build and of install-desktop).
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import sys
from pathlib import Path

from openexpress import __version__, i18n
from openexpress.i18n import _
from openexpress.paths import APP_ID

log = logging.getLogger(__name__)

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parent
PO = ROOT / "po"
TEMPLATE = PO / f"{i18n.DOMAIN}.pot"
METAINFO_TEMPLATE = PACKAGE / "data" / f"{APP_ID}.metainfo.xml.in"
METAINFO = METAINFO_TEMPLATE.with_suffix("")  # …metainfo.xml, made from the template
# The calls that mark a text to translate (i18n's docstring); the same keywords for xgettext.
GETTEXT_CALL = re.compile(r"\b(_|N_|ngettext|pgettext)\(")
KEYWORDS = ("--keyword=_", "--keyword=N_", "--keyword=ngettext:1,2", "--keyword=pgettext:1c,2")


class CatalogError(Exception):
    """A catalog or the metainfo could not be made (a tool of gettext missing or failing)."""


def languages(po_dir: Path = PO) -> list[str]:
    """The languages of po/LINGUAS, in its order (a "#" starts a comment)."""
    found = []
    for line in (po_dir / "LINGUAS").read_text(encoding="utf-8").splitlines():
        found += line.split("#", 1)[0].split()
    return found


def potfiles() -> list[str]:
    """The files with texts to translate, relative to the repository: the program's Python
    files that call one of the gettext functions, and the metainfo's template."""
    files = sorted(p.relative_to(ROOT).as_posix() for p in PACKAGE.rglob("*.py")
                   if GETTEXT_CALL.search(p.read_text(encoding="utf-8")))
    return [*files, METAINFO_TEMPLATE.relative_to(ROOT).as_posix()]


def _tool(name: str) -> str:
    found = shutil.which(name)
    if found is None:
        raise CatalogError(_("GNU gettext's {tool} is needed to build the translations (the "
                             "gettext package); without it openExpress stays in English.")
                           .format(tool=name))
    return found


def _run(args: list[str]) -> None:
    done = subprocess.run(args, capture_output=True, text=True, cwd=ROOT, check=False)
    if done.returncode != 0:
        raise CatalogError(f"{Path(args[0]).name}: {done.stderr.strip() or done.returncode}")


def write_template(out: Path = TEMPLATE) -> Path:
    """po/POTFILES written anew (with `out` the repository's template), and the template of
    every text they hold, the metainfo's by AppStream's rules (its file name says which)."""
    files = potfiles()
    if out == TEMPLATE:
        (PO / "POTFILES").write_text("\n".join(files) + "\n", encoding="utf-8")
    _run([_tool("xgettext"), "--from-code=UTF-8", *KEYWORDS, "--add-comments=TRANSLATORS",
          f"--package-name={i18n.DOMAIN}", f"--package-version={__version__}",
          f"--output={out}", *files])
    return out


def build(locale_dir: Path | None = None, po_dir: Path = PO) -> list[Path]:
    """The compiled catalog of each language of LINGUAS, into `locale_dir` (by default where
    the program reads them, i18n.LOCALE_DIR); each checked by msgfmt."""
    locale_dir = locale_dir or i18n.LOCALE_DIR
    msgfmt = _tool("msgfmt")
    built = []
    for language in languages(po_dir):
        mo = locale_dir / language / "LC_MESSAGES" / f"{i18n.DOMAIN}.mo"
        mo.parent.mkdir(parents=True, exist_ok=True)
        _run([msgfmt, "--check", f"--output-file={mo}", str(po_dir / f"{language}.po")])
        built.append(mo)
    log.info("translations: %d catalog%s built", len(built), "" if len(built) == 1 else "s")
    return built


def compose_metainfo(out: Path = METAINFO, po_dir: Path = PO) -> Path:
    """The metainfo with every language of LINGUAS, from its template (msgfmt's bulk mode)."""
    _run([_tool("msgfmt"), "--xml", f"--template={METAINFO_TEMPLATE}", "-d", str(po_dir),
          f"--output-file={out}"])
    return out


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        if argv == ["--template"]:
            print(write_template().relative_to(ROOT))
            return 0
        if argv:
            print(__doc__.split("\n\n")[1], file=sys.stderr)
            return 2
        for mo in build():
            print(mo.relative_to(ROOT) if mo.is_relative_to(ROOT) else mo)
        print(compose_metainfo().relative_to(ROOT))
    except CatalogError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
