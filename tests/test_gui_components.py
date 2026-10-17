"""Tests for GUI building blocks: icons, pictograms, navigation bar."""

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.gui

dash_svg = pytest.importorskip("dash_svg")
dash = pytest.importorskip("dash")
from dash import dcc, html

import odatix.gui.icons as icons
import odatix.lib.hard_settings as hard_settings
import odatix.gui.navigation as navigation
import odatix.gui.themes as themes


######################################
# "Run jobs" page helper
######################################
#
# The page is split across odatix.gui.jobs_config.* (the page module itself only
# registers it). The tests address it as the single namespace it used to be:
# reads find the module that defines the name, and writes -- the module-level
# prepare state some tests reset, and the "ctx" monkeypatching -- go back to
# every module holding it, so patching reaches the callback that reads it.

JOBS_CONFIG_MODULES = [
    "callbacks_config", "callbacks_run", "callbacks_sim", "common", "prepare_state",
    "checks", "run_popup", "arch_widgets", "pnr", "simulation", "context",
    "settings_io", "settings_form", "layout",
]


class _ModuleGroup:
    def __init__(self, modules):
        object.__setattr__(self, "_modules", modules)

    def __getattr__(self, name):
        for module in self._modules:
            if hasattr(module, name):
                return getattr(module, name)
        raise AttributeError(name)

    def __setattr__(self, name, value):
        holders = [module for module in self._modules if hasattr(module, name)]
        for module in holders or self._modules[:1]:
            setattr(module, name, value)


def import_jobs_config():
    """The "Run jobs" page as one namespace (see _ModuleGroup)."""
    import importlib

    # dash.register_page (called at page-module import) requires an app
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.gui.pages.jobs_config  # noqa: F401  (registers the page)

    return _ModuleGroup([
        importlib.import_module("odatix.gui.jobs_config." + name)
        for name in JOBS_CONFIG_MODULES
    ])

######################################
# Icons
######################################

KNOWN_ICONS = [
    "save", "duplicate", "delete", "generate", "edit", "more", "clean",
    "gear", "back", "check", "tooltip", "reset", "play", "pause", "cross",
]

KNOWN_PICTOGRAMS = [
    "workflow", "architecture", "run", "monitor", "explorer", "dse", "workspace",
    "documentation", "tool", "target", "fmax", "custom_freq", "pnr", "analysis",
    "simulation", "workspace_empty", "workspace_examples",
]


class TestIcons:
    @pytest.mark.parametrize("name", KNOWN_ICONS)
    def test_known_icons_build(self, name):
        # A glyph is a span naming itself; the drawing lives in the stylesheet.
        glyph = icons.icon(name)
        assert glyph is not None
        assert getattr(glyph, "data-icon", None) == name
        assert "odx-icon" in glyph.className

    @pytest.mark.parametrize("name", KNOWN_ICONS)
    def test_known_icons_are_drawn_by_the_stylesheet(self, name):
        stylesheet = icons.icon_stylesheet()
        assert '[data-icon="{0}"]'.format(name) in stylesheet
        # line-art style: stroked with currentColor, no fill
        assert "viewBox=%270 0 24 24%27" in stylesheet

    def test_the_stylesheet_paints_with_the_inherited_color(self):
        # What every ".icon <color>" rule of the theme relies on: the glyph is
        # a mask, and the color it shows is the one it inherits.
        stylesheet = icons.icon_stylesheet()
        assert "background-color:currentColor" in stylesheet
        assert "mask-image:var(--odx-icon)" in stylesheet

    def test_unknown_icon_is_not_drawn(self):
        glyph = icons.icon("does_not_exist")
        assert glyph is not None
        assert not getattr(glyph, "children", None)
        assert "odx-icon" not in (glyph.className or "")

    @pytest.mark.parametrize("name", KNOWN_PICTOGRAMS)
    def test_known_pictograms_build(self, name):
        svg = icons.pictogram(name)
        assert svg is not None
        assert svg.viewBox == "0 0 48 48"
        assert len(svg.children) > 0

    def test_unknown_pictogram_returns_empty_svg(self):
        svg = icons.pictogram("does_not_exist")
        assert svg is not None
        assert not getattr(svg, "children", None)

    def test_icon_size_is_applied(self):
        glyph = icons.icon("save", width="16px", height="16px")
        assert glyph.style["width"] == "16px"
        assert glyph.style["height"] == "16px"


######################################
# Navigation bar
######################################

class TestNavigation:
    def test_nav_groups_structure(self):
        # membership only: the display order is a UI choice
        labels = {entry[0] for entry in navigation.nav_groups}
        assert labels == {"Configure", "Run", "Monitor", "Explorer", "Workspace"}

        as_dict = {entry[0]: entry[1:] for entry in navigation.nav_groups}

        # "Monitor" is a plain link button: (label, href), no dropdown
        assert as_dict["Monitor"] == ("/monitor",)

        # Groups: (label, href, items) -- href may be "" (no page of its own)
        configure_href, configure_items = as_dict["Configure"]
        assert configure_href == ""
        assert ("RTL Architectures", "/architectures") in configure_items
        assert ("Workflows", "/workflows") in configure_items

        run_href, run_items = as_dict["Run"]
        assert run_href == "/choose_job_type"
        assert any(href.startswith("/run_jobs") for _, href in run_items)

        workspace_href, workspace_items = as_dict["Workspace"]
        assert workspace_href == ""
        assert ("Settings", "/workspace") in workspace_items
        assert ("Clean", "/clean") in workspace_items

        explorer_href, explorer_items = as_dict["Explorer"]
        assert explorer_href == "/explorer"
        explorer_paths = {href for _, href in explorer_items}
        # every chart page of the explorer must be reachable from the topbar
        assert explorer_paths >= {
            "/explorer/lines",
            "/explorer/columns",
            "/explorer/scatter",
            "/explorer/scatter3d",
            "/explorer/radar",
            "/explorer/overview",
        }

    def test_nav_group_hrefs_match_registered_pages(self):
        """Every link (group header or dropdown item) must point to a real page."""
        import importlib

        # dash.register_page (called at page-module import) requires an app
        dash.Dash(__name__, use_pages=True, pages_folder="")

        gui_page_paths = set()
        for module_name in (
            "architectures", "workflows", "tools", "derived_metrics", "choose_job_type",
            "choose_eda_tool", "monitor", "workspace_settings", "dse", "clean",
        ):
            module = importlib.import_module(f"odatix.gui.pages.{module_name}")
            gui_page_paths.add(module.page_path)

        # explorer pages register themselves on import
        import odatix.explorer.pages  # noqa: F401
        explorer_paths = {page["path"] for page in dash.page_registry.values()}

        known_paths = gui_page_paths | explorer_paths | {"/run_jobs"}

        def base_path(href):
            # strip query string and in-page anchor ("/architectures#simulations")
            return href.split("?", 1)[0].split("#", 1)[0]

        for entry in navigation.nav_groups:
            if len(entry) == 2:
                _, href = entry
                assert base_path(href) in known_paths, f"dead link in topbar: {href}"
                continue
            _, href, items = entry
            if href:
                assert base_path(href) in known_paths, f"dead link in topbar: {href}"
            for _, item_href in items:
                assert base_path(item_href) in known_paths, f"dead link in topbar: {item_href}"

    def test_nav_entry_plain_button(self):
        rendered = navigation._nav_entry(("Monitor", "/monitor"))
        assert isinstance(rendered, dcc.Link)
        assert rendered.href == "/monitor"
        assert rendered.className == "nav-link-button"

    def test_nav_entry_group_with_own_page(self):
        entry = navigation._nav_entry(("Run", "/choose_job_type", [("A", "/a"), ("B", "/b")]))
        assert entry.className == "nav-group"
        header, dropdown = entry.children
        # header is a real link: clicking it navigates to the group's own page
        assert isinstance(header, dcc.Link)
        assert header.href == "/choose_job_type"
        assert header.className == "nav-group-label"
        assert dropdown.className == "nav-dropdown"
        assert [link.href for link in dropdown.children] == ["/a", "/b"]

    def test_nav_entry_group_without_own_page(self):
        entry = navigation._nav_entry(("Configure", "", [("A", "/a")]))
        header, _ = entry.children
        # no href: header is not a link, just a hover/focus target
        assert isinstance(header, html.Span)
        assert header.className == "nav-group-label"
        assert header.tabIndex == "0"

    def test_top_bar_builds(self):
        gui = SimpleNamespace(start_theme="dark")
        bar = navigation.top_bar(gui)
        assert bar is not None
        rendered = str(bar)
        assert "nav-burger" in rendered
        assert "nav-menu" in rendered

    def test_top_bar_contains_theme_dropdown(self):
        gui = SimpleNamespace(start_theme=themes.default_theme)
        rendered = str(navigation.top_bar(gui))
        assert "theme-dropdown" in rendered

    def test_setup_callbacks_registers(self):
        app = dash.Dash(__name__)
        gui = SimpleNamespace(app=app, start_theme="dark")
        navigation.setup_callbacks(gui)
        assert len(app.callback_map) >= 3

    def test_choose_targets_link_follows_url_tool(self):
        jobs_config = import_jobs_config()

        href, _cls = jobs_config.update_choose_targets_link("?type=fmax&tool=openlane")
        assert href == "/select_targets?tool=openlane"
        href, _cls = jobs_config.update_choose_targets_link("?type=fmax&tool=design_compiler")
        assert href == "/select_targets?tool=design_compiler"
        # no tool in the url: same default as the rest of the page
        href, _cls = jobs_config.update_choose_targets_link("")
        assert href == "/select_targets?tool=vivado"

    def test_choose_targets_link_hidden_for_analyze(self):
        # RTL analysis does not use target definition files: the "Choose
        # Targets" button is hidden for ?type=analyze, unlike every other run mode.
        dash.Dash(__name__, use_pages=True, pages_folder="")
        jobs_config = import_jobs_config()

        _href, cls = jobs_config.update_choose_targets_link("?type=analyze&tool=vivado")
        assert cls == "hidden"

        # sanity: a non-analyze mode keeps the button visible
        _href, cls = jobs_config.update_choose_targets_link("?type=fmax_synthesis&tool=vivado")
        assert cls != "hidden"
        assert "disabled" not in cls


######################################
# Run jobs page: architectures vs workflows
######################################

class TestRunContext:
    @pytest.fixture(autouse=True)
    def jobs_config_module(self):
        jobs_config = import_jobs_config()

        return jobs_config

    def test_workflow_context(self, jobs_config_module):
        settings = {"workflow_path": "cfg/workflows", "workflow_settings_file": "cfg/workflow_settings.yml"}
        ctx = jobs_config_module._run_context("?type=workflow", settings)
        assert ctx["mode"] == "workflow"
        assert ctx["base_path"] == "cfg/workflows"
        assert ctx["settings_path"] == "cfg/workflow_settings.yml"
        assert ctx["selection_key"] == "workflows"
        assert ctx["title"] == "Workflows"
        assert ctx["settings_link"]("wf1") == "/workflow_editor?workflow=wf1"
        assert ctx["config_link"]("wf1") == "/config_editor?workflow=wf1"

    def test_fmax_context(self, jobs_config_module):
        settings = {"arch_path": "cfg/archs", "fmax_synthesis_settings_file": "cfg/fmax.yml"}
        ctx = jobs_config_module._run_context("?type=fmax_synthesis", settings)
        assert ctx["mode"] == "arch"
        assert ctx["base_path"] == "cfg/archs"
        assert ctx["settings_path"] == "cfg/fmax.yml"
        assert ctx["selection_key"] == "architectures"
        assert ctx["title"] == "Architectures"
        assert ctx["settings_link"]("a1") == "/arch_editor?arch=a1"
        assert ctx["config_link"]("a1") == "/config_editor?arch=a1"

    def test_custom_freq_context_is_arch(self, jobs_config_module):
        ctx = jobs_config_module._run_context("?type=custom_freq_synthesis", {})
        assert ctx["mode"] == "arch"
        assert ctx["selection_key"] == "architectures"


######################################
# Run jobs page: domain-value wildcards ("domain/*", bare "arch/*")
######################################
#
# Odatix's own wildcard syntax (ArchitectureHandler.configuration_wildcard(), used
# at run time) lets a saved selection entry use "*" for a domain value, e.g.
# "Arch + addr/* + data/*" or the bare main-domain form "Arch/*". The GUI used to
# literal-match saved entries against the generated combo strings, so a wildcard
# entry never matched anything: the per-domain checklist showed nothing checked,
# and worse, the preview checklist (which drives what actually gets saved back on
# the next Save) silently dropped the wildcard-selected combos entirely.

class TestWildcardSelectionExpansion:
    @pytest.fixture(autouse=True)
    def jobs_config_module(self):
        dash.Dash(__name__, use_pages=True, pages_folder="")
        jobs_config = import_jobs_config()

        return jobs_config

    def test_no_wildcard_passes_through_unchanged(self, jobs_config_module):
        domains_configs = {"addr": ["4", "8"], "data": ["32", "64"]}
        result = jobs_config_module._expand_wildcard_selection(
            "Arch + addr/4 + data/32", domains_configs, "Arch"
        )
        assert result == ["Arch + addr/4 + data/32"]

    def test_bare_main_domain_wildcard(self, jobs_config_module):
        import odatix.lib.hard_settings as hard_settings

        domains_configs = {hard_settings.main_parameter_domain: ["04bits", "08bits", "16bits"]}
        result = jobs_config_module._expand_wildcard_selection("Arch/*", domains_configs, "Arch")
        assert sorted(result) == ["Arch/04bits", "Arch/08bits", "Arch/16bits"]

    def test_multi_domain_wildcard_cross_product(self, jobs_config_module):
        domains_configs = {"addr": ["4", "8"], "data": ["32", "64"]}
        result = jobs_config_module._expand_wildcard_selection(
            "Arch + addr/* + data/*", domains_configs, "Arch"
        )
        assert sorted(result) == sorted([
            "Arch + addr/4 + data/32",
            "Arch + addr/4 + data/64",
            "Arch + addr/8 + data/32",
            "Arch + addr/8 + data/64",
        ])

    def test_mixed_fixed_and_wildcard_domains(self, jobs_config_module):
        domains_configs = {"addr": ["4", "8"], "data": ["32", "64"]}
        result = jobs_config_module._expand_wildcard_selection(
            "Arch + addr/4 + data/*", domains_configs, "Arch"
        )
        assert sorted(result) == ["Arch + addr/4 + data/32", "Arch + addr/4 + data/64"]

    def test_matches_real_generate_config_combinations_output(self, jobs_config_module, example_workspace):
        """
        The expanded strings must be byte-for-byte identical to what
        odatix.workspace.configs.combinations() produces for the same
        architecture, since that's what the preview checklist matches against.
        """
        from odatix.workspace.configs import combinations

        arch_name = "Example_Rom_Chisel"
        architecture = architecture_collection("odatix_userconfig/architectures")[arch_name]
        # What the page itself feeds the expansion: the configurations each
        # domain resolves to, which for this architecture are described by
        # rules and written nowhere.
        domains_configs = {
            domain.name: domain.configuration_names()
            for domain in architecture.domains
            if not domain.is_main
        }
        real_combos = {" + ".join(c) for c in combinations(domains_configs, arch_name)}

        expanded = jobs_config_module._expand_wildcard_selection(
            f"{arch_name} + addr/* + data/*", domains_configs, arch_name
        )
        assert set(expanded) == real_combos
        assert len(expanded) > 1  # sanity: this arch has more than one addr/data combo


@pytest.mark.integration
class TestUpdateParamDomainsWithWildcards:
    """End-to-end: a saved selection using Odatix's "*" wildcard syntax must
    render with the corresponding configurations checked, both in the
    per-domain checklist and in the preview checklist (the preview drives what
    gets saved back, so this is the one that must not silently drop combos)."""

    @pytest.fixture(autouse=True)
    def jobs_config_module(self, monkeypatch):
        dash.Dash(__name__, use_pages=True, pages_folder="")
        jobs_config = import_jobs_config()
        from types import SimpleNamespace

        monkeypatch.setattr(jobs_config, "ctx", SimpleNamespace(triggered_id=None))
        return jobs_config

    def _render(self, jobs_config_module, settings_path, odatix_settings=None):
        odatix_settings = odatix_settings or {}
        odatix_settings.setdefault("arch_path", "odatix_userconfig/architectures")
        odatix_settings.setdefault("custom_freq_synthesis_settings_file", settings_path)
        return jobs_config_module.update_param_domains(
            "?type=custom_freq_synthesis", "/run_jobs", odatix_settings
        )

    @staticmethod
    def _find_all(node, predicate, found=None):
        if found is None:
            found = []
        if isinstance(node, (list, tuple)):
            for item in node:
                TestUpdateParamDomainsWithWildcards._find_all(item, predicate, found)
            return found
        if predicate(node):
            found.append(node)
        children = getattr(node, "children", None)
        if isinstance(children, (list, tuple)):
            for child in children:
                TestUpdateParamDomainsWithWildcards._find_all(child, predicate, found)
        elif children is not None:
            TestUpdateParamDomainsWithWildcards._find_all(children, predicate, found)
        return found

    def _checklists_for_arch(self, job_section, arch_name, checklist_type):
        return self._find_all(
            job_section,
            lambda n: (
                isinstance(getattr(n, "id", None), dict)
                and n.id.get("type") == checklist_type
                and n.id.get("arch") == arch_name
            ),
        )

    def test_bare_main_domain_wildcard_checks_everything(self, jobs_config_module, example_workspace):
        arch_name = "Example_Counter_verilog"
        settings_path = "odatix_userconfig/tmp_wildcard_settings.yml"
        with open(settings_path, "w") as f:
            f.write(
                "overwrite: No\nask_continue: No\nexit_when_done: No\n"
                "log_size_limit: 300\nnb_jobs: 8\nforce_single_thread: No\n"
                "frequencies:\n  override: No\n  list: []\n"
                f"architectures:\n  - {arch_name}/*\n"
            )
        job_section, _, _, _ = self._render(jobs_config_module, settings_path)

        domain_checklists = self._checklists_for_arch(job_section, arch_name, "domain-config-checklist")
        assert domain_checklists  # sanity: the architecture rendered
        for checklist in domain_checklists:
            assert set(checklist.value) == {opt["value"] for opt in checklist.options}

        preview_checklists = self._checklists_for_arch(job_section, arch_name, "preview-config-checklist")
        assert len(preview_checklists) == 1
        preview = preview_checklists[0]
        # every non-default combo must be selected: the wildcard must not
        # silently drop combos from what would be saved back
        non_default_options = [opt["value"] for opt in preview.options if opt["value"] != arch_name]
        assert non_default_options  # sanity
        assert set(preview.value) & set(non_default_options) == set(non_default_options)

    def test_multi_domain_wildcard_checks_everything(self, jobs_config_module, example_workspace):
        arch_name = "Example_Rom_Chisel"
        settings_path = "odatix_userconfig/tmp_wildcard_settings2.yml"
        with open(settings_path, "w") as f:
            f.write(
                "overwrite: No\nask_continue: No\nexit_when_done: No\n"
                "log_size_limit: 300\nnb_jobs: 8\nforce_single_thread: No\n"
                "frequencies:\n  override: No\n  list: []\n"
                f"architectures:\n  - {arch_name} + addr/* + data/*\n"
            )
        job_section, _, _, _ = self._render(jobs_config_module, settings_path)

        domain_checklists = self._checklists_for_arch(job_section, arch_name, "domain-config-checklist")
        assert domain_checklists
        for checklist in domain_checklists:
            assert set(checklist.value) == {opt["value"] for opt in checklist.options}

        preview_checklists = self._checklists_for_arch(job_section, arch_name, "preview-config-checklist")
        assert len(preview_checklists) == 1
        preview = preview_checklists[0]
        non_default_options = [opt["value"] for opt in preview.options if opt["value"] != arch_name]
        assert non_default_options
        assert set(preview.value) & set(non_default_options) == set(non_default_options)


