"""Capture the screenshots of the workshop page "Describe the design, then
synthesize it", by doing what a participant does in odatix-gui.

In an empty directory:

    odatix init -y --cordic
    odatix-gui -B -N -p 8071 -T odatix

then, from the repository root:

    python docs/tools/capture_workshop_gui.py docs/static/images/screenshots/workshop [part]

The parts follow the workshop, each one starting where the previous one left
the workspace:

- "describe" (the default): the workspace holds no My_Cordic_sv yet. It ends by
  starting the synthesis of the nine configurations with Vivado, which keeps
  running after the script is done.
- "simulate": the synthesis is over, and there is no TB_My_Cordic_sv yet.
- "accuracy": the simulation has run, and there is no derived metric yet.
  Odatix Explorer has to be running too: odatix-explorer -B -N -p 8074.
- "dse": the derived metric exists, and the campaign of the finale is in
  odatix_userconfig/dse_campaigns. It runs the exploration to its end
  (DSE_WAIT seconds after the monitor).
"""
import os, sys, time
from playwright.sync_api import sync_playwright

OUT = sys.argv[1].rstrip("/")
GUI = "http://127.0.0.1:%s" % os.environ.get("PORT", "8071")
EXPLORER = "http://127.0.0.1:%s" % os.environ.get("EXPLORER_PORT", "8074")
# START_SYNTHESIS=0 captures the synthesis pages without starting it.
START_SYNTHESIS = os.environ.get("START_SYNTHESIS", "1") != "0"
ARCH = "My_Cordic_sv"


def go(pg, path, wait=8):
    # The tool pages poll the tools: the network is never idle there.
    pg.goto(GUI + path, wait_until="load", timeout=60000)
    time.sleep(wait)


def shot(pg, name, selector=None, full=False):
    path = f"{OUT}/{name}.png"
    if selector:
        pg.locator(selector).first.scroll_into_view_if_needed()
        time.sleep(0.5)
        pg.locator(selector).first.screenshot(path=path)
    else:
        pg.screenshot(path=path, full_page=full)
    print("wrote", path)


def save_all(page):
    return "[id='{\"action\":\"save-all\",\"page\":\"%s\"}']" % page


def domain_uuid(pg, title):
    for field in pg.locator("input[id*='domain-title-input']").all():
        if field.input_value() == title:
            return field.get_attribute("id").split('"domain_uuid":"')[1].split('"')[0]
    raise LookupError(title)


def describe(pg):
    # The architecture
    go(pg, "/architectures", 3)
    shot(pg, "gui-architectures")
    pg.click("text=Create new architecture")
    time.sleep(5)
    pg.fill("#arch-title", ARCH)
    pg.keyboard.press("Tab")
    pg.fill("#rtl_path", "examples/cordic_sv")
    pg.keyboard.press("Tab")
    pg.fill("#top_level_file", "cordic.sv")
    pg.keyboard.press("Tab")
    time.sleep(1)
    for field in ("top_level_module", "clock_signal", "reset_signal"):
        pg.click(f"#{field}-autodetect")
        time.sleep(2)
    pg.fill("#fixed_freq_synthesis_list", "100")
    pg.keyboard.press("Tab")
    time.sleep(1)
    pg.evaluate("window.scrollTo(0, 0)")
    shot(pg, "gui-arch-settings", full=True)
    pg.click(save_all("/arch_editor"))
    time.sleep(3)

    # Its parameter domains
    pg.click("#button-open-config-editor")
    time.sleep(6)
    pg.click("button[id*='__main__'][id*='cfg-detect-params']")
    time.sleep(4)
    shot(pg, "gui-detect", "[id*='cfg-detect-panel']")
    pg.click("text=Create domains")
    time.sleep(6)
    pg.reload(wait_until="load")
    time.sleep(6)
    for name, values in (("WIDTH", "4, 8, 12"), ("ITERATIONS", "12, 16, 24")):
        uuid = domain_uuid(pg, name)
        pg.locator(f"button[id*='{uuid}'][id*='cfg-variable-collapse']").first.click()
        time.sleep(1.5)
        field = pg.locator(f"input[id*='{uuid}'][id*='cfg-variable-field-list']")
        field.fill(values)
        field.press("Tab")
        time.sleep(3)
        if name == "WIDTH":
            # From the title of the domain down to its configurations.
            top = pg.locator(f"input[id*='{uuid}'][id*='domain-title-input']").bounding_box()
            bottom = pg.locator(f"input[id*='{uuid}'][id*='cfg-variable-field-list']").bounding_box()
            pg.evaluate(f"window.scrollTo(0, {top['y']} + window.scrollY - 60)")
            time.sleep(1)
            top = pg.locator(f"input[id*='{uuid}'][id*='domain-title-input']").bounding_box()
            bottom = pg.locator(f"input[id*='{uuid}'][id*='cfg-variable-field-list']").bounding_box()
            y = max(top["y"] - 40, 0)
            pg.screenshot(path=f"{OUT}/gui-domain-width.png",
                          clip={"x": 0, "y": y, "width": 1600, "height": min(bottom["y"] + 260 - y, 900 - y)})
            print("wrote", f"{OUT}/gui-domain-width.png")
        pg.locator(f"button[id*='{uuid}'][id*='cfg-save-rules']").click()
        time.sleep(4)

    # The analysis
    go(pg, "/run_jobs?type=analyze&tool=verilator&flow=lint", 10)
    # Only Verilator: the analysis of the common track is the ten-second one.
    box = pg.locator("label:has-text('Vivado') input").first
    if box.is_checked():
        box.evaluate("e => e.click()")
        time.sleep(2)
    pg.locator(".jobs-arch-headline .checklist-switch label").first.click()
    time.sleep(4)
    shot(pg, "gui-analysis-select", full=True)
    pg.click("[id='{\"action\":\"run-jobs\",\"page\":\"/run_jobs\"}']")
    time.sleep(5)
    shot(pg, "gui-analysis-confirm")
    pg.click("#run-confirm-btn")
    time.sleep(25)
    shot(pg, "gui-analysis-monitor")

    # The synthesis
    go(pg, "/choose_eda_tool?type=custom_freq_synthesis", 10)
    shot(pg, "gui-synthesis-tools")
    go(pg, "/run_jobs?type=custom_freq_synthesis&tool=vivado&flow=standard&until=synthesis", 10)
    pg.fill("#nb_jobs", "4")
    pg.keyboard.press("Tab")
    pg.locator(".jobs-arch-headline .checklist-switch label").first.click()
    time.sleep(4)
    shot(pg, "gui-synthesis-select", full=True)
    pg.click("[id='{\"action\":\"run-jobs\",\"page\":\"/run_jobs\"}']")
    time.sleep(8)
    if not START_SYNTHESIS:
        return
    pg.click("#run-confirm-btn")
    time.sleep(60)
    shot(pg, "gui-synthesis-monitor")


