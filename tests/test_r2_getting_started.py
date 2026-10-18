"""
A beginner's first steps (2nd pass of the new user campaign): what "odatix
init" says and creates, the links it gives, the home page of the GUI, and the
pages of the documentation that show the output of "odatix init".
"""

import os
import re
import types

import pytest

import odatix.lib.printc as printc
from odatix.components import motd
from odatix.lib import doc_links
from odatix.lib.settings import OdatixSettings
import odatix.lib.settings as settings_module

from conftest import REPO_ROOT

DOCS_DIR = os.path.join(REPO_ROOT, "docs", "content")


def _plain(text):
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


######################################
# Links to the documentation
######################################

def test_the_links_of_the_documentation_point_at_pages_that_exist():
    # The pages of the documentation of this version are served under /en/latest/
    # (the root of the site redirects to /en/stable/, the last release: 3.7).
    assert doc_links.DOCS_URL == "https://odatix.readthedocs.io/en/latest/"
    pages = {
        doc_links.GETTING_STARTED_URL: os.path.join("docs", "getting-started.md"),
        doc_links.GLOSSARY_URL: os.path.join("docs", "glossary.md"),
        doc_links.OWN_DESIGNS_URL: os.path.join("tutorials", "own_designs", "_index.md"),
    }
    for url, page in pages.items():
        assert url.startswith(doc_links.DOCS_URL)
        assert os.path.isfile(os.path.join(DOCS_DIR, page)), url


######################################
# odatix init
######################################

def test_init_ends_with_a_first_run_when_the_examples_are_there(capsys):
    OdatixSettings.init_success("odatix", examples=True)
    out = _plain(capsys.readouterr().out)
    assert "odatix " + OdatixSettings.FIRST_RUN_COMMAND in out
    assert doc_links.GETTING_STARTED_URL in out
    # The first run names an example that exists, and stops after synthesis.
    assert "--until synthesis" in OdatixSettings.FIRST_RUN_COMMAND
    examples = os.path.join(OdatixSettings.odatix_examples_path, "odatix_userconfig", "architectures")
    assert os.path.isfile(os.path.join(examples, "Example_Counter_verilog", "08bits.txt"))


def test_init_without_the_examples_says_where_to_go_next(capsys):
    OdatixSettings.init_success("odatix", examples=False)
    out = _plain(capsys.readouterr().out)
    assert "odatix init --examples" in out
    assert doc_links.OWN_DESIGNS_URL in out
    assert OdatixSettings.FIRST_RUN_COMMAND not in out


def test_init_creates_the_directories_of_the_designs(tmp_path, monkeypatch):
    monkeypatch.chdir(str(tmp_path))
    assert OdatixSettings.init_directory_nodialog(include_examples=False, silent=True)
    for path in (OdatixSettings.DEFAULT_ARCH_PATH, OdatixSettings.DEFAULT_SIM_PATH, OdatixSettings.DEFAULT_WORKFLOW_PATH):
        assert os.path.isdir(str(tmp_path / path)), path


@pytest.mark.parametrize("existing", [False, True])
def test_init_warns_of_overwriting_only_a_workspace(tmp_path, monkeypatch, capsys, existing):
    monkeypatch.chdir(str(tmp_path))
    if existing:
        (tmp_path / "odatix.yml").write_text(u"default_tool: vivado\n")
    answers = iter([False])
    monkeypatch.setattr(settings_module, "ask_yes_no", lambda: next(answers))
    assert OdatixSettings.init_directory_dialog(include_examples=False, prog="odatix") is False
    out = _plain(capsys.readouterr().out)
    assert ("already holds an Odatix workspace" in out) == existing


######################################
# The documentation shows what init prints
######################################

def _init_output_pages():
    pages = []
    for root, _dirs, files in os.walk(DOCS_DIR):
        for name in files:
            if name.endswith(".md"):
                path = os.path.join(root, name)
                with open(path) as f:
                    text = f.read()
                if "$ odatix init" in text and "can now be used by Odatix" in text:
                    pages.append((path, text))
    return pages


