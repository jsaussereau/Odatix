// Link of the "edit configurations" button of a simulation parameter domain.
// Served as an asset rather than inlined in the index so the function is always
// resolvable by name, whatever the state of the page the browser holds.
window.dash_clientside = window.dash_clientside || {};
window.dash_clientside.odatix_sim = Object.assign({}, window.dash_clientside.odatix_sim, {
  domainConfigLinks: function (paramDirs, search) {
    var params = new URLSearchParams(search || "");
    var simulation = params.get("sim") || params.get("simulation") || "";
    var base = "color-button icon-button icon-only tooltip bottom auto delay";
    var linkStyle = {textDecoration: "none", marginBottom: "4px"};
    var hrefs = [], styles = [], classes = [], tooltips = [];
    (paramDirs || []).forEach(function (paramDir) {
      var directory = (paramDir || "").trim();
      if (!simulation || !directory) {
        // The button stays in place so the row does not jump, but a link back to
        // the current page makes clicking it a no-op.
        hrefs.push(window.location.pathname + (search || ""));
        styles.push(Object.assign({cursor: "default"}, linkStyle));
        classes.push(base + " disabled");
        tooltips.push("Set a parameter directory for this domain to edit its configurations");
      } else {
        hrefs.push(
          "/config_editor?sim=" + encodeURIComponent(simulation) +
          "&domain=" + encodeURIComponent(directory)
        );
        styles.push(linkStyle);
        classes.push(base + " default");
        tooltips.push('Edit the configurations of "' + directory + '"');
      }
    });
    return [hrefs, styles, classes, tooltips];
  },
});