@pytest.mark.integration
class TestSavedBaselineOnLoad:
    """
    On a fresh page load, update_param_domains() must emit a "saved" baseline
    that matches exactly the widget-derived "current" selection computed by
    save_architecture_selections(), so the page does not falsely report
    "Unsaved changes!" right after loading (the store starts empty and is only
    written on Save otherwise).
    """

    @pytest.fixture(autouse=True)
    def jobs_config_module(self, monkeypatch):
        dash.Dash(__name__, use_pages=True, pages_folder="")
        jobs_config = import_jobs_config()
        from types import SimpleNamespace

        monkeypatch.setattr(jobs_config, "ctx", SimpleNamespace(triggered_id="test-trigger"))
        return jobs_config

    @staticmethod
    def _collect(node, id_type, found=None, extra_key=None):
        """Collect (value, id) of every component whose id has id["type"] == id_type."""
        if found is None:
            found = []
        if isinstance(node, (list, tuple)):
            for item in node:
                TestSavedBaselineOnLoad._collect(item, id_type, found, extra_key)
            return found
        nid = getattr(node, "id", None)
        if isinstance(nid, dict) and nid.get("type") == id_type:
            if extra_key is None or nid.get(extra_key[0]) == extra_key[1]:
                found.append((getattr(node, "value", None), nid))
        children = getattr(node, "children", None)
        if isinstance(children, (list, tuple)):
            for child in children:
                TestSavedBaselineOnLoad._collect(child, id_type, found, extra_key)
        elif children is not None:
            TestSavedBaselineOnLoad._collect(children, id_type, found, extra_key)
        return found

    def _load_and_check(self, jobs_config_module, search, settings_key, settings_path, analysis_tools=None):
        odatix_settings = {
            "arch_path": "odatix_userconfig/architectures",
            settings_key: settings_path,
        }
        job_sections, _heading, _title, saved_baseline = jobs_config_module.update_param_domains(
            search, "/run_jobs", odatix_settings
        )

        switches = self._collect(job_sections, "arch-title", extra_key=("is_switch", True))
        switch_values = [v for v, _ in switches]
        switch_ids = [i for _, i in switches]
        previews = self._collect(job_sections, "preview-config-checklist")
        preview_values = [v for v, _ in previews]
        preview_ids = [i for _, i in previews]

        # The Job Settings widgets live in the form (rendered by init_form, not
        # update_param_domains); recreate their loaded values the same way
        # job_settings_form() does, so "current" matches the emitted baseline.
        from odatix.workspace.yaml_io import read_yaml
        file_settings = read_yaml(settings_path, default={})
        js = jobs_config_module._job_settings_baseline(file_settings)
        overwrite_w = [True] if js["overwrite"] else []
        fst_w = [True] if js["force_single_thread"] else []
        ask_w = [True] if js["ask_continue"] else []
        exit_w = [True] if js["exit_when_done"] else []
        nb_w = str(js["nb_jobs"])
        log_w = str(js["log_size_limit"])

        # Feed the freshly-rendered widget state back into the save callback,
        # with the baseline update_param_domains() just emitted: it must report
        # "Nothing to save", not "Unsaved changes!".
        className, tooltip, _store, _feedback = jobs_config_module.save_architecture_selections(
            None,                 # save-all n_clicks
            switch_values,
            preview_values,
            [],                   # sim-selection stores (simulation mode only)
            [],                   # sim-architectures stores (simulation mode only)
            [],                   # override-arch-frequencies
            [],                   # use-custom-freq-list
            "",                   # target_frequencies
            [],                   # use-custom-freq-range
            "", "", "",           # from/to/step
            "", "",               # lower/upper fmax bound
            analysis_tools,       # analysis-tools
            overwrite_w,
            fst_w,
            nb_w,
            [],                   # auto-nb-jobs
            log_w,
            ask_w,
            exit_w,
            switch_ids,
            preview_ids,
            [],                   # sim-selection store ids
            [],                   # sim-architectures store ids
            saved_baseline,       # jobs-config-saved-selection = the emitted baseline
            search,
            "/run_jobs",
            odatix_settings,
        )
        assert tooltip == "Nothing to save", f"false unsaved-changes: {tooltip}"
        assert "disabled" in className
        return saved_baseline

    def test_fmax_no_false_unsaved(self, example_workspace):
        settings_path = "odatix_userconfig/fmax_synthesis_settings.yml"
        with open(settings_path, "w") as f:
            f.write(
                "overwrite: No\nask_continue: No\nexit_when_done: No\n"
                "log_size_limit: 300\nnb_jobs: 8\nforce_single_thread: No\n"
                "architectures:\n"
                "  - Example_Counter_verilog/04bits\n"
                "  - Example_Counter_verilog/08bits\n"
            )
        jc = import_jobs_config()
        baseline = self._load_and_check(
            jc, "?type=fmax_synthesis", "fmax_synthesis_settings_file", settings_path
        )
        assert set(baseline["architectures"]) == {
            "Example_Counter_verilog/04bits", "Example_Counter_verilog/08bits"
        }

    def test_analyze_no_false_unsaved_with_tools_and_url_tool(self, example_workspace):
        # Reproduces the reported case: file has tools:[] but ?tool=vivado, and
        # architectures selected; a refresh must not show "Unsaved changes".
        settings_path = "odatix_userconfig/analysis_settings.yml"
        with open(settings_path, "w") as f:
            f.write(
                "overwrite: No\nask_continue: No\nexit_when_done: No\n"
                "log_size_limit: 300\nnb_jobs: 8\nforce_single_thread: No\n"
                "tools: []\n"
                "architectures:\n"
                "  - Example_Counter_sv/04bits\n"
                "  - Example_Counter_sv/08bits\n"
            )
        jc = import_jobs_config()
        # the tools checklist is initialized (init_form) from file tools + url tool
        analysis_tools = jc._analysis_tools_selection("?type=analyze&tool=vivado", settings_path)
        assert analysis_tools == ["vivado"]  # sanity: matches the reported "current"
        baseline = self._load_and_check(
            jc, "?type=analyze&tool=vivado", "analysis_settings_file", settings_path,
            analysis_tools=analysis_tools,
        )
        assert baseline["tools"] == ["vivado"]

    def test_wildcard_selection_no_false_unsaved(self, example_workspace):
        # A saved wildcard entry expands in the widgets; the baseline must use
        # the same expanded form so no false "unsaved changes" on load.
        settings_path = "odatix_userconfig/fmax_synthesis_settings.yml"
        with open(settings_path, "w") as f:
            f.write(
                "overwrite: No\nask_continue: No\nexit_when_done: No\n"
                "log_size_limit: 300\nnb_jobs: 8\nforce_single_thread: No\n"
                "architectures:\n"
                "  - Example_Rom_Chisel + addr/* + data/*\n"
            )
        jc = import_jobs_config()
        baseline = self._load_and_check(
            jc, "?type=fmax_synthesis", "fmax_synthesis_settings_file", settings_path
        )
        assert len(baseline["architectures"]) > 1  # expanded, not the raw wildcard entry

    def test_job_settings_change_is_detected_as_unsaved(self, example_workspace):
        # Changing a Job Settings field (here nb_jobs) must switch the button to
        # "Unsaved changes!" (previously these fields were not wired at all).
        jc = import_jobs_config()

        settings_path = "odatix_userconfig/fmax_synthesis_settings.yml"
        with open(settings_path, "w") as f:
            f.write(
                "overwrite: No\nask_continue: No\nexit_when_done: No\n"
                "log_size_limit: 300\nnb_jobs: 8\nforce_single_thread: No\n"
                "architectures:\n  - Example_Counter_verilog/04bits\n"
            )
        odatix_settings = {
            "arch_path": "odatix_userconfig/architectures",
            "fmax_synthesis_settings_file": settings_path,
        }
        job_sections, _h, _t, baseline = jc.update_param_domains(
            "?type=fmax_synthesis", "/run_jobs", odatix_settings
        )
        switches = self._collect(job_sections, "arch-title", extra_key=("is_switch", True))
        previews = self._collect(job_sections, "preview-config-checklist")

        className, tooltip, _store, _feedback = jc.save_architecture_selections(
            None,
            [v for v, _ in switches], [v for v, _ in previews],
            [],                            # sim-selection stores (simulation mode only)
            [],                            # sim-architectures stores (simulation mode only)
            [], [], "", [], "", "", "",   # frequency inputs
            "", "",                        # lower/upper fmax bound
            None,                          # analysis-tools
            [], [], "16", [], "300", [], [],   # nb_jobs changed 8 -> 16
            [i for _, i in switches], [i for _, i in previews],
            [],                            # sim-selection store ids
            [],                            # sim-architectures store ids
            baseline,
            "?type=fmax_synthesis", "/run_jobs", odatix_settings,
        )
        assert tooltip == "Unsaved changes!"
        assert "warning" in className

    def test_no_flash_while_baseline_not_set(self, example_workspace):
        # During load, init_form (fast) can render the form and trigger the save
        # callback before update_param_domains (slower) has set the baseline
        # store. While the store is still None, the callback must NOT flash
        # "Unsaved changes!" -- it leaves the button untouched (no_update).
        jc = import_jobs_config()
        import dash as _dash

        settings_path = "odatix_userconfig/analysis_settings.yml"
        with open(settings_path, "w") as f:
            f.write(
                "overwrite: No\nask_continue: No\nexit_when_done: No\n"
                "log_size_limit: 300\nnb_jobs: 8\nforce_single_thread: No\n"
                "tools: []\n"
                "architectures:\n  - Example_Counter_sv/04bits\n"
            )
        odatix_settings = {
            "arch_path": "odatix_userconfig/architectures",
            "analysis_settings_file": settings_path,
        }
        # Form widgets already rendered (tools=['vivado'] from ?tool=vivado) but
        # the arch section / baseline store are not ready yet: saved_selection=None.
        className, tooltip, store, _feedback = jc.save_architecture_selections(
            None,
            [], [],                        # no arch widgets yet
            [],                            # sim-selection stores (simulation mode only)
            [],                            # sim-architectures stores (simulation mode only)
            [], [], "", [], "", "", "",
            "", "",                        # lower/upper fmax bound
            ["vivado"],                    # analysis-tools already rendered
            [], [], "8", [], "300", [], [],
            [], [],
            [],                            # sim-selection store ids
            [],                            # sim-architectures store ids
            None,                          # jobs-config-saved-selection still None
            "?type=analyze&tool=vivado", "/run_jobs", odatix_settings,
        )
        assert className is _dash.no_update
        assert tooltip is _dash.no_update
        assert store is _dash.no_update


def _walk(node):
    """Every component of a layout tree, depth first."""
    if isinstance(node, (list, tuple)):
        for item in node:
            for found in _walk(item):
                yield found
        return
    if node is None or isinstance(node, str):
        return
    yield node
    children = getattr(node, "children", None)
    if children is not None:
        for found in _walk(children):
            yield found


class TestSimulationListedArchitectures:
    """
    The architectures a simulation runs on are edited on the page
    (the cross on a card, the dropdown below them) but only written to the
    simulations' own settings files by Save, like everything else the page
    edits.
    """

    SIM = "TB_Example_Counter_GHDL"

    @pytest.fixture(autouse=True)
    def jobs_config_module(self, monkeypatch):
        dash.Dash(__name__, use_pages=True, pages_folder="")
        jc = import_jobs_config()
        monkeypatch.setattr(jc, "ctx", SimpleNamespace(triggered_id="test-trigger"))
        return jc

    @staticmethod
    def _settings(workspace):
        return {
            "arch_path": "odatix_userconfig/architectures",
            "sim_path": "odatix_userconfig/simulations",
            "simulation_settings_file": "odatix_userconfig/simulation_settings.yml",
        }

    def _load(self, jc, workspace):
        odatix_settings = self._settings(workspace)
        sections, _h, _t, baseline = jc.update_param_domains(
            "?type=simulation", "/run_jobs", odatix_settings
        )
        return odatix_settings, sections, baseline

    @staticmethod
    def _stores(sections, id_type):
        """(data, id) of every dcc.Store of that id type (_collect reads .value)."""
        return [
            (getattr(node, "data", None), nid)
            for node, nid in [
                (n, n.id)
                for n in _walk(sections)
                if isinstance(getattr(n, "id", None), dict) and n.id.get("type") == id_type
            ]
        ]

    @staticmethod
    def _sim_cards(sections, sim_name):
        return [
            nid.get("arch")
            for _v, nid in TestSavedBaselineOnLoad._collect(sections, "sim-arch-card")
            if nid.get("sim") == sim_name
        ]

    def _set_architectures(self, jc, workspace, names):
        jc.get_workspace(self._settings(workspace)).simulations.entry(self.SIM).update(
            architectures=list(names)
        )

    def _sim_settings_file(self, workspace):
        return workspace / "odatix_userconfig" / "simulations" / self.SIM / "_settings.yml"

    def test_empty_list_means_no_architecture(self, example_workspace):
        jc = import_jobs_config()
        path = self._sim_settings_file(example_workspace)
        self._set_architectures(jc, example_workspace, [])

        _settings, sections, baseline = self._load(jc, example_workspace)
        assert self._sim_cards(sections, self.SIM) == []
        assert baseline[jc.ARCHITECTURES_BASELINE_KEY][self.SIM] == []

    def test_saving_the_list_keeps_what_an_architecture_holds(self, example_workspace):
        # The page edits which architectures a simulation runs on, nothing else:
        # the parameter domains an entry carries must survive a Save.
        jc = import_jobs_config()
        path = self._sim_settings_file(example_workspace)
        workspace = jc.get_workspace(self._settings(example_workspace))
        workspace.simulations.entry(self.SIM).update(architectures=[
            {"Example_Counter_vhdl": {"param_domains": {"MEM": {"use_parameters": False}}}},
            "Example_Counter_verilog",
        ])

        odatix_settings, sections, baseline = self._load(jc, example_workspace)
        listed_ids = [{"type": "sim-architectures", "sim": self.SIM}]
        className, tooltip, store, _feedback = self._save(
            jc, odatix_settings, baseline, [["Example_Counter_vhdl"]], listed_ids,
            save_clicks=1, sections=sections,
        )
        assert tooltip == "Nothing to save"
        assert "Example_Counter_verilog" not in path.read_text()
        entries = jc.sim_architectures.parse(
            jc.get_workspace(odatix_settings).simulations.entry(self.SIM).settings.architectures
        )
        assert jc.sim_architectures.names(entries) == ["Example_Counter_vhdl"]
        assert entries[0].param_domains == {"MEM": {"use_parameters": False}}

    def test_editing_the_list_is_not_written_until_save(self, example_workspace):
        jc = import_jobs_config()
        path = self._sim_settings_file(example_workspace)
        self._set_architectures(jc, example_workspace, ["Example_Counter_vhdl"])

        odatix_settings, sections, baseline = self._load(jc, example_workspace)
        assert self._sim_cards(sections, self.SIM) == ["Example_Counter_vhdl"]

        # The dropdown adding an architecture only updates the store...
        listed_ids = [{"type": "sim-architectures", "sim": self.SIM}]
        edited = ["Example_Counter_vhdl", "Example_Counter_verilog"]
        className, tooltip, store, _feedback = self._save(
            jc, odatix_settings, baseline, [edited], listed_ids, save_clicks=None,
            sections=sections,
        )
        assert tooltip == "Unsaved changes!"
        assert "warning" in className
        assert store is dash.no_update
        assert "Example_Counter_verilog" not in path.read_text()

        # ... and Save is what reaches the simulation's settings file.
        className, tooltip, store, _feedback = self._save(
            jc, odatix_settings, baseline, [edited], listed_ids, save_clicks=1,
            sections=sections,
        )
        assert tooltip == "Nothing to save"
        assert store[jc.ARCHITECTURES_BASELINE_KEY] == {self.SIM: edited}
        assert jc._listed_architectures(
            jc.get_workspace(odatix_settings).simulations, self.SIM
        ) == edited

    def _save(self, jc, odatix_settings, baseline, listed_values, listed_ids, save_clicks,
              sections=None):
        triggered = {"page": "/run_jobs", "action": "save-all"} if save_clicks else "test-trigger"
        jc.ctx = SimpleNamespace(triggered_id=triggered)
        # The simulation switches and selections are left as they were loaded, so
        # only the architecture lists differ from the baseline.
        switches = TestSavedBaselineOnLoad._collect(
            sections or [], "arch-title", extra_key=("is_switch", True)
        )
        selections = self._stores(sections or [], "sim-selection")
        return jc.save_architecture_selections(
            save_clicks,
            [v for v, _ in switches], [],
            [v for v, _ in selections],
            listed_values,
            [], [], "", [], "", "", "",
            "", "",
            None,
            [], [], "8", [], "300", [], [],
            [i for _, i in switches], [],
            [i for _, i in selections],
            listed_ids,
            baseline,
            "?type=simulation", "/run_jobs", odatix_settings,
        )


