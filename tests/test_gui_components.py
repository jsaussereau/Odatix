"""Tests for GUI building blocks: icons, pictograms, navigation bar."""

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.gui

dash_svg = pytest.importorskip("dash_svg")
dash = pytest.importorskip("dash")
from dash import dcc, html

import odatix.gui.icons as icons
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
    "workflow", "architecture", "run", "monitor", "explorer", "workspace",
    "documentation", "eda_tool", "fmax", "custom_freq", "analysis",
    "simulation", "workspace_empty", "workspace_examples",
]


class TestIcons:
    @pytest.mark.parametrize("name", KNOWN_ICONS)
    def test_known_icons_build(self, name):
        svg = icons.icon(name)
        assert svg is not None
        assert svg.viewBox == "0 0 24 24"
        # line-art style: stroked with currentColor, no fill
        assert svg.stroke == "currentColor"
        assert svg.fill == "none"
        assert len(svg.children) > 0

    def test_unknown_icon_returns_empty_svg(self):
        svg = icons.icon("does_not_exist")
        assert svg is not None
        assert not getattr(svg, "children", None)

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
        svg = icons.icon("save", width="16px", height="16px")
        assert svg.width == "16px"
        assert svg.height == "16px"


######################################
# Navigation bar
######################################

class TestNavigation:
    def test_nav_groups_structure(self):
        # membership only: the display order is a UI choice
        labels = {entry[0] for entry in navigation.nav_groups}
        assert labels == {"Configure", "Run", "Monitor", "Explorer", "Settings"}

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

        settings_href, settings_items = as_dict["Settings"]
        assert settings_href == "/workspace"
        assert ("Workspace", "/workspace") in settings_items

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
            "choose_eda_tool", "monitor", "workspace_settings",
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
        gui = SimpleNamespace(start_theme=themes.list[0] if themes.list else "dark")
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
        domains_configs = {
            domain.name: domain.configs.names()
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
        className, tooltip, _store = jobs_config_module.save_architecture_selections(
            None,                 # save-all n_clicks
            switch_values,
            preview_values,
            [],                   # sim-selection stores (simulation mode only)
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

        className, tooltip, _store = jc.save_architecture_selections(
            None,
            [v for v, _ in switches], [v for v, _ in previews],
            [],                            # sim-selection stores (simulation mode only)
            [], [], "", [], "", "", "",   # frequency inputs
            "", "",                        # lower/upper fmax bound
            None,                          # analysis-tools
            [], [], "16", [], "300", [], [],   # nb_jobs changed 8 -> 16
            [i for _, i in switches], [i for _, i in previews],
            [],                            # sim-selection store ids
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
        className, tooltip, store = jc.save_architecture_selections(
            None,
            [], [],                        # no arch widgets yet
            [],                            # sim-selection stores (simulation mode only)
            [], [], "", [], "", "", "",
            "", "",                        # lower/upper fmax bound
            ["vivado"],                    # analysis-tools already rendered
            [], [], "8", [], "300", [], [],
            [], [],
            [],                            # sim-selection store ids
            None,                          # jobs-config-saved-selection still None
            "?type=analyze&tool=vivado", "/run_jobs", odatix_settings,
        )
        assert className is _dash.no_update
        assert tooltip is _dash.no_update
        assert store is _dash.no_update


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
        jobs_config._prepare_check_data = None
        return jobs_config

    def test_valid_selection_is_checked(self, jobs_config_module, example_workspace):
        jobs_config_module._run_check_workflow_settings(
            "odatix_userconfig/workflow_settings.yml",
            "odatix_userconfig/workflows",
            "work/workflows",
            False,
            True,
            False,
            300,
            4,
        )
        assert jobs_config_module._prepare_status == {"status": "checked", "error": None}
        assert jobs_config_module._prepare_check_data is not None
        # check_settings() returns a 7-tuple: instances, prepare_job, job_list,
        # exit_when_done, log_size_limit, nb_jobs, plan
        assert len(jobs_config_module._prepare_check_data) == 7
        workflow_instances = jobs_config_module._prepare_check_data[0]
        assert len(workflow_instances) > 0

    def test_missing_settings_file_is_reported_as_error(self, jobs_config_module, in_tmp_dir):
        jobs_config_module._run_check_workflow_settings(
            "nonexistent_workflow_settings.yml",
            "workflows",
            "work/workflows",
            False,
            True,
            False,
            300,
            4,
        )
        # check_settings() calls sys.exit(-1) on a missing/invalid file; this
        # must be turned into a normal "error" status, not crash the thread.
        assert jobs_config_module._prepare_status["status"] == "error"
        assert jobs_config_module._prepare_check_data is None

    def test_prepare_dispatches_to_run_workflow(self, jobs_config_module, example_workspace, monkeypatch):
        jobs_config_module._run_check_workflow_settings(
            "odatix_userconfig/workflow_settings.yml",
            "odatix_userconfig/workflows",
            "work/workflows",
            False,
            True,
            False,
            300,
            4,
        )
        assert jobs_config_module._prepare_status["status"] == "checked"

        called = {}

        def fake_prepare_workflows(**kwargs):
            called.update(kwargs)
            return "fake-parallel-jobs"

        monkeypatch.setattr(jobs_config_module.run_workflow, "prepare_workflows", fake_prepare_workflows)
        jobs_config_module._prepare_synth_type = "workflow"
        jobs_config_module._run_prepare_synthesis()

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
        result = workflow_editor_module.update_wf_task_cards(
            new_click=1,
            duplicate_clicks=[],
            delete_clicks=[],
            cards=[],
            task_names=[], task_dependencies=[], task_commands=[], task_paths=[], task_platforms=[],
        )
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
    def page(self, tmp_path, monkeypatch):
        # dash.register_page (called at page-module import) requires an app
        dash.Dash(__name__, use_pages=True, pages_folder="")
        import odatix.gui.pages.choose_eda_tool as choose_eda_tool
        import odatix.lib.eda_tools as eda_tools
        from odatix.lib.settings import OdatixSettings

        # Keep the page on the built-in tools whatever the workspace holds, and
        # on the "unix" flow declarations whatever the platform.
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
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

    def test_a_tool_with_nothing_to_choose_is_a_single_link(self, page):
        # Genus has a single one shot flow: its whole card is the link.
        links = self.links(page, "custom_freq_synthesis", className="odx-tool-card")
        assert "/run_jobs?type=custom_freq_synthesis&tool=genus&flow=synthesis" in links

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
        jobs_config._prepare_check_data = None
        return jobs_config

    def test_custom_freq_passes_the_last_step_to_the_runner(self, jobs_config_module, monkeypatch):
        called = {}

        def fake_check_settings(settings_file, arch_path, tool, flow, until_step, rerun_from_step, *args, **kwargs):
            called.update(
                tool=tool, flow=flow, until_step=until_step, rerun_from_step=rerun_from_step
            )
            return ()

        monkeypatch.setattr(
            jobs_config_module.run_range_synthesis, "check_settings", fake_check_settings
        )
        jobs_config_module._run_check_custom_freq_settings(
            "settings.yml", "architectures", "vivado", "staged", "pnr",
            "work", "targets", False, True, False, 300, 4, False,
        )
        assert called == {
            "tool": "vivado", "flow": "staged", "until_step": "pnr",
            # Re-running a completed step stays a command line only option.
            "rerun_from_step": None,
        }

    def test_fmax_passes_the_last_step_to_the_runner(self, jobs_config_module, monkeypatch):
        called = {}

        def fake_check_settings(settings_file, arch_path, tool, flow, until_step, rerun_from_step, *args, **kwargs):
            called.update(until_step=until_step, rerun_from_step=rerun_from_step)
            return ()

        monkeypatch.setattr(
            jobs_config_module.run_fmax_synthesis, "check_settings", fake_check_settings
        )
        jobs_config_module._run_check_fmax_settings(
            "settings.yml", "architectures", "vivado", "standard", None,
            "work", "targets", False, True, False, 300, 4, True, False,
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
        sections, heading, _title, baseline = jobs_config_module.update_param_domains(
            "?type=simulation", "/run_jobs", self._settings()
        )
        assert heading == "Simulations"
        assert len(sections) == len(jobs_config_module._run_context("?type=simulation", self._settings())["instances"])
        # The example settings file enables TB_Example_Counter_GHDL only.
        assert "TB_Example_Counter_GHDL" in baseline["simulations"]
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
        assert sim_editor_module.build_tasks_list([], [], [], [], []) == []

    def test_settings_round_trip(self, sim_editor_module, example_workspace):
        from odatix.workspace.simulations import SimulationCollection

        simulations = SimulationCollection(None, "odatix_userconfig/simulations")
        simulation = simulations["TB_Example_Counter_GHDL"]
        settings = sim_editor_module.normalize_simulation_settings(simulation.settings.to_dict())
        assert settings["use_parameters"] is True
        assert settings["param_target_file"] == "tb/tb_counter.vhdl"

        settings["tasks"] = [{"name": "main", "commands": ["echo hello"]}]
        simulation.update(settings)
        reloaded = sim_editor_module.normalize_simulation_settings(
            simulations["TB_Example_Counter_GHDL"].reload().settings.to_dict()
        )
        assert reloaded == settings


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
