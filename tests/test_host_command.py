"""Every command the Flatpak runs on the host (flatpak-spawn --host) is made by one function,
paths.host_command, and carries GIO_USE_VFS=gvfs: the session helper of an older flatpak passes
on its own GIO_USE_VFS=local, and the host's gio then sees mtp:// as no file of gvfs, so every
copy to the device fails with "Operation not supported"."""

import ast
from pathlib import Path

from openexpress import paths

PACKAGE = Path(paths.__file__).resolve().parent


def test_a_host_command_asks_for_gvfs_before_the_command():
    assert paths.host_command("gio", "copy", "-p", "/a", "mtp://watch/b") == [
        "flatpak-spawn", "--host", "--env=GIO_USE_VFS=gvfs", "gio", "copy", "-p", "/a",
        "mtp://watch/b"]


def _functions_with_a_spawn_list(source: Path) -> list[str]:
    """The innermost function around each list or tuple that starts with "flatpak-spawn"
    ("<module>" outside any)."""
    tree = ast.parse(source.read_text(encoding="utf-8"))
    functions = [n for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    found = []
    for node in ast.walk(tree):
        if (isinstance(node, (ast.List, ast.Tuple)) and node.elts
                and isinstance(node.elts[0], ast.Constant)
                and node.elts[0].value == "flatpak-spawn"):
            around = [f for f in functions if f.lineno <= node.lineno <= f.end_lineno]
            found.append(min(around, key=lambda f: f.end_lineno - f.lineno).name
                         if around else "<module>")
    return found


def test_no_host_command_is_made_but_by_host_command():
    makers = {(p.relative_to(PACKAGE.parent).as_posix(), name)
              for p in PACKAGE.rglob("*.py") for name in _functions_with_a_spawn_list(p)}
    assert makers == {("openexpress/paths.py", "host_command")}
