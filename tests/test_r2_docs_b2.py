"""Lot B2 (documentation): links, titles and navigation fixed in the 2nd pass."""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "sources", "odatix")


def _read(*parts):
    with io.open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def test_no_hard_coded_documentation_url_in_the_code():
    offenders = []
    for base, _dirs, files in os.walk(SRC):
        for name in files:
            path = os.path.join(base, name)
            if not name.endswith(".py") or path.endswith(os.path.join("lib", "doc_links.py")):
                continue
            with io.open(path, encoding="utf-8") as f:
                if "odatix.readthedocs.io" in f.read():
                    offenders.append(path)
    assert offenders == []


def test_glossary_url_comes_from_doc_links():
    import odatix.odatix_main as main
    from odatix.lib import doc_links
    assert main.GLOSSARY_URL == doc_links.GLOSSARY_URL


def test_readme_links_point_to_the_latest_documentation():
    for readme in (("README.md",), ("sources", "README.md")):
        text = _read(*readme)
        assert not re.search(r"odatix\.readthedocs\.io/(docs|install|tutorials)", text)


def test_titles_are_in_sentence_case():
    bad = ("RTL Architectures", "Commands Reference", "Results & Export", "Sessions & Job Monitor")
    for base, _dirs, files in os.walk(os.path.join(ROOT, "docs", "content")):
        for name in files:
            if name.endswith(".md"):
                with io.open(os.path.join(base, name), encoding="utf-8") as f:
                    text = f.read()
                assert not [b for b in bad if b in text], name
    assert 'readMore: "Read more"' in _read("docs", "i18n", "en.yml")


def test_commands_map_has_no_duplicate_category():
    cats = re.findall(r"^\| ([A-Z][^|]*?) \| `odatix", _read("docs", "content", "docs", "commands.md"), re.M)
    assert len(cats) == len(set(cats))


def test_run_jobs_cards_follow_the_beginner_path():
    text = _read("sources", "odatix", "gui", "pages", "choose_job_type.py")
    names = re.findall(r'"name": "([^"]+)"', text)
    assert names[0] == "Run RTL analysis" and names[-1] == "Design space exploration"


def test_theme_selector_is_labelled():
    assert '"aria-label": "Theme"' in _read("sources", "odatix", "gui", "navigation.py")


def test_selection_source_names_the_settings_file_of_the_job_type():
    from odatix.gui.jobs_config.callbacks_config import selection_source_text
    assert selection_source_text("?type=custom_freq_synthesis&tool=vivado", {}) == "Selection loaded from synth_settings.yml"
    assert selection_source_text("?type=fmax_synthesis&tool=vivado", {}) == "Selection loaded from fmax_settings.yml"
    assert selection_source_text("?type=fmax_synthesis", {"fmax_settings_file": "cfg/my.yml"}) == "Selection loaded from my.yml"


def test_own_flows_tutorials_follow_the_run_page():
    for name in ("add_tools.md", "add_targets.md", "add_flows.md"):
        text = _read("docs", "content", "tutorials", "own_flows", name)
        assert "**Override frequencies**" in text and "**Run jobs**" in text, name
