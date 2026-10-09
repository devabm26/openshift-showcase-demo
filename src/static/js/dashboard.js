/*
 * Thoughts Dashboard — external JavaScript
 *
 * No inline JS used in templates (CSP compliance, web_security.spec REQ-6).
 * All data is read from the DOM / data-* attributes — never from raw URL params.
 *
 * This file is intentionally minimal: the dashboard is server-rendered.
 */

"use strict";

document.addEventListener("DOMContentLoaded", function () {
  // Highlight rows with a net_rating that is strongly negative
  var rows = document.querySelectorAll(".thoughts-table tbody tr");
  rows.forEach(function (row) {
    var netCell = row.querySelector(".col-number.negative");
    if (netCell) {
      var val = parseInt(netCell.textContent.trim(), 10);
      if (!isNaN(val) && val < -5) {
        row.style.opacity = "0.75";
      }
    }
  });
});