def by_name(name, kind):
    return "[id*='\"name\":\"%s\"'][id*='\"type\":\"%s\"']" % (name, kind)


def newest(pg, kind, prefix):
    """The name of the card added last, under its provisional name."""
    names = pg.evaluate(
        "kind => [...document.querySelectorAll('input')].map(e => e.id)"
        ".filter(i => i.includes(kind)).map(i => JSON.parse(i).name)", kind)
    return [name for name in names if name.startswith(prefix)][-1]


def simulate(pg):
    # The simulation, its testbench and its template
    go(pg, "/architectures", 3)
    pg.click("text=Create new simulation")
    time.sleep(6)
    pg.fill("#sim-title", "TB_My_Cordic_sv")
    pg.keyboard.press("Tab")
    pg.fill("#sim-testbench-top", "tb_cordic")
    pg.keyboard.press("Tab")
    pg.fill("#sim-testbench-files", "examples/cordic_tb/tb_cordic.sv")
    pg.keyboard.press("Tab")
    pg.fill("#sim-testbench-parameters", "WIDTH: ${WIDTH}\nITERATIONS: ${ITERATIONS}")
    pg.keyboard.press("Tab")
    time.sleep(2)
    # What it runs on: the only architecture of the workspace is offered first
    pg.click("text=Add an architecture")
    time.sleep(4)
    pg.evaluate("window.scrollTo(0, 0)")
    pg.screenshot(path=f"{OUT}/gui-sim-settings.png", clip={"x": 0, "y": 0, "width": 1600, "height": 850})
    print("wrote", f"{OUT}/gui-sim-settings.png")
    pg.click(save_all("/sim_editor"))
    time.sleep(4)

    # Its metrics
    pg.click("#button-open-sim-metric-editor")
    time.sleep(6)
    for title, key, unit, fmt in (("snr", "snr_db", "dB", "%.2f"), ("enob", "enob", "bits", "%.2f"),
                                  ("latency", "latency_cycles", "cycles", "%.0f")):
        pg.click("text=Add new metric")
        time.sleep(3)
        name = newest(pg, "metric-title", "metric")
        pg.locator(by_name(name, "metric-title")).fill(title)
        pg.keyboard.press("Tab")
        time.sleep(2)
        pg.locator(by_name(name, "metric-type") + " .Select-control").click()
        time.sleep(0.5)
        pg.keyboard.type("YAML", delay=40)
        pg.keyboard.press("Enter")
        time.sleep(2)
        pg.locator(by_name(name, "metric-field-file")).fill("results.yml")
        pg.keyboard.press("Tab")
        pg.locator(by_name(name, "metric-field-key")).fill(key)
        pg.keyboard.press("Tab")
        pg.locator("button" + by_name(name, "metric-more-fields")).click()
        time.sleep(1)
        pg.locator(by_name(name, "metric-field-unit")).fill(unit)
        pg.keyboard.press("Tab")
        pg.locator(by_name(name, "metric-field-format")).fill(fmt)
        pg.keyboard.press("Tab")
        time.sleep(2)
        if title == "snr":
            shot(pg, "gui-sim-metric", by_name(name, "metric-card"))
    pg.click(save_all("/metric_editor"))
    time.sleep(4)

    # The run
    go(pg, "/run_jobs?type=simulation", 10)
    card = pg.locator(".jobs-arch-card").first
    card.locator(".checklist-switch label").first.click()
    time.sleep(3)
    card.locator(".checklist-switch label").nth(1).click()
    time.sleep(4)
    pg.locator("#jobs-settings-toggle").click()
    time.sleep(2)
    pg.evaluate("window.scrollTo(0, 0)")
    shot(pg, "gui-sim-select", full=True)
    pg.click("[id='{\"action\":\"run-jobs\",\"page\":\"/run_jobs\"}']")
    time.sleep(6)
    if pg.locator("#run-confirm-btn").is_visible():
        pg.click("#run-confirm-btn")
    time.sleep(45)
    shot(pg, "gui-sim-monitor")