class TestWorkflowCheckSettings:
    """
    _run_check_workflow_settings runs run_workflow.check_settings() and
    stores the result in module-level state, polled by the GUI popup. Call it
    directly (not through a background thread) against the packaged example
    workspace, which already defines valid workflow selections.
    """

    @pytest.fixture(autouse=True)
    def jobs_config_module(self):
        dash.Dash(__name__, use_pages=True, pages_folder="")
        jobs_config = import_jobs_config()

        # Isolate module-level prepare state between tests
        jobs_config._prepare_log_buffer = jobs_config._ThreadSafeBuffer()
        jobs_config._prepare_status = {"status": "checking", "error": None}
        jobs_config._prepare_run = None
        return jobs_config

    def check(self, jobs_config_module, settings_file="odatix_userconfig/workflow_settings.yml"):
        from odatix.workspace import Workspace

        jobs_config_module.start_check(
            "workflow",
            Workspace.open(),
            settings_file=settings_file,
            overwrite=False,
            noask=True,
            exit_when_done=False,
            log_size_limit=300,
            nb_jobs=4,
        )
        return jobs_config_module._prepare_run

    def test_valid_selection_is_checked(self, jobs_config_module, example_workspace):
        run = self.check(jobs_config_module)
        assert jobs_config_module._prepare_status == {"status": "checked", "error": None}
        assert run is not None and run.was_checked
        assert len(run.jobs) > 0

    def test_missing_settings_file_is_reported_as_error(self, jobs_config_module, in_tmp_dir):
        run = self.check(jobs_config_module, settings_file="nonexistent_workflow_settings.yml")
        # The run reports a settings file it cannot read instead of stopping the
        # process; the page turns that into a normal "error" status.
        assert jobs_config_module._prepare_status["status"] == "error"
        assert not run.was_checked

    def test_prepare_dispatches_to_run_workflow(self, jobs_config_module, example_workspace, monkeypatch):
        self.check(jobs_config_module)
        assert jobs_config_module._prepare_status["status"] == "checked"

        called = {}

        def fake_prepare_workflows(**kwargs):
            called.update(kwargs)
            return "fake-parallel-jobs"

        import odatix.components.run_workflow as run_workflow

        monkeypatch.setattr(run_workflow, "prepare_workflows", fake_prepare_workflows)
        jobs_config_module._prepare_synth_type = "workflow"
        jobs_config_module.start_prepare()

        assert jobs_config_module._prepare_status == {"status": "prepared", "error": None}
        assert jobs_config_module._prepare_parallel_jobs == "fake-parallel-jobs"
        assert "workflow_instances" in called
        assert "prepare_job" in called


def workflow_collection(path):
    """The workflows of a directory, as the jobs config page works on them."""
    from odatix.workspace.workflows import WorkflowCollection

    return WorkflowCollection(None, path)


def architecture_collection(path):
    """The architectures of a directory, as the jobs config page works on them."""
    from odatix.workspace.architectures import ArchitectureCollection

    return ArchitectureCollection(None, path)


class TestWorkflowVirtualParamDomains:
    """
    Workflows can define command-placeholder variables ("virtual" parameter
    domains, no directory on disk) under generate_configurations_settings.variables
    in their _settings.yml -- see run_workflow.py's
    virtual_param_domain.get_virtual_domain_names / build_variants, used by
    check_settings() to expand a workflow request into one instance per
    generated variant. _virtual_variant_tokens() reuses that exact logic to
    offer the same combinations as selectable checkboxes in the GUI. It returns
    the token lists alone ("domain/value", no name prefix): they are appended to
    every physical combination by the caller.
    """

    @pytest.fixture(autouse=True)
    def jobs_config_module(self):
        dash.Dash(__name__, use_pages=True, pages_folder="")
        jobs_config = import_jobs_config()

        return jobs_config

    def test_workflow_without_variables_returns_nothing(self, jobs_config_module, example_workspace):
        combos, domain_values, error = jobs_config_module._virtual_variant_tokens(
            workflow_collection("odatix_userconfig/workflows"), "cli_profile", "workflow"
        )
        assert combos == []
        assert domain_values == {}
        assert error is None

    def test_workflow_with_variables_generates_all_combos(self, jobs_config_module, example_workspace):
        combos, domain_values, error = jobs_config_module._virtual_variant_tokens(
            workflow_collection("odatix_userconfig/workflows"), "param_domains_cli_variables", "workflow"
        )
        assert error is None
        # 3 max_speed x 2 num_vehicles x 2 signal_timing x 2 road_length = 24
        assert len(combos) == 24
        assert domain_values == {
            "max_speed": ["35kmh", "45kmh", "55kmh"],
            "num_vehicles": ["100", "300"],
            "signal_timing": ["15s", "45s"],
            "road_length": ["1km", "5km"],
        }
        # tokens join with the workflow name into the exact
        # "name + domain/value + ..." format used by workflow_settings.yml
        combo_strings = {" + ".join(["param_domains_cli_variables"] + combo) for combo in combos}
        assert "param_domains_cli_variables + max_speed/35kmh + num_vehicles/100 + signal_timing/15s + road_length/1km" in combo_strings

    def test_combos_are_accepted_by_run_workflow_check_settings(self, jobs_config_module, example_workspace):
        """The exact strings offered in the GUI must resolve to real instances."""
        import odatix.components.run_workflow as run_workflow
        from odatix.gui.jobs_config.settings_io import write_run_settings
        from odatix.workspace.yaml_io import read_yaml

        combos, _, _ = jobs_config_module._virtual_variant_tokens(
            workflow_collection("odatix_userconfig/workflows"), "param_domains_cli_variables", "workflow"
        )
        selection = " + ".join(["param_domains_cli_variables"] + combos[0])
        path = "odatix_userconfig/workflow_settings.yml"
        base = read_yaml(path, default={})
        write_run_settings(path, {**base, "workflows": [selection]}, "workflow")

        instances, *_ = run_workflow.check_settings(
            run_config_settings_filename=path,
            workflow_path="odatix_userconfig/workflows",
            work_path="work/workflows",
            overwrite=False,
            noask=True,
            exit_when_done=False,
            log_size_limit=300,
            nb_jobs=4,
        )
        assert len(instances) == 1
        assert instances[0].workflow_name == "param_domains_cli_variables"

    def test_invalid_variable_type_degrades_gracefully(self, jobs_config_module, tmp_path):
        # An invalid variable "type" doesn't crash: config_generator.generate()
        # returns no combinations for it rather than raising.
        workflow_dir = tmp_path / "workflows" / "bad_workflow"
        workflow_dir.mkdir(parents=True)
        (workflow_dir / "_settings.yml").write_text(
            "generate_configurations_settings:\n  variables:\n    v1:\n      type: bogus\n"
        )
        combos, domain_values, error = jobs_config_module._virtual_variant_tokens(
            workflow_collection(str(tmp_path / "workflows")), "bad_workflow", "workflow"
        )
        assert combos == []
        assert error is None

    def test_sync_preview_values_never_overwrites_title(self, jobs_config_module):
        """
        Regression test: sync_preview_values() must never recompute the
        "Preview (N combinations)" title from the checked-count. The title is a
        separate callback (update_preview_title) driven by the TOTAL number of
        available combinations stashed in arch-metadata ("n_combos", fixed once
        at render time in update_param_domains), not by how many are currently
        checked -- recomputing it from the checked count would silently corrupt
        the title as soon as a workflow (virtual-domain or not) has a partial
        selection with zero domain-config-checklist siblings -- exactly the
        case for a workflow using only virtual parameter domains.
        """
        # No domain-config-checklist components at all (as for a virtual-only
        # workflow): nothing to diff, the "unchanged" branch is taken.
        result_value = jobs_config_module.sync_preview_values(
            selected_per_domain=[],
            domain_ids=[],
            current_preview_values=["wf"],  # 1 checked out of e.g. 24 available
            arch_metadata={"arch_name": "wf"},
            prev_selections={},
        )
        assert result_value == ["wf"]

        # The title itself is computed independently from n_combos (the total),
        # not from how many are checked.
        title = jobs_config_module.update_preview_title(
            preview_value=["wf"],
            arch_metadata={"arch_name": "wf", "n_combos": 24},
        )
        # The heading is "Preview" plus a badge holding the count.
        assert "24" in "".join(str(part.children) for part in title)


class TestAnalysisToolsTile:
    """
    In analyze mode (?type=analyze), jobs_config must show a "Tools" tile (like
    "Synthesis Constraints" is shown only for custom_freq_synthesis) so the user
    can pick several eda tools to run the RTL analysis with, saved as the "tools"
    list of the analysis settings file (equivalent to 'odatix analyze --tool').
    """

    @pytest.fixture(autouse=True)
    def jobs_config_module(self):
        dash.Dash(__name__, use_pages=True, pages_folder="")
        jobs_config = import_jobs_config()

        return jobs_config

    @staticmethod
    def _find_by_id(node, target_id):
        if getattr(node, "id", None) == target_id:
            return node
        children = getattr(node, "children", None)
        if isinstance(children, (list, tuple)):
            for child in children:
                found = TestAnalysisToolsTile._find_by_id(child, target_id)
                if found is not None:
                    return found
        elif children is not None:
            return TestAnalysisToolsTile._find_by_id(children, target_id)
        return None

    @staticmethod
    def _tile_of(node, checklist_id):
        children = getattr(node, "children", None)
        if isinstance(children, (list, tuple)):
            for child in children:
                if TestAnalysisToolsTile._find_by_id(child, checklist_id) is not None:
                    if "odx-panel" in (getattr(child, "className", "") or ""):
                        return child
                    inner = TestAnalysisToolsTile._tile_of(child, checklist_id)
                    if inner is not None:
                        return inner
        return None

    def test_tile_hidden_when_not_analyze(self, jobs_config_module):
        form = jobs_config_module.job_settings_form({}, run_mode="fmax_synthesis")
        checklist = self._find_by_id(form, "analysis-tools")
        assert checklist is not None  # always present so its State is valid
        tile = self._tile_of(form, "analysis-tools")
        assert tile.style.get("display") == "none"

    def test_tile_visible_and_preselects_tools(self, jobs_config_module):
        form = jobs_config_module.job_settings_form(
            {}, run_mode="analyze", selected_tools=["vivado", "verilator"]
        )
        tile = self._tile_of(form, "analysis-tools")
        assert tile.style.get("display") == "block"
        checklist = self._find_by_id(form, "analysis-tools")
        assert checklist.value == ["vivado", "verilator"]
        values = [opt["value"] for opt in checklist.options]
        assert values == jobs_config_module.eda_tools.tools_supporting("analysis")

    def test_tools_default_from_settings(self, jobs_config_module):
        # With no explicit selected_tools, the tile pre-checks the "tools" list
        # of the settings dict.
        form = jobs_config_module.job_settings_form(
            {"tools": ["design_compiler"]}, run_mode="analyze"
        )
        checklist = self._find_by_id(form, "analysis-tools")
        assert checklist.value == ["design_compiler"]

    def test_unknown_tools_are_dropped(self, jobs_config_module):
        form = jobs_config_module.job_settings_form(
            {}, run_mode="analyze", selected_tools=["vivado", "not_a_tool"]
        )
        checklist = self._find_by_id(form, "analysis-tools")
        assert checklist.value == ["vivado"]


class TestAnalysisCheckSettingsMultiTool:
    """
    run_analysis.check_settings must accept several tools (like the CLI
    'odatix analyze --tool vivado verilator') and return a single flattened job
    set so all tools run in one monitor session, with prepare_synthesis staying
    tool-agnostic.
    """

    def _fake_context(self, tool, n_instances, shared_job_list):
        from odatix.lib.run_report import JobPlan

        built = []

        class _Handler:
            process_group = f"pg_{tool}"
            plan = JobPlan()
            cached_archs = []
            overwrite_archs = []
            incomplete_archs = []
            daemon_archs = []
            new_archs = [f"arch{i}" for i in range(n_instances)]
            error_archs = []

        instances = [f"{tool}_inst{i}" for i in range(n_instances)]

        def prepare_job(arch_instance):
            # Real prepare_job()s append a built ParallelJob to the shared
            # job_list threaded through prepare_analysis(); mirror that here
            # (ParallelJobHandler needs a real .display_name) so
            # prepare_synthesis()'s "did anything actually get built" check
            # behaves like it would against the real implementation.
            built.append(arch_instance)
            shared_job_list.append(SimpleNamespace(display_name=arch_instance))

        context = {
            "work_path": f"work/{tool}",
            "format_settings_file": f"{tool}_settings.yml",
            "process_group": _Handler.process_group,
            "arch_handler": _Handler(),
            "architecture_instances": instances,
            "prepare_job": prepare_job,
            "job_list": shared_job_list,
            "ask_continue": False,
            "exit_when_done": False,
            "log_size_limit": 300,
            "nb_jobs": 4,
            "valid_arch_count": n_instances,
        }
        return context, built

    def test_multi_tool_flattens_and_dispatches(self, monkeypatch):
        import odatix.components.run_analysis as run_analysis

        monkeypatch.setattr(run_analysis, "load_tool_context", lambda tool, target_path, flow=None: {
            "tool_test_command": "true", "install_path": None,
        })
        # tool checks run in background threads; neutralize them
        monkeypatch.setattr(run_analysis, "start_tool_check", lambda *a, **k: None)
        monkeypatch.setattr(run_analysis, "settle_tool_checks", lambda *a, **k: None)

        by_tool = {}
        built_by_tool = {}

        def fake_prepare_analysis(**kwargs):
            # check_settings() threads its own accumulating job_list into every
            # prepare_analysis() call (kwargs["job_list"]); real prepare_job()s
            # append into it, so the fake must do the same.
            tool = kwargs["tool"]
            n_instances = {"vivado": 2, "verilator": 3}[tool]
            context, built = self._fake_context(tool, n_instances, kwargs["job_list"])
            by_tool[tool] = context
            built_by_tool[tool] = built
            return context

        monkeypatch.setattr(run_analysis, "prepare_analysis", fake_prepare_analysis)

        result = run_analysis.check_settings(
            "analysis_settings.yml", "archs", ["vivado", "verilator"], "work",
            "targets", overwrite=False, noask=True, exit_when_done=False,
            log_size_limit=300, nb_jobs=4, check_eda_tool=True,
        )
        (
            architecture_instances, prepare_job, job_list, tool_settings_file,
            arch_handler, exit_when_done, log_size_limit, nb_jobs, _plan,
        ) = result

        assert len(architecture_instances) == 5  # 2 vivado + 3 verilator
        assert tool_settings_file == "vivado_settings.yml"  # first tool drives the session

        run_analysis.prepare_synthesis(
            architecture_instances=architecture_instances,
            prepare_job=prepare_job,
            job_list=job_list,
            tool_settings_file=tool_settings_file,
            arch_handler=arch_handler,
            exit_when_done=exit_when_done,
            log_size_limit=log_size_limit,
            nb_jobs=nb_jobs,
        )
        assert built_by_tool["vivado"] == ["vivado_inst0", "vivado_inst1"]
        assert built_by_tool["verilator"] == ["verilator_inst0", "verilator_inst1", "verilator_inst2"]


######################################
# Run popup: job-preparation progress bar
######################################

class TestPrepareProgressBar:
    """
    The run popup shows a progress bar of the job-preparation phase (copies
    into the work directory, parameter replacements), fed by the state
    published by run_common.PrepareProgress: the green section is the jobs
    prepared successfully, the red section the failed ones, with ok/failed
    counts.
    """

    @pytest.fixture(autouse=True)
    def jobs_config_module(self):
        dash.Dash(__name__, use_pages=True, pages_folder="")
        jobs_config = import_jobs_config()
        from odatix.components import run_common

        run_common.reset_prepare_progress()
        yield jobs_config
        run_common.reset_prepare_progress()

    def test_empty_without_progress_state(self, jobs_config_module):
        assert jobs_config_module._prepare_progress_bar() == ""

    def test_bar_shows_counts_and_colored_sections(self, jobs_config_module):
        import io
        from odatix.components import run_common

        progress = run_common.PrepareProgress(total=10, stream=io.StringIO())
        for _ in range(6):
            progress.update(ok=True)
        for _ in range(2):
            progress.update(ok=False)

        rendered = str(jobs_config_module._prepare_progress_bar())
        assert "8/10 jobs prepared" in rendered
        assert "✔ 6" in rendered
        assert "✘ 2" in rendered
        # green/red section widths are proportional to ok/failed counts
        assert "60.0%" in rendered
        assert "20.0%" in rendered

    def test_failed_count_hidden_when_no_failure(self, jobs_config_module):
        import io
        from odatix.components import run_common

        progress = run_common.PrepareProgress(total=2, stream=io.StringIO())
        progress.update(ok=True)

        rendered = str(jobs_config_module._prepare_progress_bar())
        assert "✔ 1" in rendered
        assert "✘" not in rendered


######################################
# Select targets page: target_card
######################################

class TestTargetCard:
    @pytest.fixture(autouse=True)
    def select_targets_module(self):
        # dash.register_page (called at page-module import) requires an app
        dash.Dash(__name__, use_pages=True, pages_folder="")
        import odatix.gui.pages.select_targets as select_targets

        return select_targets

    def is_extra_open(self, card):
        # target_card()'s children: [title, store, buttons-row, extra-div]
        extra_div = card.children[-1]
        return extra_div.style == {"display": "block"}

    def test_closed_by_default(self, select_targets_module):
        card = select_targets_module.target_card({"name": "t1", "enabled": True})
        assert not self.is_extra_open(card)

    def test_open_when_script_copy_enabled(self, select_targets_module):
        card = select_targets_module.target_card({"name": "t1", "enabled": True, "script_copy_enable": True})
        assert self.is_extra_open(card)

    def test_open_when_script_copy_source_set(self, select_targets_module):
        card = select_targets_module.target_card({
            "name": "t1", "enabled": True, "script_copy_enable": False, "script_copy_source": "/opt/pre.tcl",
        })
        assert self.is_extra_open(card)

    def test_closed_when_source_blank(self, select_targets_module):
        card = select_targets_module.target_card({
            "name": "t1", "enabled": True, "script_copy_enable": False, "script_copy_source": "   ",
        })
        assert not self.is_extra_open(card)


######################################
# Workflow editor: "Add new" buttons
######################################

