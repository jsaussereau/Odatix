"""Capture the documentation screenshots of future_docs from a running Odatix.

Start the two apps first, from the workspace root:

    python run_odatix_explorer.py -B -N -p 8060
    python run_odatix_gui.py      -B -N -p 8061

then:

    python capture.py <output_dir> [shot ...]

With no shot names, every shot is captured.
"""
import sys, time
from playwright.sync_api import sync_playwright

OUT = sys.argv[1].rstrip("/")
ONLY = sys.argv[2:] or None
XP = "http://127.0.0.1:8060"
GUI = "http://127.0.0.1:8061"


def go(pg, url, wait=8):
    pg.goto(url, wait_until="networkidle", timeout=60000)
    time.sleep(wait)


def sources(pg, wanted):
    """Set the Data-source checklist to exactly `wanted`."""
    labels = pg.locator("#xp-source-select label")
    for i in range(labels.count()):
        lb = labels.nth(i)
        box = lb.locator("input")
        if (lb.inner_text().strip() in wanted) != box.is_checked():
            box.click()
            time.sleep(0.5)
    time.sleep(3)


def tab(pg, name):
    pg.click(f"#xp-tab-btn-{name}")
    time.sleep(1.5)


def filter_set(pg, dimension, wanted):
    """Restrict a filter dimension to exactly `wanted` (Filters tab must be open)."""
    sel = "[id='{\"dim\":\"%s\",\"type\":\"xp-filter\"}'] label" % dimension
    labels = pg.locator(sel)
    for i in range(labels.count()):
        lb = labels.nth(i)
        # The label may carry a marker glyph on its own line before the value.
        name = lb.inner_text().strip().splitlines()[-1].strip()
        box = lb.locator("input")
        if (name in wanted) != box.is_checked():
            box.click()
            time.sleep(0.4)
    time.sleep(2)


def dd(pg, ident, value, verify=True):
    """Set a Dash dropdown by typing its visible option label."""
    pg.click(f"#{ident} .Select-control")
    time.sleep(0.5)
    pg.keyboard.type(value, delay=40)
    time.sleep(0.8)
    pg.keyboard.press("Enter")
    time.sleep(2)
    if verify:
        # A label matching no option leaves the dropdown untouched, which would
        # silently produce a figure of the wrong metric.
        got = pg.locator(f"#{ident} .Select-value-label").first.inner_text().strip()
        assert got == value, f"#{ident}: asked for {value!r}, got {got!r}"


def dd_multi(pg, ident, values):
    """Replace the whole value list of a multi dropdown."""
    pg.click(f"#{ident} .Select-clear-zone")
    time.sleep(1.5)
    for value in values:
        # Chips accumulate, so the single-value check does not apply here.
        dd(pg, ident, value, verify=False)
    chips = [c.strip() for c in pg.locator(f"#{ident} .Select-value-label").all_inner_texts()]
    assert chips == list(values), f"#{ident}: asked for {values}, got {chips}"


def shot(pg, name, selector=None):
    # Driving the dropdowns scrolls the sidebar; rewind it so every figure shows
    # the panel from the top.
    pg.evaluate("document.querySelectorAll('*').forEach(e => e.scrollTop = 0)")
    time.sleep(0.5)
    path = f"{OUT}/{name}.png"
    (pg.locator(selector) if selector else pg).screenshot(path=path)
    print("wrote", path)


def want(name):
    return ONLY is None or name in ONLY


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1600, "height": 900}, device_scale_factor=2)
        wide = b.new_page(viewport={"width": 1920, "height": 1000}, device_scale_factor=2)

        if want("fmax-lines"):
            pg = page
            go(pg, f"{XP}/explorer/lines")
            sources(pg, {"vivado_asterisc"})
            tab(pg, "filters")
            filter_set(pg, "Target", {"xc7a100t-csg324-1"})
            filter_set(pg, "MEM", {"1024I_1024D"})
            filter_set(pg, "Baseline", {"I"})
            tab(pg, "data")
            dd(pg, "xp-axis-y", "Fmax")
            dd(pg, "xp-axis-x", "main")
            dd(pg, "xp-dissociate-by", "Mul")
            dd(pg, "xp-color-by", "Mul")
            shot(pg, "fmax-lines")
            shot(pg, "chart-lines", "#xp-graph-area")

        # A coherent subset of the vivado example results. Only Example_ALU_sv is
        # kept: the other designs in that result file carry broken *_percent
        # values (63400 instead of a percentage), which makes the overview grid
        # look like a rendering bug rather than a documentation figure.
        def vivado_subset(pg, color_by="Target"):
            sources(pg, {"vivado"})
            tab(pg, "filters")
            filter_set(pg, "Architecture", {"Example_ALU_sv"})
            filter_set(pg, "Configuration",
                       {"04bits", "08bits", "16bits", "24bits", "32bits", "48bits", "64bits"})
            tab(pg, "data")
            if color_by:
                dd(pg, "xp-color-by", color_by)

        if want("explorer-overview"):
            pg = wide
            go(pg, f"{XP}/explorer/overview")
            vivado_subset(pg)
            shot(pg, "explorer-overview")

        if want("explorer-charts"):
            pg = page
            # Frequency is the default Y metric but it is constant here, so each
            # tile picks a metric that actually varies with the configuration.
            go(pg, f"{XP}/explorer/lines")
            vivado_subset(pg)
            dd(pg, "xp-axis-y", "Total Power")
            shot(pg, "chart-lines", "#xp-graph-area")

            go(pg, f"{XP}/explorer/columns")
            vivado_subset(pg)
            dd(pg, "xp-axis-y", "LUT count")
            shot(pg, "chart-columns", "#xp-graph-area")

            go(pg, f"{XP}/explorer/radar")
            vivado_subset(pg)
            dd(pg, "xp-axis-y", "LUT+Reg count")
            shot(pg, "chart-radar", "#xp-graph-area")

            go(pg, f"{XP}/explorer/scatter")
            vivado_subset(pg)
            dd(pg, "xp-axis-x", "LUT count")
            dd(pg, "xp-axis-y", "Total Power")
            shot(pg, "chart-scatter", "#xp-graph-area")

        if want("synthesis-results"):
            pg = wide
            go(pg, f"{XP}/explorer/table")
            vivado_subset(pg, color_by=None)
            dd_multi(pg, "xp-table-columns", [
                "Architecture", "Configuration", "Target", "Frequency (MHz)",
                "LUT count", "Reg count", "LUT+Reg count", "Total Power (W)",
            ])
            shot(pg, "synthesis-results")

        if want("pnr"):
            pg = page
            go(pg, f"{XP}/explorer/scatter")
            sources(pg, {"openlane"})
            dd(pg, "xp-axis-x", "Cell Area")
            dd(pg, "xp-axis-y", "Fmax")
            dd(pg, "xp-color-by", "Configuration")
            shot(pg, "pnr")

        if want("explorer-home"):
            go(page, f"{XP}/explorer")
            shot(page, "explorer-home")

        if want("gui-home"):
            go(page, f"{GUI}/", wait=5)
            shot(page, "gui-home")

        if want("job-monitor"):
            # Needs a job actually running; capture it during a real campaign.
            go(page, f"{GUI}/monitor", wait=6)
            shot(page, "job-monitor")

        b.close()


if __name__ == "__main__":
    main()
