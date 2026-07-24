(function () {
  function applyIndeterminate(span) {
    if (!span) return;
    var raw = span.textContent || "[]";
    var values = [];
    try {
      values = JSON.parse(raw) || [];
    } catch (e) {
      values = [];
    }
    var set = new Set(values.map(String));
    var container = span.parentElement || span;
    var inputs = container.querySelectorAll("input[type='checkbox']");
    inputs.forEach(function (input) {
      var val = String(input.value || "");
      input.indeterminate = set.has(val);
    });
  }

  function scan() {
    var spans = document.querySelectorAll(".domain-config-intermediate");
    spans.forEach(applyIndeterminate);
  }

  // Periodic scan handles dynamic Dash updates.
  setInterval(scan, 500);
  if (document.readyState === "complete" || document.readyState === "interactive") {
    scan();
  } else {
    document.addEventListener("DOMContentLoaded", scan);
  }
})();