class TestWorkflowEditorAddButtons:
    """
    Regression test: the "Add new variable"/"Add new task" buttons are built
    by wf_add_card(prefix), which gives the clickable element id f"{prefix}-new"
    (e.g. "wf-variable-new"). The callbacks that react to a click must listen
    on that exact id -- a swapped id ("wf-new-variable") silently never fires,
    since Dash simply never matches it to any real component.
    """

    @pytest.fixture(autouse=True)
    def workflow_editor_module(self):
        dash.Dash(__name__, use_pages=True, pages_folder="")
        import odatix.gui.pages.workflow_editor as workflow_editor

        return workflow_editor

    def test_add_card_button_id_matches_prefix(self, workflow_editor_module):
        card = workflow_editor_module.wf_add_card(prefix="wf-variable", text="Add new variable")
        clickable = card.children
        assert clickable.id == "wf-variable-new"

    def test_add_variable_callback_listens_on_the_real_button_id(self, workflow_editor_module, monkeypatch):
        from types import SimpleNamespace

        monkeypatch.setattr(workflow_editor_module, "ctx", SimpleNamespace(triggered_id="wf-variable-new"))
        result = workflow_editor_module.update_wf_variable_cards(
            new_click=1,
            duplicate_clicks=[],
            delete_clicks=[],
            cards=[],
            types=[], base_vals=[], from_vals=[], to_vals=[], from_2_pow_vals=[], to_2_pow_vals=[],
            from_type_vals=[], to_type_vals=[], step_vals=[], op_vals=[], list_vals=[], source_vals=[], sources_vals=[],
            group_vals=[],
        )
        ids = [getattr(card, "id", None) for card in result]
        assert {"type": "wf-variable-card", "name": "var1"} in ids

    def test_add_task_callback_listens_on_the_real_button_id(self, workflow_editor_module, monkeypatch):
        from types import SimpleNamespace

        task_card = workflow_editor_module.wf_add_card(prefix="wf-task", text="Add new task", mode="task")
        assert task_card.children.id == "wf-task-new"

        monkeypatch.setattr(workflow_editor_module, "ctx", SimpleNamespace(triggered_id="wf-task-new"))
        result = workflow_editor_module.update_wf_task_cards(1, [], [], [], [], [], [], [], [], [])
        ids = [getattr(card, "id", None) for card in result]
        assert any(isinstance(i, dict) and i.get("name") == "task1" for i in ids)


######################################
# Tool / flow / step selection page
######################################

class TestChooseEdaToolPage:
    """
    /choose_eda_tool lays out, inside each tool's card, everything that tool
    leaves to choose: its flows as buttons and, for a flow split into steps,
    its steps as "run up to here" buttons. Every one of them leads straight to
    the job settings, so a run is always one click away.
    """

    @pytest.fixture(autouse=True)
    def page(self, tmp_path, monkeypatch, install_dummy_tool):
        # dash.register_page (called at page-module import) requires an app
        dash.Dash(__name__, use_pages=True, pages_folder="")
        import odatix.gui.pages.choose_eda_tool as choose_eda_tool
        import odatix.lib.eda_tools as eda_tools
        from odatix.lib.settings import OdatixSettings

        # Keep the page on the built-in tools (plus the "dummy" test tool)
        # whatever the workspace holds, and on the "unix" flow declarations
        # whatever the platform.
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        install_dummy_tool(tools_dir)
        monkeypatch.setattr(OdatixSettings, "user_tools_path", str(tools_dir))
        monkeypatch.setattr(eda_tools, "platform_key", lambda: "unix")
        return choose_eda_tool

    def links(self, page, job_type, className=None):
        """Every href of the rendered page, optionally filtered by class."""
        found = []

        def walk(component):
            href = getattr(component, "href", None)
            if href and (className is None or className in (getattr(component, "className", "") or "")):
                found.append(href)
            children = getattr(component, "children", None)
            if isinstance(children, (list, tuple)):
                for child in children:
                    walk(child)
            elif children is not None:
                walk(children)

        for block in page.get_layout(job_type):
            walk(block)
        return found

    def test_every_link_of_the_page_starts_a_run(self, page):
        # No intermediate selection page and no "continue" step: the only way
        # out of a *card* is the job settings. The two ways out of the page
        # itself (back link, per-tool settings gear) are not card links.
        links = [
            link
            for link in self.links(page, "custom_freq_synthesis")
            if link != "/choose_job_type" and not link.startswith("/tool_editor?")
        ]
        assert links
        assert all(link.startswith("/run_jobs?") for link in links)

    def test_a_tool_with_nothing_to_choose_is_a_single_link(self, page, tmp_path):
        # A tool with a single one shot flow: its whole card is the link.
        tool_dir = tmp_path / "tools" / "oneshot"
        tool_dir.mkdir()
        (tool_dir / "tool.yml").write_text(
            "label: One shot\n"
            "default_flow: synthesis\n"
            "unix:\n"
            "  custom_freq_synthesis_command: [echo]\n"
            "flows:\n"
            "  synthesis:\n"
            "    label: Synthesis\n"
        )
        links = self.links(page, "custom_freq_synthesis", className="odx-tool-card")
        assert "/run_jobs?type=custom_freq_synthesis&tool=oneshot&flow=synthesis" in links

    def test_the_flows_of_a_tool_are_buttons_inside_its_card(self, page):
        # dummy's "quick" flow runs in one go: one button, no stopping point.
        links = self.links(page, "custom_freq_synthesis", className="odx-flow")
        assert "/run_jobs?type=custom_freq_synthesis&tool=dummy&flow=quick" in links

    def test_a_stepped_flow_offers_one_button_per_stopping_point(self, page):
        links = [
            link
            for link in self.links(page, "custom_freq_synthesis", className="odx-step")
            if "tool=vivado&flow=power_opt" in link
        ]
        # One button per stopping point, in flow order. Every one of them says
        # where it stops, the default included: not saying it would mean
        # "wherever the flow stops by default", which is what the flow button
        # itself is for.
        assert links == [
            "/run_jobs?type=custom_freq_synthesis&tool=vivado&flow=power_opt&until=elaboration",
            "/run_jobs?type=custom_freq_synthesis&tool=vivado&flow=power_opt&until=synthesis",
            "/run_jobs?type=custom_freq_synthesis&tool=vivado&flow=power_opt&until=pnr",
            "/run_jobs?type=custom_freq_synthesis&tool=vivado&flow=power_opt&until=bitstream",
        ]

    def test_every_flow_of_a_stepped_tool_offers_its_steps(self, page):
        # Being split into steps belongs to the tool, not to one dedicated
        # flow: both Vivado flows can be stopped wherever.
        links = self.links(page, "custom_freq_synthesis", className="odx-step")
        for flow in ("standard", "power_opt"):
            assert f"/run_jobs?type=custom_freq_synthesis&tool=vivado&flow={flow}&until=pnr" in links

    def test_an_fmax_search_can_be_stopped_at_a_step_too(self, page):
        links = self.links(page, "fmax_synthesis", className="odx-step")
        # Searching on post-synthesis timing only, leaving implementation out.
        assert "/run_jobs?type=fmax_synthesis&tool=vivado&flow=standard&until=synthesis" in links

    def test_a_one_shot_flow_has_no_step_button(self, page):
        links = self.links(page, "custom_freq_synthesis", className="odx-step")
        assert not [link for link in links if "flow=quick" in link]

    def test_a_flow_that_cannot_run_the_job_type_is_not_offered(self, page):
        # Verilator only lints: no flow of it shows up under fmax synthesis.
        links = self.links(page, "fmax_synthesis")
        assert not [link for link in links if "tool=verilator" in link]

    def test_no_tool_for_an_unknown_job_type(self, page):
        assert self.links(page, "nope") == ["/choose_job_type"]

class TestStepSelectionReachesTheRun:
    """
    The step picked on /choose_eda_tool travels to the runner as the "--until"
    of the command line: it decides where a run stops, and therefore where a
    later run resumes.
    """

    @pytest.fixture(autouse=True)
    def jobs_config_module(self):
        dash.Dash(__name__, use_pages=True, pages_folder="")
        jobs_config = import_jobs_config()

        jobs_config._prepare_log_buffer = jobs_config._ThreadSafeBuffer()
        jobs_config._prepare_status = {"status": "checking", "error": None}
        jobs_config._prepare_run = None
        return jobs_config

    def check(self, jobs_config_module, mode, **options):
        from odatix.workspace import Workspace

        jobs_config_module.start_check(mode, Workspace.open(), **options)

    def test_custom_freq_passes_the_last_step_to_the_runner(self, jobs_config_module, monkeypatch, in_tmp_dir):
        import odatix.components.run_custom_synthesis as run_custom_synthesis

        called = {}

        def fake_check_settings(**kwargs):
            called.update(
                tool=kwargs["tool"], flow=kwargs["flow"],
                until_step=kwargs["until_step"], rerun_from_step=kwargs["rerun_from_step"],
            )
            return (None,) * 9

        monkeypatch.setattr(run_custom_synthesis, "check_settings", fake_check_settings)
        self.check(
            jobs_config_module, "custom_freq_synthesis",
            tool="vivado", flow="staged", until="pnr", nb_jobs=4, log_size_limit=300,
        )
        assert called == {
            "tool": "vivado", "flow": "staged", "until_step": "pnr",
            # Re-running a completed step stays a command line only option.
            "rerun_from_step": None,
        }

    def test_fmax_passes_the_last_step_to_the_runner(self, jobs_config_module, monkeypatch, in_tmp_dir):
        import odatix.components.run_fmax_synthesis as run_fmax_synthesis

        called = {}

        def fake_check_settings(**kwargs):
            called.update(until_step=kwargs["until_step"], rerun_from_step=kwargs["rerun_from_step"])
            return (None,) * 9

        monkeypatch.setattr(run_fmax_synthesis, "check_settings", fake_check_settings)
        self.check(
            jobs_config_module, "fmax_synthesis",
            tool="vivado", flow="standard", until=None, nb_jobs=4, log_size_limit=300,
        )
        assert called == {"until_step": None, "rerun_from_step": None}


class TestMetricEditorLayers:
    """
    In tool mode, the metrics editor shows the metrics Odatix ships together
    with what the workspace metrics.yml says about them. Every card is editable;
    only what differs from the built-in definition is saved, as an override (see
    odatix.lib.metrics).
    """

    @pytest.fixture
    def metric_editor(self):
        # dash.register_page (called at page-module import) requires an app
        dash.Dash(__name__, use_pages=True, pages_folder="")
        import odatix.gui.pages.metric_editor as metric_editor

        return metric_editor

    @pytest.fixture
    def builtin_section(self):
        return {
            "Area": {
                "type": "regex",
                "settings": {"file": "report/area.rep", "pattern": "area ([0-9]+)", "group_id": 1},
            },
            "Power": {
                "type": "regex",
                "settings": {"file": "report/power.rep", "pattern": "power ([0-9]+)", "group_id": 1},
            },
        }

    def test_a_builtin_metric_the_workspace_ignores_stays_builtin(self, metric_editor):
        entries = metric_editor.section_entries({"Area": {"type": "regex"}}, {})
        assert entries == [("Area", {"type": "regex"}, metric_editor.ORIGIN_BUILTIN, True)]

    def test_an_overridden_metric_shows_the_workspace_definition(self, metric_editor):
        entries = metric_editor.section_entries(
            {"Area": {"type": "regex"}}, {"Area": {"type": "operation"}}
        )
        assert entries == [("Area", {"type": "operation"}, metric_editor.ORIGIN_WORKSPACE, True)]

    def test_an_empty_workspace_entry_is_a_removed_builtin_metric(self, metric_editor):
        entries = metric_editor.section_entries({"Area": {"type": "regex"}}, {"Area": None})
        # The built-in definition is still shown, so the reset button can bring
        # it back.
        assert entries == [("Area", {"type": "regex"}, metric_editor.ORIGIN_REMOVED, True)]

    def test_the_metrics_of_the_workspace_come_last(self, metric_editor):
        entries = metric_editor.section_entries(
            {"Area": {"type": "regex"}}, {"Mine": {"type": "operation"}}
        )
        assert [(name, origin, has_builtin) for name, _definition, origin, has_builtin in entries] == [
            ("Area", metric_editor.ORIGIN_BUILTIN, True),
            ("Mine", metric_editor.ORIGIN_WORKSPACE, False),
        ]

    def test_an_untouched_builtin_metric_is_not_a_workspace_metric(self, metric_editor, builtin_section):
        # The very definition the built-in file holds, read back from a card.
        definition = metric_editor.normalized_definition(builtin_section["Area"])
        assert metric_editor.card_origin("Area", definition, False, builtin_section) == (
            metric_editor.ORIGIN_BUILTIN
        )

    def test_changing_one_field_makes_it_an_override(self, metric_editor, builtin_section):
        definition = metric_editor.normalized_definition(builtin_section["Area"])
        definition["settings"]["pattern"] = "area ([0-9.]+)"
        assert metric_editor.card_origin("Area", definition, False, builtin_section) == (
            metric_editor.ORIGIN_WORKSPACE
        )

    def test_only_what_differs_from_the_builtin_metrics_is_saved(self, metric_editor, builtin_section):
        # Three cards: one left as Odatix defines it, one removed, one of its own.
        fields = (
            ["Area", "Power", "Mine"],                       # names
            ["regex", "regex", "operation"],                 # types
            ["report/area.rep", "report/power.rep", ""],     # file
            ["area ([0-9]+)", "power ([0-9]+)", ""],         # pattern
            ["1", "1", ""],                                  # group_id
            ["", "", ""],                                    # key
            ["", "", "2*2"],                                 # op
            ["", "", ""],                                    # unit
            ["", "", ""],                                    # format
            [[True], [True], [True]],                        # error_if_missing
            [[], [], []],                                    # multiple
            [
                metric_editor.ORIGIN_BUILTIN,
                metric_editor.ORIGIN_REMOVED,
                metric_editor.ORIGIN_WORKSPACE,
            ],
        )

        section = metric_editor.build_section_dict(*fields, builtin_section=builtin_section)

        # "Area" is exactly the built-in metric: nothing is written for it, so it
        # keeps following the built-in definition. "Power" is saved as an empty
        # entry, which is what excludes it from the export.
        assert list(section) == ["Power", "Mine"]
        assert section["Power"] is None
        assert section["Mine"] == {"type": "operation", "settings": {"op": "2*2"}}

    def test_an_edited_builtin_metric_is_saved_as_an_override(self, metric_editor, builtin_section):
        fields = (
            ["Area"],
            ["regex"],
            ["report/area.rep"],
            ["area ([0-9.]+)"],   # the pattern was edited
            ["1"],
            [""],
            [""],
            ["um2"],              # and a unit was added
            [""],
            [[True]],
            [[]],
            [metric_editor.ORIGIN_BUILTIN],
        )

        section = metric_editor.build_section_dict(*fields, builtin_section=builtin_section)

        assert section["Area"]["settings"]["pattern"] == "area ([0-9.]+)"
        assert section["Area"]["unit"] == "um2"

    def test_the_badge_follows_what_is_being_typed(self, metric_editor, builtin_section):
        # Two cards rendered from the built-in metrics; the second one is edited.
        names = ["Area", "Power"]
        fields = (
            names,
            ["regex", "regex"],
            ["report/area.rep", "report/power.rep"],
            ["area ([0-9]+)", "power ([0-9.]+)"],   # "Power" no longer matches
            ["1", "1"],
            ["", ""],
            ["", ""],
            ["", ""],
            ["", ""],
            [[True], [True]],
            [[], []],
        )
        definitions = metric_editor.section_definitions(*fields)

        origins = metric_editor.card_origins(
            names, definitions, [metric_editor.ORIGIN_BUILTIN] * 2, builtin_section
        )

        assert origins == [metric_editor.ORIGIN_BUILTIN, metric_editor.ORIGIN_WORKSPACE]
        # The badge only shows up for a metric there is a built-in one to
        # compare with, and says which of the two you are looking at.
        assert metric_editor.origin_note_style(origins[0], True).get("display") != "none"
        assert metric_editor.origin_note_style(origins[1], False) == {"display": "none"}

    def test_a_card_excluded_from_the_export_stays_removed(self, metric_editor, builtin_section):
        names = ["Area"]
        definitions = metric_editor.section_definitions(
            names, ["regex"], ["report/area.rep"], ["area ([0-9]+)"], ["1"],
            [""], [""], [""], [""], [[True]], [[]],
        )
        origins = metric_editor.card_origins(
            names, definitions, [metric_editor.ORIGIN_REMOVED], builtin_section
        )
        assert origins == [metric_editor.ORIGIN_REMOVED]