def accuracy(pg):
    go(pg, "/derived_metrics", 8)
    for title, unit in (("snr", "dB"), ("enob", "bits")):
        pg.click("text=Add new derived metric")
        time.sleep(3)
        name = newest(pg, "dm-title", "new_metric")
        pg.locator(by_name(name, "dm-title")).fill(title)
        pg.keyboard.press("Tab")
        time.sleep(2)
        pg.locator("button" + by_name(name, "dm-more-fields")).click()
        time.sleep(1)
        pg.locator(by_name(name, "dm-field-unit")).fill(unit)
        pg.keyboard.press("Tab")
        time.sleep(2)
    pg.click(save_all("/derived_metrics"))
    time.sleep(4)
    pg.click("#dm-apply")
    time.sleep(8)
    pg.evaluate("window.scrollTo(0, 0)")
    shot(pg, "gui-derived-metrics", full=True)

    # The chart, in Odatix Explorer
    pg.goto(EXPLORER + "/explorer/scatter", wait_until="networkidle", timeout=60000)
    time.sleep(8)
    for ident, value in (("xp-axis-x", "LUT count"), ("xp-axis-y", "snr"), ("xp-color-by", "WIDTH")):
        pg.click(f"#{ident} .Select-control")
        time.sleep(0.5)
        pg.keyboard.type(value, delay=40)
        time.sleep(0.8)
        pg.keyboard.press("Enter")
        time.sleep(2)
    pg.evaluate("document.querySelectorAll('*').forEach(e => e.scrollTop = 0)")
    time.sleep(2)
    shot(pg, "explorer-snr-lut")


def dse(pg):
    # The campaign file of the finale is in dse_campaigns already, and no
    # campaign is selected in dse_settings.yml.
    campaign = "cordic_accuracy_area"
    go(pg, "/dse", 8)
    shot(pg, "gui-dse-campaigns", full=True)
    pg.locator("a" + by_name(campaign, "dse-campaign-edit")).first.click()
    time.sleep(8)
    shot(pg, "gui-dse-campaign", full=True)

    go(pg, "/dse", 8)
    pg.locator(by_name(campaign, "dse-campaign-enable") + " label").first.click()
    time.sleep(2)
    pg.fill("#dse-nb-jobs", "4")
    pg.keyboard.press("Tab")
    time.sleep(2)
    pg.click("#dse-save-all")
    time.sleep(3)
    pg.click("#dse-run")
    time.sleep(20)
    shot(pg, "gui-dse-check", "#dse-run-popup > div")
    if not START_SYNTHESIS:
        return
    pg.click("#dse-run-start")
    time.sleep(90)
    shot(pg, "gui-dse-monitor")

    # Odatix Explorer, once the exploration is over
    time.sleep(int(os.environ.get("DSE_WAIT", "240")))
    go(pg, "/explorer/dse?campaign=" + campaign, 15)
    shot(pg, "gui-dse-front", full=True)


def main():
    part = sys.argv[2] if len(sys.argv) > 2 else "describe"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={"width": 1600, "height": 900}, device_scale_factor=1.5)
        {"describe": describe, "simulate": simulate, "accuracy": accuracy, "dse": dse}[part](pg)
        browser.close()


if __name__ == "__main__":
    main()
