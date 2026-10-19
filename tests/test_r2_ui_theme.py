"""Regression tests of the shared GUI/Explorer look (2nd new-user campaign, ui_theme)."""

import os
import re
from types import SimpleNamespace

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "sources", "odatix", "gui", "assets")
THEMES = os.path.join(ASSETS, "themes")


def _read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as f:
        return f.read()


def _rule(css, selector):
    """Body of the first rule whose selector list is exactly `selector`."""
    m = re.search(r"(^|\n)" + re.escape(selector) + r"\s*\{([^}]*)\}", css)
    return m.group(2) if m else None


class TestTooltips:
    def test_tooltip_host_has_no_z_index(self):
        # An info icon must stay under open menus and sticky headers.
        body = _rule(_read(ASSETS, "style.css"), ".tooltip")
        assert body is not None and "z-index" not in body

    def test_no_pseudo_element_bubble_left(self):
        # The ::after bubble widened the page and was clipped by containers.
        assert not re.search(r"^\.tooltip[^{,]*::?after", _read(ASSETS, "style.css"), re.M)

    def test_bubble_is_fixed_and_hidden_by_display(self):
        body = _rule(_read(ASSETS, "style.css"), ".odx-tooltip")
        assert "position: fixed" in body and "display: none" in body

    def test_script_places_and_flips(self):
        js = _read(ASSETS, "tooltips.js")
        for needed in ("data-tooltip", "innerHeight", "pointerdown", "ellipsis"):
            assert needed in js

    def test_steps_popover_not_drawn_while_hidden(self):
        css = _read(ASSETS, "odatix-ui.css")
        assert "display: none" in _rule(css, ".odx-steps-pop")
        assert "odx-pop-left" in css and "odx-pop-left" in _read(ASSETS, "floating_menus.js")

    def test_menus_can_open_upward(self):
        assert ".Select.odx-menu-up .Select-menu-outer" in _read(ASSETS, "style.css")
        assert "odx-menu-up" in _read(ASSETS, "floating_menus.js")


class TestTokens:
    def test_base_declares_contrast_tokens(self):
        base = _read(THEMES, "00_base.css")
        for token in ("--theme-on-primary-color", "--theme-on-success-color", "--theme-placeholder-color",
                      "--theme-secondary-text-color", "--theme-field-border-color", "--theme-mono-font-family"):
            assert token + ":" in base

    def test_no_white_on_primary_hardcoded(self):
        css = _read(ASSETS, "style.css")
        assert not re.search(r"background: var\(--theme-primary-color\);\s*color: #fff", css)
        assert ".monitor-mode-button.active { background: var(--theme-primary-color); color: var(--theme-on-primary-color); }" in css

    def test_pre_is_monospaced(self):
        assert "var(--theme-mono-font-family)" in _rule(_read(ASSETS, "style.css"), "pre")

    def test_placeholders_are_themed(self):
        assert "::placeholder" in _read(ASSETS, "style.css")

    def test_win95_font_leaves_ambiguous_glyphs_to_fallback(self):
        css = _read(THEMES, "win95.css")
        assert "unicode-range" in css and "U+0031-004E" in css

    def test_navbar_text_uses_token(self):
        assert "color: var(--navbar-text-color)" in _rule(_read(ASSETS, "style.css"), ".navbar .nav-links a")


class TestThemePerRequest:
    """A visitor's cookie must never change the server's default theme."""

    def test_gui_start_theme_is_not_stored(self, monkeypatch):
        import odatix.gui.app as app_module
        import odatix.gui.themes as themes
        gui = SimpleNamespace(default_theme="odatix")
        prop = app_module.OdatixApp.start_theme
        monkeypatch.setattr(themes, "theme_from_cookie", lambda default=None: "dracula")
        assert prop.fget(gui) == "dracula"
        assert gui.default_theme == "odatix"
        monkeypatch.setattr(themes, "theme_from_cookie", lambda default=None: default)
        assert prop.fget(gui) == "odatix"

    def test_sources_never_assign_from_cookie(self):
        for path in (("sources", "odatix", "gui", "app.py"), ("sources", "odatix", "explorer", "standalone.py")):
            src = _read(ROOT, *path)
            assert not re.search(r"self\.start_theme\s*=\s*\S*theme_from_cookie", src)