class TestSimulationRunMode:
    """
    /run_jobs?type=simulation is set up the other way around from every other
    job type: the instances are the simulations and what each of them selects is
    a set of architecture configurations, saved as the "simulations" mapping of
    the simulation settings file.
    """

    @pytest.fixture(autouse=True)
    def jobs_config_module(self, monkeypatch):
        dash.Dash(__name__, use_pages=True, pages_folder="")
        jobs_config = import_jobs_config()
        from types import SimpleNamespace

        monkeypatch.setattr(jobs_config, "ctx", SimpleNamespace(triggered_id="test-trigger"))
        return jobs_config

    @staticmethod
    def _settings():
        return {
            "arch_path": "odatix_userconfig/architectures",
            "sim_path": "odatix_userconfig/simulations",
            "simulation_settings_file": "odatix_userconfig/simulations_settings.yml",
        }

    def test_run_context_targets_the_simulations(self, jobs_config_module, example_workspace):
        context = jobs_config_module._run_context("?type=simulation", self._settings())
        assert context["mode"] == "simulation"
        assert context["selection_key"] == "simulations"
        assert "TB_Example_Counter_GHDL" in context["instances"]
        assert context["settings_link"]("TB_X") == "/sim_editor?sim=TB_X"
        assert context["config_link"]("TB_X") == "/metric_editor?simulation=TB_X"

    def test_page_load_lists_one_section_per_simulation(self, jobs_config_module, example_workspace):
        # Selection written here rather than taken from the examples, which
        # change what they enable over time.
        (example_workspace / "odatix_userconfig" / "simulations_settings.yml").write_text(
            "simulations:\n"
            "  - TB_Example_Counter_GHDL:\n"
            "    - Example_Counter_vhdl/04bits\n"
        )
        sections, heading, _title, baseline = jobs_config_module.update_param_domains(
            "?type=simulation", "/run_jobs", self._settings()
        )
        assert heading == "Simulations"
        assert len(sections) == len(jobs_config_module._run_context("?type=simulation", self._settings())["instances"])
        assert list(baseline["simulations"]) == ["TB_Example_Counter_GHDL"]
        assert "Example_Counter_vhdl/04bits" in baseline["simulations"]["TB_Example_Counter_GHDL"]

    def test_preview_is_the_union_of_the_architecture_panels(self, jobs_config_module):
        # A simulation runs each selected configuration once: the union of what
        # the enabled architecture sub-cards have checked, not a cross product.
        entries = jobs_config_module.sync_simulation_selection(
            [["A + d/1", "A + d/2"], ["B + d/1", "A + d/2"]],
            [[True], [True]],
            [
                {"type": "preview-config-checklist", "sim": "S", "arch": "A"},
                {"type": "preview-config-checklist", "sim": "S", "arch": "B"},
            ],
            [
                {"type": "sim-arch-switch", "sim": "S", "arch": "A"},
                {"type": "sim-arch-switch", "sim": "S", "arch": "B"},
            ],
            [], [], [],
        )
        assert entries == ["A+d/1", "A+d/2", "B+d/1"]

    def test_a_disabled_architecture_contributes_nothing(self, jobs_config_module):
        entries = jobs_config_module.sync_simulation_selection(
            [["A + d/1"], ["B + d/1"]],
            [[True], []],  # B switched off
            [
                {"type": "preview-config-checklist", "sim": "S", "arch": "A"},
                {"type": "preview-config-checklist", "sim": "S", "arch": "B"},
            ],
            [
                {"type": "sim-arch-switch", "sim": "S", "arch": "A"},
                {"type": "sim-arch-switch", "sim": "S", "arch": "B"},
            ],
            [], [], [],
        )
        assert entries == ["A+d/1"]

    def test_only_enabled_simulations_are_collected(self, jobs_config_module):
        selection = jobs_config_module._collect_simulation_selection(
            [[True], []],
            [
                {"type": "arch-title", "arch": "S1", "is_switch": True},
                {"type": "arch-title", "arch": "S2", "is_switch": True},
            ],
            [["A/1"], ["B/1"]],
            [{"type": "sim-selection", "sim": "S1"}, {"type": "sim-selection", "sim": "S2"}],
        )
        assert selection == {"S1": ["A/1"]}

    def test_selection_round_trips_through_the_settings_file(self, jobs_config_module, example_workspace):
        from odatix.gui.jobs_config.settings_io import write_run_settings
        from odatix.lib.run_settings import get_sim_settings
        from odatix.workspace.jobs import job_config

        settings = jobs_config_module._collect_run_settings(
            "simulation", "simulations",
            [[True]], [{"type": "arch-title", "arch": "TB_Demo", "is_switch": True}],
            [], [],
            [], [], "4", [], "300", [], [],
            [], [], "", [], "", "", "", "", "", [],
            sim_selection_values=[["Example_Counter_vhdl/04bits", "Example_Counter_vhdl/08bits"]],
            sim_selection_ids=[{"type": "sim-selection", "sim": "TB_Demo"}],
        )
        expected = {"TB_Demo": ["Example_Counter_vhdl/04bits", "Example_Counter_vhdl/08bits"]}
        assert settings["simulations"] == expected

        path = "odatix_userconfig/tmp_simulations_settings.yml"
        write_run_settings(path, settings, "simulation")
        assert job_config(path, "simulation").settings.simulations == expected
        # And "odatix sim" must accept what the GUI writes.
        assert get_sim_settings(path)[-1] == [expected]

    @staticmethod
    def _make_huge_architecture(name="Huge_Arch", domains=11, values=8, main_configs=3):
        """
        An architecture whose parameter domains multiply into far more
        combinations than can be listed (domains ** values), as a workspace
        where configurations have been generated ends up looking.
        """
        import os

        root = os.path.join("odatix_userconfig/architectures", name)
        os.makedirs(root, exist_ok=True)
        with open(os.path.join(root, "_settings.yml"), "w") as f:
            f.write("use_parameters: Yes\nparam_target_file: rtl/top.v\n")
        for index in range(main_configs):
            with open(os.path.join(root, "cfg%d.txt" % index), "w") as f:
                f.write("parameter = %d\n" % index)
        for domain in range(domains):
            domain_dir = os.path.join(root, "domain%d" % domain)
            os.makedirs(domain_dir, exist_ok=True)
            with open(os.path.join(domain_dir, "_settings.yml"), "w") as f:
                f.write("use_parameters: Yes\nparam_target_file: rtl/top.v\n")
            for value in range(values):
                with open(os.path.join(domain_dir, "v%d.txt" % value), "w") as f:
                    f.write("value = %d\n" % value)
        return name

    @staticmethod
    def _domains_configs(arch_path, arch_name):
        jobs_config = import_jobs_config()

        return jobs_config._arch_domains_configs(architecture_collection(arch_path), arch_name)

    def test_an_architecture_with_too_many_combinations_is_not_enumerated(
        self, jobs_config_module, example_workspace
    ):
        # Parameter domains multiply: 11 domains of 8 values is 8**11 = 8.6e9
        # combinations. Enumerating them would hang the page and exhaust
        # memory, so past MAX_PREVIEW_COMBINATIONS none is generated.
        from odatix.workspace.configs import count_combinations

        name = self._make_huge_architecture()
        domains_configs = self._domains_configs("odatix_userconfig/architectures", name)
        n_combos = count_combinations(domains_configs)
        assert n_combos > jobs_config_module.MAX_PREVIEW_COMBINATIONS

    def test_a_small_architecture_is_fully_enumerated(self, jobs_config_module, example_workspace):
        from odatix.workspace.configs import combinations, count_combinations

        domains_configs = self._domains_configs(
            "odatix_userconfig/architectures", "Example_Counter_vhdl"
        )
        n_combos = count_combinations(domains_configs)
        assert n_combos <= jobs_config_module.MAX_PREVIEW_COMBINATIONS
        combos = combinations(domains_configs, "Example_Counter_vhdl")
        assert ["Example_Counter_vhdl/04bits"] in combos

    def test_page_load_stays_cheap_with_a_huge_architecture(self, jobs_config_module, example_workspace):
        # Regression: the page used to enumerate every parameter-domain
        # combination of every architecture, once per simulation.
        import time

        self._make_huge_architecture()
        start = time.perf_counter()
        sections, _heading, _title, _baseline = jobs_config_module.update_param_domains(
            "?type=simulation", "/run_jobs", self._settings()
        )
        assert time.perf_counter() - start < 10
        assert sections

    def test_an_unlisted_saved_entry_is_kept(self, jobs_config_module, example_workspace):
        # A wildcard over an architecture too large to enumerate matches nothing
        # that is listed: it must survive the round-trip instead of being
        # silently dropped on the next save.
        self._make_huge_architecture()
        with open("odatix_userconfig/simulations_settings.yml", "w") as f:
            f.write(
                "overwrite: No\nask_continue: No\nexit_when_done: No\n"
                "log_size_limit: 300\nnb_jobs: 8\n"
                "simulations:\n"
                "  - TB_Example_Counter_GHDL:\n"
                "    - Huge_Arch + domain0/*\n"
            )
        _sections, _heading, _title, baseline = jobs_config_module.update_param_domains(
            "?type=simulation", "/run_jobs", self._settings()
        )
        # Entries are re-normalized to the settings-file syntax ("A+d/v", the
        # parser strips around "+"), but none must go missing.
        assert "Huge_Arch+domain0/*" in baseline["simulations"]["TB_Example_Counter_GHDL"]

    def test_a_wildcard_entry_is_expanded_on_load(self, jobs_config_module, example_workspace):
        with open("odatix_userconfig/simulations_settings.yml", "w") as f:
            f.write(
                "overwrite: No\nask_continue: No\nexit_when_done: No\n"
                "log_size_limit: 300\nnb_jobs: 8\n"
                "simulations:\n"
                "  - TB_Example_Counter_GHDL:\n"
                "    - Example_Counter_vhdl/*\n"
            )
        _sections, _heading, _title, baseline = jobs_config_module.update_param_domains(
            "?type=simulation", "/run_jobs", self._settings()
        )
        selected = baseline["simulations"]["TB_Example_Counter_GHDL"]
        assert len(selected) > 1
        assert all(entry.startswith("Example_Counter_vhdl/") for entry in selected)


class TestSimulationEditor:
    @pytest.fixture(autouse=True)
    def sim_editor_module(self):
        dash.Dash(__name__, use_pages=True, pages_folder="")
        import odatix.gui.pages.sim_editor as sim_editor

        return sim_editor

    def test_a_simulation_without_task_normalizes_to_an_empty_list(self, sim_editor_module):
        settings = sim_editor_module.normalize_simulation_settings({"use_parameters": True})
        assert settings["tasks"] == []
        assert settings["override_parameters"] is False

    def test_tasks_are_rebuilt_from_the_card_fields(self, sim_editor_module):
        tasks = sim_editor_module.build_tasks_list(
            ["compile", "main"],
            ["", "compile"],
            ["echo a\necho b", "echo run"],
            ["", ""],
            ["", "sub/dir"],
            ["", "linux, win32"],
        )
        assert tasks[0] == {"name": "compile", "commands": ["echo a", "echo b"]}
        assert tasks[1]["dependencies"] == ["compile"]
        assert tasks[1]["path"] == "sub/dir"
        assert tasks[1]["platforms"] == ["linux", "win32"]

    def test_no_task_stays_no_task(self, sim_editor_module):
        # Unlike a workflow, a simulation may define no task at all: it then
        # runs "make sim". Nothing must be invented on its behalf.
        assert sim_editor_module.build_tasks_list([], [], [], [], [], []) == []

    def test_settings_round_trip(self, sim_editor_module, example_workspace):
        from odatix.workspace.simulations import SimulationCollection

        simulations = SimulationCollection(None, "odatix_userconfig/simulations")
        simulation = simulations["TB_Example_Counter_GHDL"]
        settings = sim_editor_module.normalize_simulation_settings(simulation.settings.to_dict())
        assert settings["use_parameters"] is True
        assert settings["param_target_file"] == "tb/tb_counter.vhdl"

        settings["tasks"] = [{"name": "main", "commands": ["echo hello"]}]
        # The page writes the architectures back the way the file holds them.
        simulation.update(dict(
            settings,
            architectures=sim_editor_module.architectures_to_yaml(settings["architectures"]),
        ))
        reloaded = sim_editor_module.normalize_simulation_settings(
            simulations["TB_Example_Counter_GHDL"].reload().settings.to_dict()
        )
        assert reloaded == settings

    def test_a_card_carries_what_a_simulation_substitutes_untouched(self, sim_editor_module):
        # The parameter domains are edited in the configuration editor: the card
        # only lists the architecture, and must write back what it does not show.
        architectures = sim_editor_module.normalize_architectures([
            {"Example_Cordic_sv": {
                "param_domains": {"width": {"param_dir": "tb_params"}},
                "metrics_file": "_metrics_sv.yml",
            }},
            "Example_Cordic_vhdl",
        ])
        cards = sim_editor_module.arch_cards_from_settings(architectures)
        assert cards[0]["extra"] == {"param_domains": {"width": {"param_dir": "tb_params"}}}
        assert sim_editor_module.architectures_to_yaml(
            sim_editor_module.arch_cards_to_settings(cards)
        ) == [
            {"Example_Cordic_sv": {
                "metrics_file": "_metrics_sv.yml",
                "param_domains": {"width": {"param_dir": "tb_params"}},
            }},
            # Listed, nothing overridden, and still listed after an edit.
            "Example_Cordic_vhdl",
        ]

    def test_a_card_says_how_many_domains_it_overrides(self, sim_editor_module):
        cards = sim_editor_module.arch_cards_from_settings(
            sim_editor_module.normalize_architectures([
                {"Example_Cordic_sv": {"param_domains": {"width": {}, "iterations": {}}}},
                "Example_Cordic_vhdl",
            ])
        )
        badges = []

        def walk(component):
            children = getattr(component, "children", None)
            if isinstance(children, str):
                badges.append(children)
            elif isinstance(children, (list, tuple)):
                for child in children:
                    walk(child)
            elif children is not None:
                walk(children)

        for card in cards:
            walk(sim_editor_module.arch_card("a000", card))
        assert "2 domains" in badges
        assert "no override" in badges


class TestSimulationMetricEditor:
    @pytest.fixture(autouse=True)
    def metric_editor_module(self):
        dash.Dash(__name__, use_pages=True, pages_folder="")
        import odatix.gui.pages.metric_editor as metric_editor

        return metric_editor

    def test_simulation_mode_loads_the_simulation_metrics(self, metric_editor_module, example_workspace):
        settings = {"sim_path": "odatix_userconfig/simulations"}
        out = metric_editor_module.init_page(
            "?simulation=TB_Example_Counter_GHDL", "/metric_editor", settings
        )
        initial = out[8]
        assert initial["mode"] == "simulation"
        assert "reset" in initial["sections"]["metric"]

    def test_simulation_mode_points_back_to_the_simulation_editor(self, metric_editor_module):
        title = metric_editor_module.metric_title("TB_X", is_tool=False, mode="simulation")
        assert "/sim_editor?sim=TB_X" in str(title)

    def test_metrics_round_trip(self, metric_editor_module, example_workspace):
        from odatix.workspace.simulations import SimulationCollection

        simulations = SimulationCollection(None, "odatix_userconfig/simulations")
        metrics = {"cycles": {"type": "csv", "settings": {"file": "results.csv", "key": "cycles"}}}
        metadata = {"run": {"type": "csv", "settings": {"file": "results.csv", "key": "run"}}}
        metrics_file = simulations["TB_Example_Counter_GHDL"].metrics
        metrics_file.metrics = metrics
        metrics_file.metadata = metadata
        metrics_file.save()

        reloaded = simulations["TB_Example_Counter_GHDL"].metrics
        assert reloaded.metrics == metrics
        assert reloaded.metadata == metadata


######################################
# Architecture editor: overrides section
######################################

class TestArchitectureEditorOverrides:
    """
    The "overrides" section of an architecture, as the editor shows it: one card
    per rule, its selectors comma-separated, and a constraint declaration
    written one file per line.
    """

    @pytest.fixture(autouse=True)
    def architecture_editor_module(self):
        # dash.register_page (called at page-module import) requires an app
        dash.Dash(__name__, use_pages=True, pages_folder="")
        import odatix.gui.pages.architecture_editor as architecture_editor

        return architecture_editor

    @staticmethod
    def build(module, tools=None, targets=None, configurations=None, fmax_lower=None,
              fmax_upper=None, custom_freq="", constraints="", rest=None):
        """One card's worth of form values, as build_overrides takes them."""
        return module.build_overrides(
            {"tools": [tools], "targets": [targets], "configurations": [configurations]},
            [fmax_lower], [fmax_upper], [custom_freq], [constraints], [rest],
        )

    def test_a_constraint_declaration_survives_the_form(self, architecture_editor_module):
        # Every shape a settings file accepts comes back as one line per file,
        # and goes back to a declaration the run can read.
        text = architecture_editor_module.constraints_to_text([
            "pinout.xdc",
            {"file": "floorplan.tcl", "scope": "pnr"},
            {"files": ["a.sdc", "b.sdc"], "scope": "synthesis"},
        ])
        assert text.splitlines() == [
            "pinout.xdc", "floorplan.tcl @ pnr", "a.sdc @ synthesis", "b.sdc @ synthesis",
        ]
        assert architecture_editor_module.constraints_from_text(text) == [
            "pinout.xdc",
            {"file": "floorplan.tcl", "scope": "pnr"},
            {"file": "a.sdc", "scope": "synthesis"},
            {"file": "b.sdc", "scope": "synthesis"},
        ]

    def test_an_at_sign_that_is_not_a_stage_is_part_of_the_path(self, architecture_editor_module):
        assert architecture_editor_module.constraints_from_text("io@v2.xdc") == ["io@v2.xdc"]

    def test_a_card_is_built_for_every_rule(self, architecture_editor_module):
        cards = architecture_editor_module.override_cards([
            {"targets": "xc7a100t-csg324-1", "fmax_synthesis": {"lower_bound": 250}},
            {"tools": ["vivado", "genus@power_opt"], "constraints": ["floorplan.tcl"]},
        ])
        # One card per rule, in file order, plus the "add override" card.
        assert [card.id.get("index") for card in cards[:-1]] == [0, 1]
        assert cards[-1].id == "arch-add-override-card"

    def test_a_selector_is_a_name_a_list_or_nothing(self, architecture_editor_module):
        rules = self.build(architecture_editor_module, tools="vivado", targets=" xc7a*, xc7k* ",
                           configurations="  ", fmax_lower=300)
        assert rules == [{
            "tools": "vivado",
            "targets": ["xc7a*", "xc7k*"],
            "fmax_synthesis": {"lower_bound": 300},
        }]

    def test_editing_a_rule_keeps_what_the_card_does_not_show(self, architecture_editor_module):
        # A key the form has no field for must not be dropped by a save.
        rest = {"file_copy_enable": True, "file_copy_source": "extra.v"}
        rules = self.build(
            architecture_editor_module, targets="xc7a100t-csg324-1",
            fmax_lower=300, fmax_upper=900, custom_freq="50, 100",
            constraints="pinout.xdc @ pnr", rest=rest,
        )
        assert rules == [{
            "file_copy_enable": True,
            "file_copy_source": "extra.v",
            "targets": "xc7a100t-csg324-1",
            "fmax_synthesis": {"lower_bound": 300, "upper_bound": 900},
            "custom_freq_synthesis": {"list": [50, 100]},
            "constraints": [{"file": "pinout.xdc", "scope": "pnr"}],
        }]

    def test_a_rule_emptied_of_everything_keeps_no_empty_block(self, architecture_editor_module):
        rules = self.build(
            architecture_editor_module, targets="fpga1", fmax_lower=None, fmax_upper="",
            rest={"fmax_synthesis": {"lower_bound": 250}, "constraints": ["old.xdc"]},
        )
        assert rules == [{"targets": "fpga1"}]

    def test_a_rule_saying_nothing_at_all_is_not_written(self, architecture_editor_module):
        # An override with neither selector nor setting is the architecture
        # repeating itself: it is dropped rather than written.
        assert self.build(architecture_editor_module) == []

    def test_a_section_read_from_file_compares_equal_to_the_form(self, architecture_editor_module):
        # What normalize_form_settings stores at page load must be what the
        # cards rebuild, or the save button reports unsaved changes on load.
        section = [{
            "targets": ["xc7a100t-csg324-1"],
            "fmax_synthesis": {"lower_bound": 250, "upper_bound": 900},
            "custom_freq_synthesis": {"list": [50, 100]},
            "constraints": [{"files": ["a.xdc", "b.xdc"], "scope": "pnr"}],
        }]
        stored = architecture_editor_module.normalize_form_settings({"overrides": section})["overrides"]
        card = architecture_editor_module.override_cards(stored)[0]
        body = card.children[-1].children
        rebuilt = self.build(
            architecture_editor_module,
            targets="xc7a100t-csg324-1", fmax_lower=250, fmax_upper=900,
            custom_freq="50, 100", constraints=body[-2].children[-1].value,
            rest=body[-1].data,
        )
        assert rebuilt == stored


######################################
# Configuration editor: rules and origins
######################################

