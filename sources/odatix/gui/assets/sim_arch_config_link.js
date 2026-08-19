// Link of the "parameter domains" button of a simulation architecture card.
// Served as an asset rather than inlined in the index so the function is always
// resolvable by name, whatever the state of the page the browser holds.
window.dash_clientside = window.dash_clientside || {};
window.dash_clientside.odatix_sim = Object.assign({}, window.dash_clientside.odatix_sim, {
  archConfigLinks: function (archNames, search) {
    var params = new URLSearchParams(search || "");
    var simulation = params.get("sim") || params.get("simulation") || "";
    var base = "color-button icon-button tooltip bottom auto delay";
    var linkStyle = {textDecoration: "none"};
    var hrefs = [], styles = [], classes = [], tooltips = [];
    (archNames || []).forEach(function (archName) {
      var architecture = (archName || "").trim();
      if (!simulation || !architecture) {
        // The button stays in place so the head does not jump, but a link back
        // to the current page makes clicking it a no-op.
        hrefs.push(window.location.pathname + (search || ""));
        styles.push(Object.assign({cursor: "default"}, linkStyle));
        classes.push(base + " disabled");
        tooltips.push("Pick an architecture to edit what this simulation substitutes for it");
      } else {
        hrefs.push(
          "/config_editor?sim=" + encodeURIComponent(simulation) +
          "&arch=" + encodeURIComponent(architecture)
        );
        styles.push(linkStyle);
        classes.push(base + " default");
        tooltips.push('Edit the parameter domains this simulation substitutes for "' + architecture + '"');
      }
    });
    return [hrefs, styles, classes, tooltips];
  },
});