def test_the_documentation_shows_the_output_of_init_as_it_is(capsys):
    printc.set_command("odatix init")
    try:
        OdatixSettings.init_success("odatix", examples=True)
    finally:
        printc.set_command("")
    expected = [line.strip() for line in _plain(capsys.readouterr().out).splitlines() if line.strip()]
    pages = _init_output_pages()
    assert len(pages) >= 4
    for path, text in pages:
        shown = re.sub(r"<[^>]+>", "", text)
        assert "[settings.py]" not in shown, path
        for line in expected:
            assert line in shown, (path, line)


def test_the_tutorials_create_their_directory_even_if_it_exists():
    for root, _dirs, files in os.walk(os.path.join(DOCS_DIR, "tutorials", "run_examples")):
        for name in files:
            with open(os.path.join(root, name)) as f:
                assert "$ mkdir ~/odatix_examples" not in f.read(), name
    with open(os.path.join(DOCS_DIR, "docs", "getting-started.md")) as f:
        assert "$ mkdir ~/odatix_examples" not in f.read()


def test_the_installation_pages_say_that_pypi_serves_odatix_3():
    for page in ("_index.md", "pypi.md", "offline.md"):
        with open(os.path.join(DOCS_DIR, "install", page)) as f:
            assert "Odatix 4.0 is not on PyPI yet" in f.read(), page
    with open(os.path.join(DOCS_DIR, "docs", "getting-started.md")) as f:
        assert "Odatix 4.0 is not on PyPI yet" in f.read()


######################################
# Update check
######################################

def test_versions_are_compared_as_numbers():
    assert motd.version_tuple("3.10.0") > motd.version_tuple("3.9.1")
    assert motd.version_tuple("4.0.0") > motd.version_tuple("3.7.3")
    assert motd.version_tuple("4.0.0rc1") == (4, 0, 0)


######################################
# GUI home page
######################################

dash = pytest.importorskip("dash")
pytest.importorskip("dash_svg")


@pytest.fixture(scope="module")
def home():
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.gui.pages.home as home
    return home


def _texts(component):
    found = []
    def walk(node):
        if isinstance(node, str):
            found.append(node)
            return
        if isinstance(node, (list, tuple)):
            for child in node:
                walk(child)
            return
        children = getattr(node, "children", None)
        if children is not None:
            walk(children)
    walk(component)
    return found


def _hrefs(component):
    found = []
    def walk(node):
        if isinstance(node, (list, tuple)):
            for child in node:
                walk(child)
            return
        href = getattr(node, "href", None)
        if href:
            found.append(href)
        children = getattr(node, "children", None)
        if children is not None and not isinstance(children, str):
            walk(children)
    walk(component)
    return found


def test_the_home_cards_follow_a_first_run(home):
    names = [card["name"] for card in home.home_cards]
    assert names[:4] == ["RTL architectures", "Run jobs", "Monitor jobs", "Explore results"]


def test_the_home_page_names_its_workspace_and_where_to_start(home, tmp_path, monkeypatch):
    monkeypatch.chdir(str(tmp_path))
    layout = home.home_layout()
    assert any(str(tmp_path) in text for text in _texts(layout))
    hrefs = _hrefs(layout)
    assert doc_links.GETTING_STARTED_URL in hrefs
    assert doc_links.GLOSSARY_URL in hrefs
    assert doc_links.DOCS_URL in hrefs


def test_a_failed_workspace_creation_is_not_reported_as_created(home, monkeypatch):
    # The result of the creation used to be a one-element tuple, always true.
    monkeypatch.setattr(dash, "ctx", types.SimpleNamespace(triggered_id="create-empty-workspace"))
    monkeypatch.setattr(OdatixSettings, "init_directory_nodialog", staticmethod(lambda **kwargs: False))
    assert home.create_empty_workspace(1, None) is dash.no_update


def test_the_page_not_found_leads_back_home():
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.gui.pages.not_found_404 as not_found
    assert "/" in _hrefs(not_found.layout)
    assert "Page not found" in _texts(not_found.layout)