class TestConfigurationRules:
    """
    The configuration editor is where a parameter domain is described, whether
    it holds files written by hand or rules that produce configurations. The
    rules used to be a page of their own, generating files as its only effect;
    they are now a panel inside the domain they belong to, and the cards below
    it show what the domain resolves to -- generated configurations included,
    with nothing written to disk.
    """

    @pytest.fixture(autouse=True)
    def pages(self):
        dash.Dash(__name__, use_pages=True, pages_folder="")
        import odatix.gui.config_rules as config_rules
        import odatix.gui.pages.config_editor as config_editor
        import odatix.gui.pages.config_generator as config_generator

        return SimpleNamespace(rules=config_rules, editor=config_editor, generator=config_generator)

    RULES = {
        "configurations": {"name": "${width}bits", "template": "  parameter BITS = ${width}"},
        "variables": {"width": {"type": "list", "settings": {"list": [8, 16, 32]}}},
    }

    def domain(self, tmp_path, settings=None, files=None):
        """A parameter domain on disk, with rules and/or configuration files."""
        import yaml

        from odatix.workspace.architectures import ArchitectureCollection

        root = tmp_path / "architectures"
        path = root / "arch"
        path.mkdir(parents=True, exist_ok=True)
        (path / "_settings.yml").write_text(yaml.safe_dump(settings or {}))
        for name, content in (files or {}).items():
            (path / name).write_text(content)
        return ArchitectureCollection(None, str(root))["arch"].main_domain

    ######################################
    # Reading a domain
    ######################################

    def test_a_described_configuration_gets_a_card_without_any_file(self, pages, tmp_path):
        domain = self.domain(tmp_path, self.RULES)
        cards = pages.editor.build_config_cards(domain, "main", "normal")

        # The three configurations of the rules, plus the "show more" and "add" cards
        assert len(cards) == 5
        assert not list((tmp_path / "architectures" / "arch").glob("*.txt"))

    def test_main_domain_resolves_explicit_default_rules(self, pages, tmp_path):
        domain = self.domain(tmp_path, {
            "configurations": {"enabled": True},
            "variables": {"width": {"type": "list", "settings": {"list": [8, 16]}}},
        })

        assert [(config.name, config.content) for config in domain.resolve_configurations()] == [
            ("8", "8"),
            ("16", "16"),
        ]

    def test_a_card_says_where_its_configuration_comes_from(self, pages, tmp_path):
        domain = self.domain(
            tmp_path, self.RULES,
            files={"16bits.txt": "  parameter BITS = 16 // corrected", "extra.txt": "  parameter BITS = 7"},
        )
        cards = pages.editor.build_config_cards(domain, "main", "normal")
        origins = {}
        for card in cards[:-2]:
            store = [child for child in card.children if getattr(child, "data", None)][0]
            origins[store.data["config_name"]] = store.data["origin"]

        assert origins == {
            "8bits.txt": "generated",
            "16bits.txt": "edited",
            "32bits.txt": "generated",
            "extra.txt": "manual",
        }

    def test_a_generated_configuration_cannot_be_renamed_in_place(self, pages, tmp_path):
        # Its name is the name template: renaming the file would only leave the
        # rule's own name to reappear next to the copy.
        domain = self.domain(tmp_path, self.RULES)
        card = pages.editor.build_config_cards(domain, "main", "normal")[0]
        title = card.children[0].children[0]
        assert title.readOnly is True

    def test_a_hand_written_configuration_can_still_be_renamed(self, pages, tmp_path):
        domain = self.domain(tmp_path, files={"only.txt": "parameter BITS = 8"})
        card = pages.editor.build_config_cards(domain, "main", "normal")[0]
        title = card.children[0].children[0]
        assert title.readOnly is False

    ######################################
    # The rules panel
    ######################################

    def test_the_rules_panel_opens_filled_in(self, pages):
        (blocks, variables) = pages.rules.rule_set_fields(self.RULES)
        [(_key, name, template, _constraints)] = blocks
        assert name == "${width}bits"
        assert template == "  parameter BITS = ${width}"
        assert list(variables) == ["width"]

    def test_the_rules_panel_reads_the_settings_odatix_used_to_write(self, pages):
        from conftest import make_generation_settings

        (blocks, variables) = pages.rules.rule_set_fields(make_generation_settings())
        [(_key, name, template, _constraints)] = blocks
        assert name == "w$WIDTH"
        assert template == "parameter WIDTH = $WIDTH"
        assert list(variables) == ["WIDTH"]

    def test_saving_the_rules_writes_the_current_form_of_the_settings(self, pages):
        settings = pages.rules.rules_settings("${w}bits", "parameter W = ${w}", {"w": {"type": "bool"}})
        assert settings == {
            "configurations": {"name": "${w}bits", "template": "parameter W = ${w}"},
            "variables": {"w": {"type": "bool"}},
        }

    def test_rule_settings_keep_the_configuration_blacklist(self, pages):
        saved = pages.rules.rules_settings(
            "${w}", "W = ${w}", {"w": {"type": "list", "settings": {"list": [8, 16]}}},
            blacklist=["16"],
        )

        current = pages.rules.form_rules_settings(
            [(0, "${w}", "W = ${w}", [])],
            {"w": {"type": "list", "settings": {"list": [8, 16]}}},
            hard_settings.main_parameter_domain, saved,
        )
        space = pages.rules.rules_space(current)

        assert current == saved
        assert [point.name for point in space.points()] == ["8"]

    def test_generated_configuration_can_be_blacklisted_and_restored(self, pages, monkeypatch, tmp_path):
        import yaml

        from odatix.workspace.architectures import ArchitectureCollection

        root = tmp_path / "architectures"
        path = root / "arch"
        path.mkdir(parents=True)
        (path / "_settings.yml").write_text(yaml.safe_dump(self.RULES))
        instances = ArchitectureCollection(None, str(root))
        monkeypatch.setattr(
            pages.editor, "get_instance_collection_context",
            lambda search, settings: ("arch", "arch", instances),
        )

        domain_metadata = [{"domain_uuid": "main-uuid", "domain_name": hard_settings.main_parameter_domain}]
        generated_metadata = [{
            "domain_uuid": "main-uuid",
            "config_uuid": "16-uuid",
            "config_name": "16bits.txt",
            "origin": "generated",
        }]
        saved = pages.rules.rules_settings(
            self.RULES["configurations"]["name"], self.RULES["configurations"]["template"], self.RULES["variables"],
        )
        import odatix.gui.page_scope as page_scope

        fake = SimpleNamespace(
            triggered_id={"type": "delete-config", "domain_uuid": "main-uuid", "config_uuid": "16-uuid"},
            inputs_list=[[{"id": {"type": "delete-config", "domain_uuid": "main-uuid",
                                  "config_uuid": "16-uuid"}}]],
            states_list=[],
        )
        monkeypatch.setattr(pages.editor, "ctx", fake)
        monkeypatch.setattr(page_scope, "ctx", fake)

        stores, counters, _rows = pages.editor.toggle_generated_configuration_blacklist(
            [1], generated_metadata, domain_metadata, [saved], [0], "normal", "?arch=arch", {},
        )
        domain = instances["arch"].main_domain
        assert stores[0]["configurations"]["blacklist"] == ["16bits"]
        assert counters == [1]
        assert "16bits" not in domain.configuration_names()
        assert [config.name for config in domain.blacklisted_configurations()] == ["16bits"]

        blacklisted_card = next(
            card for card in pages.editor.build_config_cards(domain, "main-uuid", "normal")
            if card.id.get("type") == "config-card"
            and next(child.data for child in card.children if hasattr(child, "data"))["config_name"] == "16bits.txt"
        )
        restore_button = blacklisted_card.children[3].children[1].children[2]
        restore_icon = restore_button.children.children[0]
        assert "odx-config-blacklisted" in blacklisted_card.className
        assert restore_icon.id["type"] == "restore-config-icon"

        blacklisted_metadata = [{**generated_metadata[0], "origin": "blacklisted"}]
        stores, counters, _rows = pages.editor.toggle_generated_configuration_blacklist(
            [2], blacklisted_metadata, domain_metadata, stores, counters, "normal", "?arch=arch", {},
        )
        written = yaml.safe_load((path / "_settings.yml").read_text())
        assert "blacklist" not in stores[0]["configurations"]
        assert "blacklist" not in written["configurations"]
        domain.reload()
        assert "16bits" in domain.configuration_names()

    def test_saving_blank_main_rules_records_the_default_choice(self, pages, monkeypatch, tmp_path):
        import yaml

        from odatix.workspace.architectures import ArchitectureCollection

        root = tmp_path / "architectures"
        path = root / "arch"
        path.mkdir(parents=True)
        (path / "_settings.yml").write_text(yaml.safe_dump({}))
        instances = ArchitectureCollection(None, str(root))
        monkeypatch.setattr(
            pages.rules, "get_instance_collection_context",
            lambda search, settings: ("arch", "arch", instances),
        )

        variables = {"main-uuid": ["width"]}
        monkeypatch.setattr(
            pages.rules, "ctx",
            self.fake_ctx(pages, variables, triggered_id={"type": "cfg-save-rules", "domain_uuid": "main-uuid"}),
        )
        fields = self.field_values(variables, {("main-uuid", "width"): {"type": "list", "list": "8, 16"}})
        saved = pages.rules.rules_settings(
            "", "", {"width": {"type": "list", "settings": {"list": [8, 16]}}},
        )

        stores, bumps = pages.rules.save_rules(
            [1], None, None, [""], [""], [""], [""], *fields,
            [{"domain_uuid": "main-uuid", "domain_name": hard_settings.main_parameter_domain}],
            [saved], [0], "?arch=arch", {},
        )

        written = yaml.safe_load((path / "_settings.yml").read_text())
        assert written["configurations"]["enabled"] is True
        assert stores[0]["configurations"]["enabled"] is True
        assert bumps == [1]

    def test_a_domain_with_no_rules_says_so(self, pages):
        assert pages.rules.describes_configurations({}) is False
        assert pages.rules.describes_configurations(self.RULES) is True

    def test_the_panel_of_each_domain_has_its_own_components(self, pages):
        # Two domains on one page must not share the ids of a variable of the
        # same name, or editing one would edit the other.
        first = pages.rules.rules_section("domain-a", self.RULES)
        second = pages.rules.rules_section("domain-b", self.RULES)

        def variable_ids(section):
            row = section.children[2]
            return [card.id for card in row.children if isinstance(getattr(card, "id", None), dict)]

        assert {"type": "cfg-variable-card", "name": "width", "domain_uuid": "domain-a"} in variable_ids(first)
        assert {"type": "cfg-variable-card", "name": "width", "domain_uuid": "domain-b"} in variable_ids(second)

    def test_every_component_of_a_variable_card_carries_its_domain(self, pages):
        # A pattern-matching callback of the panel outputs one value per
        # component of a pattern: a field whose id forgot the domain matches
        # nothing, and the callback dies on the mismatch.
        import odatix.gui.variable_editor as ve

        card = ve.variable_card_from_config(
            "cfg-", "width", {"type": "range", "settings": {"from": 1, "to": 4}},
            scope={"domain_uuid": "domain-a"},
        )

        def identifiers(component):
            found = []
            component_id = getattr(component, "id", None)
            if isinstance(component_id, dict):
                found.append(component_id)
            children = getattr(component, "children", None)
            for child in children if isinstance(children, list) else [children]:
                if hasattr(child, "children") or hasattr(child, "id"):
                    found += identifiers(child)
            return found

        forgotten = [i for i in identifiers(card) if i.get("domain_uuid") != "domain-a"]
        assert forgotten == []

    def test_the_panel_of_an_untouched_domain_has_nothing_to_save(self, pages):
        # A settings file and a form do not spell the same thing identically (a
        # list of numbers comes back as text, a range without step comes back
        # with one): opening a panel must not report unsaved changes.
        import odatix.gui.variable_editor as ve

        for settings in (
            self.RULES,
            {"configurations": {"name": "w${n}", "template": "$n"},
             "variables": {"n": {"type": "range", "settings": {"from": 1, "to": 4}}}},
            {"configurations": {"name": "w${p}", "template": "$p"},
             "variables": {"p": {"type": "format", "settings": {"source": "$n", "format": "%02d"}}}},
        ):
            blocks, variables = pages.rules.rule_set_fields(settings)
            [(_key, name, template, _constraints)] = blocks
            saved = pages.rules.rules_settings(name, template, variables)
            # What the cards of that panel hand back, untouched.
            assert saved == pages.rules.rules_settings(name, template, ve.normalized_variables(variables))

    def test_a_format_variable_keeps_its_format(self, pages):
        # The format string of a "format" variable lives in its settings, where
        # the generator reads it; any other variable carries one next to them.
        import odatix.gui.variable_editor as ve

        variables = {
            "padded": {"type": "format", "settings": {"source": "$bits", "format": "%02d"}},
            "bits": {"type": "list", "settings": {"list": [4, 8]}, "format": "%03d"},
        }
        assert ve.normalized_variables(variables) == variables

    def test_a_domain_of_a_single_variable_needs_neither_template(self, pages, monkeypatch):
        # Writing "${width}" twice for a domain sweeping "width" says nothing
        # the variable does not: the fields stay empty and suggest it instead.
        settings = {"variables": {"width": {"type": "list", "settings": {"list": [8, 16]}}}}
        [(_key, name, template, _constraints)], _variables = pages.rules.rule_set_fields(settings)
        assert (name, template) == ("", "")
        assert pages.rules.describes_configurations(settings)

        variables = {"domain-a": ["width"]}
        monkeypatch.setattr(pages.rules, "ctx", self.fake_ctx(pages, variables))
        fields = self.field_values(variables, {("domain-a", "width"): {"type": "list", "list": "8, 16"}})
        # A named domain: the main one shares its file with the architecture,
        # whose variables may feed its commands instead.
        _previews, summaries, config_previews, name_hints, template_hints = pages.rules.update_rules_preview(
            [""], [""], [""], [None], "normal", *fields, [[]], [],
            [{"domain_uuid": "domain-a", "domain_name": "width"}],
        )
        assert summaries[0][0].children == "2 configurations"
        assert name_hints == template_hints == ["${width}"]
        titles = [child.children[0].children for child in config_previews[0][1].children]
        assert titles == ["8", "16"]

        # The main domain previews the same defaults before they are saved.
        _previews, summaries, config_previews, _n, _t = pages.rules.update_rules_preview(
            [""], [""], [""], [None], "normal", *fields, [[]], [],
            [{"domain_uuid": "domain-a", "domain_name": hard_settings.main_parameter_domain}],
        )
        assert summaries[0][0].children == "2 configurations"
        titles = [child.children[0].children for child in config_previews[0][1].children]
        assert titles == ["8", "16"]

    @pytest.mark.parametrize(
        "name, template, expected_name, expected_content",
        [
            ("", "", "8", "8"),
            ("w${width}", "", "w8", "8"),
            ("", "value = ${width}", "8", "value = 8"),
            ("w${width}", "value = ${width}", "w8", "value = 8"),
        ],
        ids=["defaults", "name-only", "template-only", "both"],
    )
    def test_main_preview_fills_missing_templates(
        self, pages, monkeypatch, name, template, expected_name, expected_content,
    ):
        variables = {"domain-a": ["width"]}
        monkeypatch.setattr(pages.rules, "ctx", self.fake_ctx(pages, variables))
        fields = self.field_values(variables, {("domain-a", "width"): {"type": "list", "list": "8"}})

        config_preview = pages.rules.update_rules_preview(
            [name], [template], [""], [None], "normal", *fields, [[]], [],
            [{"domain_uuid": "domain-a", "domain_name": hard_settings.main_parameter_domain}],
        )[2][0]
        card = config_preview[1].children[0]

        assert card.children[0].children == expected_name
        assert card.children[1].children == expected_content

    def test_the_configurations_the_rules_describe_are_previewed_until_saved(self, pages, monkeypatch):
        variables = {"domain-a": ["width"]}
        monkeypatch.setattr(pages.rules, "ctx", self.fake_ctx(pages, variables))
        fields = self.field_values(variables, {("domain-a", "width"): {"type": "list", "list": "8, 16"}})
        metadata = [{"domain_uuid": "domain-a", "domain_name": hard_settings.main_parameter_domain}]

        def preview(saved):
            return pages.rules.update_rules_preview(
                ["${width}bits"], ["parameter W = ${width}"], [""], [saved], "normal", *fields, [[]], [], metadata,
            )[2][0]

        # Nothing saved yet: the cards of the domain show none of this.
        titles = [
            child.children[0].children
            for child in preview(None)[1].children
        ]
        assert titles == ["8bits", "16bits"]
        # Saved: the configuration cards below are the real thing.
        saved = pages.rules.rules_settings(
            "${width}bits", "parameter W = ${width}",
            {"width": {"type": "list", "settings": {"list": [8, 16]}}},
        )
        assert preview(saved) == []

    def test_preview_updates_generated_content_before_rules_are_saved(self, pages, monkeypatch):
        variables = {"domain-a": ["width"]}
        monkeypatch.setattr(pages.rules, "ctx", self.fake_ctx(pages, variables))
        fields = self.field_values(variables, {("domain-a", "width"): {"type": "list", "list": "8"}})
        metadata = [{"domain_uuid": "domain-a", "domain_name": hard_settings.main_parameter_domain}]
        saved = pages.rules.rules_settings(
            "${width}", "old value = ${width}",
            {"width": {"type": "list", "settings": {"list": [8]}}},
        )
        held = [{
            "domain_uuid": "domain-a",
            "config_name": "8.txt",
            "origin": "generated",
            "config_content": "old value = 8",
        }]

        config_preview = pages.rules.update_rules_preview(
            ["${width}"], ["new value = ${width}"], [""], [saved], "normal", *fields, [[]], held, metadata,
        )[2][0]
        card = config_preview[1].children[0]

        assert "odx-config-preview-changed" in card.className
        assert card.children[1].children == "new value = 8"

    def test_preview_pane_uses_unsaved_generated_content(self, pages, monkeypatch):
        variables = {"domain-a": ["width"]}
        monkeypatch.setattr(pages.rules, "ctx", self.fake_ctx(pages, variables))
        fields = self.field_values(variables, {("domain-a", "width"): {"type": "list", "list": "8"}})
        metadata = [{"domain_uuid": "domain-a", "domain_name": hard_settings.main_parameter_domain}]
        saved = pages.rules.rules_settings(
            "${width}", "old value = ${width}",
            {"width": {"type": "list", "settings": {"list": [8]}}},
        )

        pending = pages.editor.unsaved_rule_configurations(
            ["${width}"], ["new value = ${width}"], [saved], fields, metadata,
        )
        replacement_text = pages.editor.replacement_text_for_preview(
            "config-8", "domain-a", {"config-8": "old value = 8"},
            [{
                "domain_uuid": "domain-a",
                "config_uuid": "config-8",
                "config_name": "8.txt",
                "origin": "generated",
            }],
            pending["domain-a"],
        )

        assert replacement_text == "new value = 8"

        monkeypatch.setattr(
            pages.editor, "get_instance_collection_context",
            lambda search, settings: ("arch", "arch", {"arch": object()}),
        )
        monkeypatch.setattr(
            pages.editor, "preview_pane",
            lambda domain_uuid, mode, settings, domain_settings, text, base_path=None: text,
        )
        result = pages.editor.update_preview_all(
            "?arch=arch", None,
            [[True]], [""], [""], [""], [{}],
            # The contents no longer trigger the callback: the debounced signal
            # does, and outside a callback every pane is rebuilt anyway.
            None, ["old value = 8"], ["config-8"],
            ["${width}"], ["new value = ${width}"], [""], [saved], *fields,
            [{
                "domain_uuid": "domain-a",
                "config_uuid": "config-8",
                "config_name": "8.txt",
                "origin": "generated",
            }],
            metadata, {},
        )

        assert result == ["new value = 8"]

    def test_preview_pane_keeps_the_selected_blacklisted_configuration(self, pages):
        replacement_text = pages.editor.replacement_text_for_preview(
            "config-16", "domain-a",
            {"config-16": "value = 16", "config-8": "value = 8"},
            [{
                "domain_uuid": "domain-a",
                "config_uuid": "config-16",
                "config_name": "16.txt",
                "origin": "blacklisted",
            }],
            {"8": "new value = 8"},
        )

        assert replacement_text == "value = 16"

    def test_the_preview_shows_the_whole_list_the_rules_would_leave_behind(self, pages, monkeypatch):
        # One list, in order: what a change means is the list it results in, and
        # a new configuration reads in its place among the old ones.
        variables = {"domain-a": ["width"]}
        monkeypatch.setattr(pages.rules, "ctx", self.fake_ctx(pages, variables))
        metadata = [{"domain_uuid": "domain-a", "domain_name": "width"}]

        def held(*configs):
            return [
                {"domain_uuid": "domain-a", "config_name": name + ".txt",
                 "origin": origin, "config_content": name}
                for name, origin in configs
            ]

        def preview(values, configurations):
            fields = self.field_values(variables, {("domain-a", "width"): {"type": "list", "list": values}})
            return pages.rules.update_rules_preview(
                [""], [""], [""], [None], "normal", *fields, [[]], configurations, metadata,
            )[2][0]

        def names_and_chips(cards):
            return [(card.children[0].children, card.children[2].children.children) for card in cards]

        holds = held(("8", "generated"), ("custom", "manual"))

        # One value added to a domain that already holds the other: the whole
        # list, the new one among the ones it keeps, sorted by name.
        cards = preview("8, 16", holds)[1].children
        assert names_and_chips(cards) == [("8", "generated"), ("16", "preview"), ("custom", "manual")]

        # One value dropped instead: the configuration it produced is on its way
        # out, and says so where a new one says "preview".
        cards = preview("16", holds)[1].children
        assert names_and_chips(cards) == [("8", "removed"), ("16", "preview"), ("custom", "manual")]
        assert "odx-config-preview-removed" in cards[0].className
        # A configuration written by hand is not the rules' to take away.
        assert "odx-config-preview-kept" in cards[2].className

        # The rules describing exactly what the domain holds change nothing.
        assert preview("8", held(("8", "generated"))) == []

    def test_the_variables_of_a_domain_are_always_shown(self, pages):
        # No fold of its own: a variable is a row saying what it holds, so the
        # list is readable without opening anything.
        section = pages.rules.rules_section("main", self.RULES)
        row = section.children[2]
        assert row.id == {"type": "cfg-variable-cards-row", "domain_uuid": "main"}
        assert not (getattr(row, "style", None) or {}).get("display") == "none"

    ######################################
    # Several sets of rules, one domain
    ######################################

    #: A domain whose configurations are the union of two sets of rules: what a
    #: parameter deciding which *other* parameters mean anything asks for.
    RULE_SETS = {
        "configurations": [
            {"name": "M${width}", "template": "mode = 0\nwidth = ${width}",
             "constraints": ["${width} > 4"]},
            {"name": "P${depth}", "template": "mode = 1\ndepth = ${depth}"},
        ],
        "variables": {
            "width": {"type": "list", "settings": {"list": [4, 8]}},
            "depth": {"type": "list", "settings": {"list": [1, 2]}},
        },
    }

    @staticmethod
    def components(component, wanted):
        """Every component of one id type in a tree of components, in the order built."""
        found = []
        identifier = getattr(component, "id", None)
        if isinstance(identifier, dict) and identifier.get("type") == wanted:
            found.append(component)
        children = getattr(component, "children", None)
        for child in children if isinstance(children, list) else [children]:
            if child is not None and not isinstance(child, str):
                found += TestConfigurationRules.components(child, wanted)
        return found

    @staticmethod
    def component_ids(component, wanted):
        """Every id of one type in a tree of components, in the order built."""
        return [found.id for found in TestConfigurationRules.components(component, wanted)]

    def test_a_domain_of_several_rule_sets_opens_one_card_per_set(self, pages):
        blocks, variables = pages.rules.rule_set_fields(self.RULE_SETS)
        assert [(name, constraints) for _key, name, _template, constraints in blocks] == [
            ("M${width}", ["${width} > 4"]),
            ("P${depth}", []),
        ]
        assert list(variables) == ["width", "depth"]

        section = pages.rules.domain_advanced_section("domain-a", self.RULE_SETS)
        # One field of each kind per set of rules, each carrying the block it
        # edits: a card of the panel is one set of rules, and is saved as one.
        for field in ("cfg-gen-name", "cfg-gen-template", "cfg-gen-constraints"):
            assert [i["rule_set"] for i in self.component_ids(section, field)] == [0, 1]
        # And a way to delete either of them, or to add another.
        assert [i["rule_set"] for i in self.component_ids(section, "cfg-delete-rule-set")] == [0, 1]
        assert len(self.component_ids(section, "cfg-new-rule-set")) == 1
        # The panel opens by itself: a union is never what a domain says by
        # declaring its variables alone.
        assert section.children[1].style == {"marginTop": "12px"}

    def test_a_domain_of_one_set_of_rules_has_nothing_to_delete(self, pages):
        # A domain describes its configurations with one set of rules or
        # several, never with none: the only one has no delete button.
        section = pages.rules.domain_advanced_section("domain-a", self.RULES)
        assert self.component_ids(section, "cfg-delete-rule-set") == []
        assert [i["rule_set"] for i in self.component_ids(section, "cfg-gen-name")] == [0]

    def test_the_panel_of_a_domain_of_several_rule_sets_has_nothing_to_save(self, pages):
        # The union is written back as it stands: a panel nobody touched must
        # not report unsaved changes, or "Save all" would flatten the file.
        blocks, variables = pages.rules.rule_set_fields(self.RULE_SETS)
        stored = pages.rules.stored_rules_settings(self.RULE_SETS, blocks, variables, "domain-a")
        current = pages.rules.form_rules_settings(
            blocks, variables, "domain-a", stored, match={},
        )
        assert current == stored
        assert stored["configurations"] == self.RULE_SETS["configurations"]

    def test_the_configurations_of_a_union_are_not_combined(self, pages, monkeypatch):
        # Two sets of rules over the same variables: what the domain holds is
        # what each of them produces, side by side -- never their product.
        variables = {"domain-a": ["width", "depth"]}
        monkeypatch.setattr(
            pages.rules, "ctx",
            self.fake_ctx(pages, variables, rule_sets_by_domain={"domain-a": 2}),
        )
        fields = self.field_values(variables, {
            ("domain-a", "width"): {"type": "list", "list": "4, 8"},
            ("domain-a", "depth"): {"type": "list", "list": "1, 2"},
        })
        _previews, summaries, config_previews, _n, _t = pages.rules.update_rules_preview(
            ["M${width}", "P${depth}"],
            ["mode = 0\nwidth = ${width}", "mode = 1\ndepth = ${depth}"],
            ["${width} > 4", ""],
            [None], "normal", *fields, [[]], [],
            [{"domain_uuid": "domain-a", "domain_name": "mode"}],
        )
        # One "M" left by the constraint, and both "P": three, not four times two.
        assert summaries[0][0].children == "3 configurations"
        titles = [card.children[0].children for card in config_previews[0][1].children]
        assert titles == ["M8", "P1", "P2"]

    def test_a_set_of_rules_can_be_added_duplicated_and_deleted(self, pages, monkeypatch):
        variables = {"domain-a": ["width"]}
        fields = self.field_values(variables, {("domain-a", "width"): {"type": "list", "list": "8"}})
        metadata = [{"domain_uuid": "domain-a", "domain_name": "mode"}]

        def cards(names, templates, constraints, triggered, rule_sets):
            monkeypatch.setattr(
                pages.rules, "ctx",
                self.fake_ctx(pages, variables, triggered_id=triggered,
                              rule_sets_by_domain={"domain-a": rule_sets}),
            )
            kind = triggered["type"]
            clicks = [1] if kind == "cfg-new-rule-set" else []
            duplicates = [1] if kind == "cfg-duplicate-rule-set" else []
            deletes = [1] if kind == "cfg-delete-rule-set" else []
            return pages.rules.update_rule_set_cards(
                clicks, deletes, duplicates, names, templates, constraints, metadata, *fields,
            )[0]

        def names_of(row):
            return [
                component.value
                for card in row
                for component in self.components(card, "cfg-gen-name")
            ]

        def keys_of(row):
            return [
                identifier["rule_set"]
                for card in row
                for identifier in self.component_ids(card, "cfg-gen-name")
            ]

        # One set of rules, and one more: the new one is empty and last.
        row = cards(["w${width}"], ["W = ${width}"], [""],
                    {"type": "cfg-new-rule-set", "domain_uuid": "domain-a"}, 1)
        assert keys_of(row) == [0, 1]

        # And back: deleting one leaves the other exactly as it was.
        row = cards(["w${width}", ""], ["W = ${width}", ""], ["", ""],
                    {"type": "cfg-delete-rule-set", "domain_uuid": "domain-a", "rule_set": 1}, 2)
        assert keys_of(row) == [0]

        # A duplicate is what the set says now, right after it.
        row = cards(["w${width}", "d${width}"], ["W = ${width}", "D = ${width}"], ["", ""],
                    {"type": "cfg-duplicate-rule-set", "domain_uuid": "domain-a", "rule_set": 0}, 2)
        assert keys_of(row) == [0, 2, 1]
        assert names_of(row) == ["w${width}", "w${width}", "d${width}"]

    def test_a_domain_of_one_set_of_rules_is_still_written_as_one_block(self, pages):
        # Adding a set of rules is what makes a domain a union; a domain of one
        # keeps the shape every settings file has always had.
        variables = {"width": {"type": "list", "settings": {"list": [8]}}}
        one = pages.rules.form_rules_settings([(0, "w${width}", "W = ${width}", [])], variables, "mode")
        two = pages.rules.form_rules_settings(
            [(0, "w${width}", "W = ${width}", []), (1, "d${width}", "D = ${width}", [])],
            variables, "mode",
        )
        assert isinstance(one["configurations"], dict)
        assert isinstance(two["configurations"], list)
        assert [block["name"] for block in two["configurations"]] == ["w${width}", "d${width}"]

    def test_editing_one_set_of_rules_keeps_what_the_others_hide(self, pages):
        # The blacklist of a block is not something the form edits: it has to
        # survive an edit of any card, its own included.
        saved = {
            "configurations": [
                {"name": "M${w}", "template": "m", "blacklist": ["M8"]},
                {"name": "P${w}", "template": "p", "variables": ["w"]},
            ],
            "variables": {"w": {"type": "list", "settings": {"list": [8]}}},
        }
        written = pages.rules.form_rules_settings(
            [(0, "M${w}", "MODE = m", []), (1, "P${w}", "p", [])],
            saved["variables"], "mode", saved,
        )["configurations"]
        assert written[0] == {"name": "M${w}", "template": "MODE = m", "blacklist": ["M8"]}
        assert written[1] == {"name": "P${w}", "template": "p", "variables": ["w"]}

    def test_the_templates_are_folded_away_next_to_the_target_file(self, pages):
        # A domain of a single variable needs neither template: they open only
        # when they are not optional.
        single = pages.rules.domain_advanced_section(
            "main", {"variables": {"width": {"type": "list", "settings": {"list": [8]}}}},
            domain_name="width",
        )
        written = pages.rules.domain_advanced_section("main", self.RULES, domain_name="width")
        assert single.children[1].style == {"display": "none"}
        assert written.children[1].style == {"marginTop": "12px"}

    ######################################
    # Where the generator page used to be
    ######################################

    def test_the_old_generator_url_leads_to_the_domain_it_named(self, pages):
        assert pages.generator.editor_link("?arch=ALU&domain=Mul") == "/config_editor?arch=ALU&domain=Mul"
        assert pages.generator.editor_link("?workflow=train") == "/config_editor?workflow=train"

    ######################################
    # Several domains, one page
    ######################################

    def fake_ctx(self, pages, variables_by_domain, triggered_id=None, rule_sets_by_domain=None):
        """
        The callback context of a page showing several domains: the ids Dash
        matched for every variable field, in the order it returns their values.
        """
        ids = [
            {"type": "cfg-variable-title", "name": name, "domain_uuid": domain_uuid}
            for domain_uuid, names in variables_by_domain.items()
            for name in names
        ]
        # And the ids of the rules fields: one set of rules per domain unless
        # the test says otherwise, in the order their values come back.
        rule_sets = rule_sets_by_domain or dict((domain_uuid, 1) for domain_uuid in variables_by_domain)
        rule_ids = [
            {"type": "cfg-gen-name", "domain_uuid": domain_uuid, "rule_set": key}
            for domain_uuid, count in rule_sets.items()
            for key in range(count)
        ]
        return SimpleNamespace(
            triggered_id=triggered_id,
            inputs_list=[
                [{"id": identifier} for identifier in ids],
                [{"id": identifier} for identifier in rule_ids],
            ],
            states_list=[],
        )

    def field_values(self, variables_by_domain, values):
        """
        The flat per-field value lists Dash hands a callback, filled from
        {(domain_uuid, variable): {field: value}}.
        """
        keys = [(domain_uuid, name) for domain_uuid, names in variables_by_domain.items() for name in names]
        lists = []
        for pattern in ["variable-title", "variable-type", "variable-field-base", "variable-field-from",
                        "variable-field-to", "variable-field-from_2_pow", "variable-field-to_2_pow",
                        "variable-field-from_type", "variable-field-to_type", "variable-field-step",
                        "variable-field-op", "variable-field-list", "variable-field-source",
                        "variable-field-sources", "variable-field-format", "variable-field-group"]:
            field = pattern.replace("variable-field-", "").replace("variable-", "")
            lists.append([
                key[1] if field == "title" else values[key].get(field, "")
                for key in keys
            ])
        return lists

    def test_each_domain_previews_its_own_variables(self, pages, monkeypatch):
        # Two domains, each with a variable called "width": the values of one
        # must not leak into the preview of the other.
        variables = {"domain-a": ["width"], "domain-b": ["width"]}
        monkeypatch.setattr(pages.rules, "ctx", self.fake_ctx(pages, variables))
        fields = self.field_values(variables, {
            ("domain-a", "width"): {"type": "list", "list": "8, 16"},
            ("domain-b", "width"): {"type": "list", "list": "1, 2, 3"},
        })
        previews, summaries, config_previews, _n, _t = pages.rules.update_rules_preview(
            ["${width}bits", "d${width}"],
            ["parameter W = ${width}", "parameter D = ${width}"],
            ["", ""], [None, None], "normal",
            *fields, [[], []], [],
            [{"domain_uuid": "domain-a", "domain_name": hard_settings.main_parameter_domain},
             {"domain_uuid": "domain-b", "domain_name": "depth"}],
        )
        # The badge of each summary counts the configurations of that domain
        assert summaries[0][0].children == "2 configurations"
        assert summaries[1][0].children == "3 configurations"
        # And each variable row says the values of its own variable.
        assert [row[1].children for row in previews] == ["8, 16", "1, 2, 3"]

    def test_a_domain_without_rules_says_what_it_holds_instead(self, pages, monkeypatch):
        variables = {"main": []}
        monkeypatch.setattr(pages.rules, "ctx", self.fake_ctx(pages, variables))
        previews, summaries, config_previews, _n, _t = pages.rules.update_rules_preview(
            [""], [""], [""], [None], "normal", *self.field_values(variables, {}), [[]], [],
            [{"domain_uuid": "main", "domain_name": hard_settings.main_parameter_domain}],
        )
        assert summaries[0][0].children == "no rules"

    def test_saving_writes_only_the_domain_whose_button_was_pressed(self, pages, monkeypatch, tmp_path):
        import yaml

        from odatix.workspace.architectures import ArchitectureCollection

        root = tmp_path / "architectures"
        for domain in ("arch", "arch/depth"):
            (root / domain).mkdir(parents=True)
            (root / domain / "_settings.yml").write_text(yaml.safe_dump({}))

        instances = ArchitectureCollection(None, str(root))
        monkeypatch.setattr(
            pages.rules, "get_instance_collection_context",
            lambda search, settings: ("arch", "arch", instances),
        )
        variables = {"main-uuid": ["width"], "depth-uuid": ["depth"]}
        monkeypatch.setattr(
            pages.rules, "ctx",
            self.fake_ctx(pages, variables, triggered_id={"type": "cfg-save-rules", "domain_uuid": "main-uuid"}),
        )
        fields = self.field_values(variables, {
            ("main-uuid", "width"): {"type": "list", "list": "8, 16"},
            ("depth-uuid", "depth"): {"type": "list", "list": "4"},
        })
        metadata = [
            {"domain_uuid": "main-uuid", "domain_name": hard_settings.main_parameter_domain},
            {"domain_uuid": "depth-uuid", "domain_name": "depth"},
        ]
        stores, bumps = pages.rules.save_rules(
            [1, 0], None, None,
            ["${width}bits", "d${depth}"],
            ["parameter W = ${width}", "parameter D = ${depth}"],
            ["", ""], ["", ""],
            *fields,
            metadata, [None, None], [0, 0], "?arch=arch", {},
        )
        written = yaml.safe_load((root / "arch" / "_settings.yml").read_text())
        assert written["configurations"]["name"] == "${width}bits"
        assert list(written["variables"]) == ["width"]
        # The other domain was left alone, and only the saved one asks for its
        # configurations to be read again.
        assert yaml.safe_load((root / "arch" / "depth" / "_settings.yml").read_text()) == {}
        assert bumps[0] == 1
        assert bumps[1] is dash.no_update

    def test_save_all_writes_every_domain_whose_rules_changed(self, pages, monkeypatch, tmp_path):
        import yaml

        from odatix.workspace.architectures import ArchitectureCollection

        root = tmp_path / "architectures"
        for domain in ("arch", "arch/depth"):
            (root / domain).mkdir(parents=True)
            (root / domain / "_settings.yml").write_text(yaml.safe_dump({}))

        instances = ArchitectureCollection(None, str(root))
        monkeypatch.setattr(
            pages.rules, "get_instance_collection_context",
            lambda search, settings: ("arch", "arch", instances),
        )
        variables = {"main-uuid": ["width"], "depth-uuid": ["depth"]}
        monkeypatch.setattr(
            pages.rules, "ctx",
            self.fake_ctx(pages, variables, triggered_id={"page": "/config_editor", "action": "save-all"}),
        )
        fields = self.field_values(variables, {
            ("main-uuid", "width"): {"type": "list", "list": "8, 16"},
            ("depth-uuid", "depth"): {"type": "list", "list": "4"},
        })
        metadata = [
            {"domain_uuid": "main-uuid", "domain_name": hard_settings.main_parameter_domain},
            {"domain_uuid": "depth-uuid", "domain_name": "depth"},
        ]
        pages.rules.save_rules(
            [0, 0], None, [1],
            ["${width}bits", "d${depth}"],
            ["parameter W = ${width}", "parameter D = ${depth}"],
            ["", ""], ["", ""],
            *fields,
            metadata, [None, None], [0, 0], "?arch=arch", {},
        )
        assert yaml.safe_load((root / "arch" / "_settings.yml").read_text())["configurations"]["name"] == "${width}bits"
        assert yaml.safe_load((root / "arch" / "depth" / "_settings.yml").read_text())["configurations"]["name"] == "d${depth}"

    def test_the_save_button_of_a_domain_lights_up_only_for_its_own_change(self, pages, monkeypatch):
        variables = {"main-uuid": ["width"], "depth-uuid": ["depth"]}
        monkeypatch.setattr(pages.rules, "ctx", self.fake_ctx(pages, variables))
        fields = self.field_values(variables, {
            ("main-uuid", "width"): {"type": "list", "list": "8, 16"},
            ("depth-uuid", "depth"): {"type": "list", "list": "4"},
        })
        saved_depth = pages.rules.rules_settings(
            "d${depth}", "parameter D = ${depth}",
            {"depth": {"type": "list", "settings": {"list": [4]}}},
            # As a panel stores it: the selectors of a directory are saved with
            # its rules, so an untouched one holds an empty block of them.
            match={},
        )
        classes, tooltips, _match_classes, _match_tooltips = pages.rules.update_save_rules_button(
            ["${width}bits", "d${depth}"],
            ["parameter W = ${width}", "parameter D = ${depth}"],
            ["", ""], ["", ""],
            [None, saved_depth],
            *fields,
            [{"domain_uuid": "main-uuid", "domain_name": hard_settings.main_parameter_domain},
             {"domain_uuid": "depth-uuid", "domain_name": "depth"}],
        )
        assert "warning" in classes[0]
        assert "disabled" in classes[1]

    def test_adding_a_variable_touches_only_its_own_domain(self, pages, monkeypatch):
        variables = {"main-uuid": ["width"], "depth-uuid": ["depth"]}
        monkeypatch.setattr(
            pages.rules, "ctx",
            self.fake_ctx(pages, variables, triggered_id={"type": "cfg-new-variable", "domain_uuid": "depth-uuid"}),
        )
        rows = [
            pages.rules.rules_section("main-uuid", self.RULES).children[1].children,
            pages.rules.rules_section("depth-uuid", self.RULES).children[1].children,
        ]
        metadata = [
            {"domain_uuid": "main-uuid", "domain_name": hard_settings.main_parameter_domain},
            {"domain_uuid": "depth-uuid", "domain_name": "depth"},
        ]
        updated = pages.rules.update_variable_cards(
            [0, 1], [], [], rows, metadata, *self.field_values(variables, {
                ("main-uuid", "width"): {"type": "list", "list": "8"},
                ("depth-uuid", "depth"): {"type": "list", "list": "4"},
            }),
        )
        assert updated[0] is dash.no_update
        ids = [card.id for card in updated[1] if isinstance(getattr(card, "id", None), dict)]
        assert {"type": "cfg-variable-card", "name": "var", "domain_uuid": "depth-uuid"} in ids
        # The add card stays last
        assert ids[-1] == {"type": "cfg-add-variable-card", "domain_uuid": "depth-uuid"}


