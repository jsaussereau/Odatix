"""
What gets shipped: the link checker of the documentation, and the files of the
package a wheel would leave out.
"""

import importlib.util
import os
import re

from conftest import REPO_ROOT

SOURCES_DIR = os.path.join(REPO_ROOT, "sources")


def _load_check_links():
    path = os.path.join(REPO_ROOT, "docs", "tools", "check_links.py")
    spec = importlib.util.spec_from_file_location("check_links", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(root, relpath, html):
    path = os.path.join(str(root), relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


class TestCheckLinks:
    def test_valid_site(self, tmp_path, capsys):
        check_links = _load_check_links()
        _write(tmp_path, "index.html", '<a href="/docs/">docs</a><a href="https://example.com/x">out</a>')
        _write(tmp_path, "docs/index.html", '<h2 id="intro">x</h2><a href="#intro">self</a><a href="../">up</a>')
        _write(tmp_path, "docs/page/index.html", '<a href="/docs/#intro">anchor</a><img src="/img.png">')
        _write(tmp_path, "img.png", "")
        assert check_links.check(str(tmp_path))
        assert "0 broken links" in capsys.readouterr().out

    def test_missing_page_and_anchor(self, tmp_path, capsys):
        check_links = _load_check_links()
        _write(tmp_path, "index.html", '<a href="/nowhere/">x</a><a href="/docs/#missing">y</a>')
        _write(tmp_path, "docs/index.html", '<h2 id="intro">x</h2>')
        assert not check_links.check(str(tmp_path))
        out = capsys.readouterr().out
        assert "/nowhere/ (no such page)" in out
        assert "/docs/#missing (no such anchor)" in out

    def test_anchor_through_an_alias(self, tmp_path):
        """A Hugo alias is a refresh to the real page: its anchors are the real page's."""
        check_links = _load_check_links()
        _write(tmp_path, "old/index.html", '<meta http-equiv="refresh" content="0; url=/new/">')
        _write(tmp_path, "new/index.html", '<h2 id="part">x</h2>')
        _write(tmp_path, "index.html", '<a href="/old/#part">x</a>')
        assert check_links.check(str(tmp_path))


class TestPackageData:
    def test_python_directories_without_init_are_package_data(self):
        """
        find_packages() skips a directory without __init__.py (gui/pages, which
        Dash loads by path): setup.py has to list its files, or the wheel ships
        a GUI without its pages.
        """
        with open(os.path.join(SOURCES_DIR, "setup.py"), encoding="utf-8") as f:
            setup_py = f.read()
        listed = set(re.findall(r"package_files\('odatix', '([^']+)'\)", setup_py))

        odatix_dir = os.path.join(SOURCES_DIR, "odatix")
        missing = []
        for root, dirs, files in os.walk(odatix_dir):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            if any(name.endswith(".py") for name in files) and "__init__.py" not in files:
                relpath = os.path.relpath(root, odatix_dir).replace(os.sep, "/")
                if relpath not in listed:
                    missing.append(relpath)
        assert missing == []

    def test_manifest_names_existing_paths(self):
        """A recursive-include of a directory that does not exist ships nothing."""
        with open(os.path.join(SOURCES_DIR, "MANIFEST.in"), encoding="utf-8") as f:
            lines = f.read().splitlines()
        for line in lines:
            words = line.split()
            if words and words[0] in ("include", "recursive-include"):
                assert os.path.exists(os.path.join(SOURCES_DIR, words[1])), line

    def test_data_directories_are_shipped(self):
        """Directories Odatix reads at run time, with no Python package of their own."""
        with open(os.path.join(SOURCES_DIR, "setup.py"), encoding="utf-8") as f:
            setup_py = f.read()
        with open(os.path.join(SOURCES_DIR, "MANIFEST.in"), encoding="utf-8") as f:
            manifest = f.read()
        for directory in ("odatix_eda_tools", "odatix_sim_templates", "odatix_examples", "odatix_init"):
            assert "package_files('" + directory + "')" in setup_py, directory
            assert "recursive-include " + directory + " *" in manifest, directory