class TestConfigurationEditorScoping:
    """
    A domain holding hundreds of configurations turned every keystroke into a
    round-trip carrying the whole page. What is left on the server now answers
    only for what actually changed: these are the rules that keep it that way.
    """

    @pytest.fixture(autouse=True)
    def editor(self):
        dash.Dash(__name__, use_pages=True, pages_folder="")
        import odatix.gui.pages.config_editor as config_editor

        return config_editor

    def triggered(self, editor, monkeypatch, prop_ids):
        monkeypatch.setattr(editor, "ctx", SimpleNamespace(triggered_prop_ids=prop_ids))

    def test_a_keystroke_only_makes_its_own_domain_stale(self, editor, monkeypatch):
        self.triggered(editor, monkeypatch, {"config-content-debounce.data": "config-content-debounce"})
        stale = editor.preview_domains_to_refresh({"stamp": 1, "domains": ["domain-a"]})
        assert stale == {"domain-a"}

    def test_typing_in_two_domains_makes_both_stale(self, editor, monkeypatch):
        self.triggered(editor, monkeypatch, {"config-content-debounce.data": "config-content-debounce"})
        stale = editor.preview_domains_to_refresh({"stamp": 1, "domains": ["domain-a", "domain-b"]})
        assert stale == {"domain-a", "domain-b"}

    def test_a_domain_scoped_field_only_makes_its_domain_stale(self, editor, monkeypatch):
        self.triggered(editor, monkeypatch, {
            "x.value": {"type": "start_delimiter", "domain_uuid": "domain-b"},
        })
        assert editor.preview_domains_to_refresh(None) == {"domain-b"}

    def test_a_structural_change_makes_every_pane_stale(self, editor, monkeypatch):
        # The section was rebuilt: nothing says which domain, so all of them.
        self.triggered(editor, monkeypatch, {"param-domains-section.children": "param-domains-section"})
        assert editor.preview_domains_to_refresh(None) is None

    def test_the_debounce_can_ask_for_every_pane(self, editor, monkeypatch):
        # A trigger the client could not tie to a domain publishes no domain list.
        self.triggered(editor, monkeypatch, {"config-content-debounce.data": "config-content-debounce"})
        assert editor.preview_domains_to_refresh({"stamp": 1, "domains": None}) is None

    def test_outside_a_callback_every_pane_is_stale(self, editor):
        assert editor.preview_domains_to_refresh(None) is None

    def test_a_card_carries_its_looks_as_classes(self, editor):
        # The style dictionaries the cards used to carry were sent once per card
        # on every round-trip of a row.
        card = editor.config_card("domain-a", "config-1", "8.txt", "", "")
        assert getattr(card, "style", None) is None
        assert "odx-config-card" in card.className
        title, content = card.children[0].children[0], card.children[1]
        assert getattr(title, "style", None) is None
        assert getattr(content, "style", None) is None
        assert "odx-config-name" in title.className
        assert "odx-config-content" in content.className

    def test_the_layout_switch_keeps_what_a_card_is(self, editor):
        assert "wide" in editor.card_class("wide", False)
        assert "wide" not in editor.card_class("normal", False)
        blacklisted = editor.card_class("wide", True)
        assert "odx-config-blacklisted" in blacklisted and "odx-config-card" in blacklisted


class TestConfigurationPaging:
    """
    A domain holding hundreds of configurations only gives cards to the first of
    them. What is left has no card, no text area and no store: it is counted,
    and read from the domain again when the show more card is clicked.
    """

    @pytest.fixture(autouse=True)
    def pages(self):
        dash.Dash(__name__, use_pages=True, pages_folder="")
        import odatix.gui.pages.config_editor as config_editor

        return config_editor

    def domain(self, tmp_path, count):
        """A parameter domain holding `count` configuration files."""
        import yaml

        from odatix.workspace.architectures import ArchitectureCollection

        root = tmp_path / "architectures"
        path = root / "arch"
        path.mkdir(parents=True, exist_ok=True)
        (path / "_settings.yml").write_text(yaml.safe_dump({}))
        for index in range(count):
            (path / f"config{index:03d}.txt").write_text(f"WIDTH = {index}")
        return ArchitectureCollection(None, str(root))

    def cards_of(self, row):
        return [card for card in row if getattr(card, "id", {}).get("type") == "config-card"]

    def show_more(self, row):
        return next(card for card in row if getattr(card, "id", {}).get("type") == "show-more-card")

    def hidden_of(self, row):
        return self.show_more(row).children[1].data

    def test_a_long_domain_only_gets_a_page_of_cards(self, pages, tmp_path):
        instances = self.domain(tmp_path, pages.initial_configs_per_page + 12)
        row = pages.build_config_cards(instances["arch"].main_domain, "main-uuid", "normal")

        assert len(self.cards_of(row)) == pages.initial_configs_per_page
        assert self.hidden_of(row) == 12
        assert "odx-hidden" not in self.show_more(row).className

    def test_a_short_domain_hides_the_show_more_card(self, pages, tmp_path):
        instances = self.domain(tmp_path, 3)
        row = pages.build_config_cards(instances["arch"].main_domain, "main-uuid", "normal")

        assert len(self.cards_of(row)) == 3
        assert self.hidden_of(row) == 0
        assert "odx-hidden" in self.show_more(row).className

    def test_the_cards_that_are_there_are_the_first_ones(self, pages, tmp_path):
        instances = self.domain(tmp_path, pages.initial_configs_per_page + 5)
        row = pages.build_config_cards(instances["arch"].main_domain, "main-uuid", "normal")
        names = [card.children[0].children[0].value for card in self.cards_of(row)]

        assert names == [f"config{index:03d}" for index in range(pages.initial_configs_per_page)]

    def test_the_add_card_stays_last(self, pages, tmp_path):
        instances = self.domain(tmp_path, 3)
        row = pages.build_config_cards(instances["arch"].main_domain, "main-uuid", "normal")

        assert row[-1].id["type"] == "add-config-card"
        # A new configuration joins the others, not the cards that close the row.
        pages.insert_config_card(row, pages.config_card("main-uuid", "new-uuid", "new.txt", "", ""))
        assert [getattr(card, "id", {}).get("type") for card in row[-3:]] == [
            "config-card", "show-more-card", "add-config-card",
        ]

    def test_showing_more_asks_the_domain_for_what_has_no_card(self, pages, monkeypatch, tmp_path):
        total = pages.initial_configs_per_page + 5
        instances = self.domain(tmp_path, total)
        monkeypatch.setattr(
            pages, "get_instance_collection_context", lambda search, settings: ("arch", "arch", instances),
        )
        monkeypatch.setattr(
            pages, "ctx", SimpleNamespace(
                triggered_id={"type": "show-more-configs", "domain_uuid": "main-uuid"},
                outputs_list=[[{"id": {"domain_uuid": "main-uuid"}}]] * 5,
            ),
        )
        shown = [
            {"domain_uuid": "main-uuid", "config_uuid": f"u{index}", "config_name": f"config{index:03d}.txt"}
            for index in range(pages.initial_configs_per_page)
        ]
        domain_metadata = [{"domain_uuid": "main-uuid", "domain_name": hard_settings.main_parameter_domain}]

        row, label, count, class_name, hidden = pages.show_more_configs(
            [1], shown, domain_metadata, [None], [{"domain_uuid": "main-uuid"}], "normal", "?arch=arch", {},
        )

        # Nothing is left over: the five that had no card now have one.
        assert hidden == [0]
        assert label == [""] and count == [""]
        assert "odx-hidden" in class_name[0]
        # The row is patched rather than rewritten, and the cards go where the
        # ones already shown end.
        patch = row[0].to_plotly_json()
        assert [operation["operation"] for operation in patch["operations"]] == ["Insert"] * 5
        positions = [operation["params"]["index"] for operation in patch["operations"]]
        assert positions == list(range(pages.initial_configs_per_page, total))

    def test_showing_more_stops_at_one_page(self, pages, monkeypatch, tmp_path):
        # One first page shown, two full batches still hidden: one click takes
        # a batch, and what is left is exactly the next one.
        instances = self.domain(tmp_path, pages.initial_configs_per_page + pages.configs_per_page * 2)
        monkeypatch.setattr(
            pages, "get_instance_collection_context", lambda search, settings: ("arch", "arch", instances),
        )
        monkeypatch.setattr(
            pages, "ctx", SimpleNamespace(
                triggered_id={"type": "show-more-configs", "domain_uuid": "main-uuid"},
                outputs_list=[[{"id": {"domain_uuid": "main-uuid"}}]] * 5,
            ),
        )
        shown = [
            {"domain_uuid": "main-uuid", "config_uuid": f"u{index}", "config_name": f"config{index:03d}.txt"}
            for index in range(pages.initial_configs_per_page)
        ]
        domain_metadata = [{"domain_uuid": "main-uuid", "domain_name": hard_settings.main_parameter_domain}]

        row, label, count, class_name, hidden = pages.show_more_configs(
            [1], shown, domain_metadata, [None], [{"domain_uuid": "main-uuid"}], "normal", "?arch=arch", {},
        )

        assert hidden == [pages.configs_per_page]
        assert label == [f"Show {pages.configs_per_page} more"]
        assert "odx-hidden" not in class_name[0]
        assert len(row[0].to_plotly_json()["operations"]) == pages.configs_per_page

    def test_a_rebuilt_row_keeps_what_was_revealed(self, pages, tmp_path):
        instances = self.domain(tmp_path, pages.configs_per_page * 2)
        revealed = [
            {"domain_uuid": "main-uuid", "config_name": f"config{index:03d}.txt"}
            for index in range(pages.initial_configs_per_page + 7)
        ]
        row = pages.build_config_cards(
            instances["arch"].main_domain, "main-uuid", "normal",
            shown=pages.cards_shown(revealed, "main-uuid"),
        )

        assert len(self.cards_of(row)) == pages.initial_configs_per_page + 7

    def test_a_shortened_domain_still_counts_everything_it_holds(self, pages):
        metadata = [
            {"domain_uuid": "main-uuid", "config_uuid": f"u{index}", "origin": "manual"}
            for index in range(pages.configs_per_page)
        ]
        counters = pages.update_config_counters(
            metadata, [12], [None], [{"domain_uuid": "main-uuid", "domain_name": "main"}],
        )
        stats = [stat.children[0].children for stat in counters[0]]

        assert stats[0] == str(pages.configs_per_page + 12)
        assert stats[1] == "12"


######################################
# Task editor (workflows and simulations)
######################################

class TestTaskEditor:
    """The task cards of the workflow and simulation editors, shared."""

    @pytest.fixture
    def workflow_editor_module(self):
        dash.Dash(__name__, use_pages=True, pages_folder="")
        import odatix.gui.pages.workflow_editor as workflow_editor

        return workflow_editor

    @pytest.fixture
    def sim_editor_module(self):
        dash.Dash(__name__, use_pages=True, pages_folder="")
        import odatix.gui.pages.sim_editor as sim_editor

        return sim_editor

    @staticmethod
    def _fields(cards):
        """The value of every task field of the cards, as the page reads them."""
        import odatix.gui.task_editor as te

        def walk(component):
            yield component
            children = getattr(component, "children", None)
            for child in children if isinstance(children, list) else [children]:
                if child is not None and not isinstance(child, str):
                    yield from walk(child)

        columns = {field: [] for field in te.TASK_FIELDS}
        for card in cards:
            for component in walk(card):
                cid = getattr(component, "id", None)
                if isinstance(cid, dict) and cid.get("type", "").endswith(tuple("-task-field-" + f for f in te.TASK_FIELDS)):
                    field = cid["type"].split("-task-field-", 1)[1]
                    columns[field].append(component.value)
        return [columns[field] for field in te.TASK_FIELDS]

    def test_tasks_round_trip_through_their_cards(self):
        import odatix.gui.task_editor as te
        import yaml

        import os

        from conftest import EXAMPLES_DIR

        with open(os.path.join(EXAMPLES_DIR, "odatix_userconfig", "workflows", "tensorflow", "_settings.yml")) as f:
            tasks = yaml.safe_load(f)["tasks"]
        assert any("on_failure_commands" in task for task in tasks)

        for prefix in ("wf", "sim"):
            cards = te.cards_from_tasks(prefix, tasks)
            assert te.build_tasks_list(*self._fields(cards)) == tasks

    def test_a_fallback_is_shown_without_unfolding(self):
        import odatix.gui.task_editor as te

        with_fallback = te.task_card("wf", "env", values={"commands": "a", "on_failure_commands": "b"})
        without = te.task_card("wf", "env", values={"commands": "a"})

        def panel(card):
            return next(
                c for c in self._walk_all(card)
                if getattr(c, "id", None) == {"type": "wf-more-task-field-div", "name": "env"}
            )

        assert panel(with_fallback).style["display"] != "none"
        assert panel(without).style["display"] == "none"

    @staticmethod
    def _walk_all(component):
        yield component
        children = getattr(component, "children", None)
        for child in children if isinstance(children, list) else [children]:
            if child is not None and not isinstance(child, str):
                yield from TestTaskEditor._walk_all(child)

    def test_both_editors_listen_to_every_field(self, workflow_editor_module, sim_editor_module):
        import odatix.gui.task_editor as te

        for module, prefix, callback in (
            (workflow_editor_module, "wf", "save_and_status"),
            (sim_editor_module, "sim", "save_and_status"),
        ):
            source = __import__("inspect").getsource(getattr(module, callback))
            assert "task_on_failure_commands" in source
        assert len(te.task_field_dependencies("wf", dash.State)) == len(te.TASK_FIELDS)

    def test_a_workflow_always_keeps_its_main_task(self, workflow_editor_module):
        tasks = workflow_editor_module.wf_build_tasks_list(["prep"], [""], ["echo"], [""], [""], [""])
        assert [task["name"] for task in tasks] == ["main", "prep"]

    def test_duplicating_a_task_keeps_its_fallback(self, workflow_editor_module, monkeypatch):
        from types import SimpleNamespace

        cards = workflow_editor_module.wf_cards_from_tasks(
            [{"name": "main", "commands": ["a"], "on_failure_commands": ["b"]}]
        )
        cards = [card.to_plotly_json() if hasattr(card, "to_plotly_json") else card for card in cards]
        monkeypatch.setattr(
            workflow_editor_module, "ctx",
            SimpleNamespace(triggered_id={"type": "wf-duplicate-task", "name": "main"}),
        )
        result = workflow_editor_module.update_wf_task_cards(
            None, [1], [None], cards, ["main"], [""], ["a"], ["b"], [""], [""],
        )
        names, _, _, fallbacks, _, _ = self._fields([c for c in result if not isinstance(c, dict)])
        assert "main_copy1" in names
        assert fallbacks[names.index("main_copy1")] == "b"
