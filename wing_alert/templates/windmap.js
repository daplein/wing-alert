/* Wind maps drawn in the browser from the day's forecast and the coastline.
   Same layout as the PNGs (FR-3.1 to FR-3.6): sizes are in points, as in matplotlib,
   at 100 dpi (1 pt = 100/72 px). */
(function () {
  "use strict";
  var PT = 100 / 72;
  var COLOURS = { light: "#80868b", good: "#2e9e4f", strong: "#f08c00", wild: "#d62828" };
  // Grey and orange text need a darker shade than the arrows to read on land (FR-3.2).
  var TEXT_COLOURS = { light: "#5f6368", good: "#2e9e4f", strong: "#d97700", wild: "#d62828" };
  var ARROW_OFFSET = 22, ARROW_HALF = 14, LABEL_GAP = 7, ARROW_SPACING = 30;
  var SEA = "#7fb8df", SHALLOWS = "#b9dcf0", LAND = "#e3e8cf", SHORE = "#4f6f80";
  var INK = "#1f2933", FRAME = "#7d95a5", NOTE = "#4f6f80";
  // matplotlib's font; Verdana is the same design but a little wider, so it's condensed a touch.
  var FONT = "DejaVu Sans, Verdana, sans-serif", SPACING = "-0.025em";
  // Wicklow Harbour to Arklow; Seapoint is 40 km north, so it gets an inset (FR-3.1).
  var WICKLOW = { lon: [-6.37, -5.95], lat: [52.76, 53.01], sea: [1, 0] };
  var DUBLIN_BAY = { lon: [-6.2, -6.06], lat: [53.27, 53.333], sea: [0, 1] };
  var INSET_BOX = [0.02, 0.74, 0.30, 0.24];  // axes fraction, from the bottom left
  var WIDTH = 545, PAD = 8, MAP_WIDTH = 529;  // the PNG: 529 px map, 8 px margin
  var FOOTER = [
    "kn mean/gust · arrow = where the wind blows to · grey <10, green 10–20, orange 20–30, red 30+",
    "Forecast: Open-Meteo · Coastline © OpenStreetMap contributors"
  ];

  function band(knots) {
    return knots < 10 ? "light" : knots < 20 ? "good" : knots < 30 ? "strong" : "wild";
  }

  function aspect(extent) {
    var middle = (extent.lat[0] + extent.lat[1]) / 2;
    return 1 / Math.cos(middle * Math.PI / 180);
  }

  /* The map's box shrunk to the coast's true shape and centred in it, like set_aspect. */
  function fit(extent, box) {
    var ratio = (extent.lat[1] - extent.lat[0]) * aspect(extent) / (extent.lon[1] - extent.lon[0]);
    var w = Math.min(box.w, box.h / ratio), h = w * ratio;
    return { x: box.x + (box.w - w) / 2, y: box.y + (box.h - h) / 2, w: w, h: h, extent: extent };
  }

  function project(frame, lon, lat) {
    var e = frame.extent;
    return [
      frame.x + (lon - e.lon[0]) / (e.lon[1] - e.lon[0]) * frame.w,
      frame.y + (e.lat[1] - lat) / (e.lat[1] - e.lat[0]) * frame.h
    ];
  }

  function path(frame, points, close) {
    var d = points.map(function (p, i) {
      var xy = project(frame, p[0], p[1]);
      return (i ? "L" : "M") + xy[0].toFixed(1) + " " + xy[1].toFixed(1);
    }).join("");
    return close ? d + "Z" : d;
  }

  function base(frame, coast, id) {
    var lines = coast.lines.map(function (l) { return path(frame, l, false); }).join("");
    var land = coast.land.map(function (l) { return path(frame, l, true); }).join("");
    var rect = 'x="' + frame.x + '" y="' + frame.y + '" width="' + frame.w + '" height="' + frame.h + '"';
    return '<clipPath id="' + id + '"><rect ' + rect + '/></clipPath>' +
      '<g clip-path="url(#' + id + ')"><rect ' + rect + ' fill="' + SEA + '"/>' +
      // Shallows under the land, so only the sea side shows (FR-3.6).
      '<path d="' + lines + '" fill="none" stroke="' + SHALLOWS + '" stroke-width="' + 9 * PT +
      '" stroke-linejoin="round" stroke-linecap="round"/>' +
      '<path d="' + land + '" fill="' + LAND + '"/>' +
      '<path d="' + lines + '" fill="none" stroke="' + SHORE + '" stroke-width="' + 0.8 * PT + '"/></g>';
  }

  function frameRect(frame, colour, width) {
    return '<rect x="' + frame.x + '" y="' + frame.y + '" width="' + frame.w + '" height="' + frame.h +
      '" fill="none" stroke="' + colour + '" stroke-width="' + width * PT + '"/>';
  }

  /* Shifts that keep neighbours at least `spacing` apart, each group centred where it was. */
  function spread(positions, spacing) {
    var order = positions.map(function (_, i) { return i; })
      .sort(function (a, b) { return positions[a] - positions[b]; });
    var shifts = positions.map(function () { return 0; }), groups = [];
    order.forEach(function (i) {
      var last = groups[groups.length - 1];
      if (last && positions[i] - positions[last[last.length - 1]] < spacing) last.push(i);
      else groups.push([i]);
    });
    groups.forEach(function (group) {
      var middle = group.reduce(function (s, i) { return s + positions[i]; }, 0) / group.length;
      group.forEach(function (i, rank) {
        shifts[i] = middle + (rank - (group.length - 1) / 2) * spacing - positions[i];
      });
    });
    return shifts;
  }

  function contains(extent, spot) {
    return extent.lat[0] <= spot.lat && spot.lat <= extent.lat[1] &&
      extent.lon[0] <= spot.lon && spot.lon <= extent.lon[1];
  }

  function spots(frame, data, hour) {
    var shown = data.spots.filter(function (s) { return contains(frame.extent, s) && s.at[hour]; });
    var dots = shown.map(function (s) { return project(frame, s.lon, s.lat); });
    // Along the coast in points: up for an east-facing coast, right for a north-facing one.
    var along = dots.map(function (d) { return frame.extent.sea[0] ? -d[1] / PT : d[0] / PT; });
    var nudges = spread(along, ARROW_SPACING);
    return shown.map(function (s, i) {
      var reading = s.at[hour];
      return arrow(frame.extent, dots[i], reading, nudges[i]) + dot(dots[i]) +
        label(frame.extent, dots[i], s, reading);
    }).join("");
  }

  function dot(xy) {
    return '<circle cx="' + xy[0] + '" cy="' + xy[1] + '" r="' + 3 * PT + '" fill="white" stroke="' +
      INK + '" stroke-width="' + 1.5 * PT + '"/>';
  }

  /* Points where the wind blows to, just out at sea, clear of the dot and the label (FR-3.2). */
  function arrow(extent, xy, reading, nudge) {
    var to = (reading.direction + 180) % 360 * Math.PI / 180;
    var east = extent.sea[0], north = extent.sea[1];
    var cx = xy[0] + (east * ARROW_OFFSET + north * nudge) * PT;
    var cy = xy[1] - (north * ARROW_OFFSET + east * nudge) * PT;
    var ux = Math.sin(to), uy = -Math.cos(to);
    var half = (ARROW_HALF - 2) * PT, head = 6.4 * PT, wing = 3.2 * PT;  // 2 pt shrink at each end
    var tip = [cx + ux * half, cy + uy * half], back = [tip[0] - ux * head, tip[1] - uy * head];
    var colour = COLOURS[band(reading.knots)], width = 2.8 * PT;
    return '<line x1="' + (cx - ux * half) + '" y1="' + (cy - uy * half) + '" x2="' + back[0] +
      '" y2="' + back[1] + '" stroke="' + colour + '" stroke-width="' + width + '"/>' +
      '<path d="M' + tip + "L" + (back[0] - uy * wing) + " " + (back[1] + ux * wing) + "L" +
      (back[0] + uy * wing) + " " + (back[1] - ux * wing) + 'Z" fill="' + colour + '" stroke="' +
      colour + '" stroke-width="' + width + '" stroke-linejoin="miter"/>';
  }

  function windText(reading) {
    var text = reading.wind + "/" + reading.gust;
    return reading.tide ? text + " · " + reading.tide : text;
  }

  function halo(size, extra) {
    return ' font-size="' + size * PT + '" paint-order="stroke" stroke="white" stroke-width="' +
      3 * PT + '" stroke-linejoin="round"' + (extra || "");
  }

  /* Numbers next to the dot on the land side, away from the arrow; the name beyond them. */
  function label(extent, xy, spot, reading) {
    var colour = TEXT_COLOURS[band(reading.knots)];
    var numbers = '<tspan fill="' + colour + '" font-weight="bold" font-size="' + 12 * PT + '"';
    if (extent.sea[0]) {
      return '<text x="' + (xy[0] - LABEL_GAP * PT) + '" y="' + xy[1] + '" text-anchor="end"' +
        ' dominant-baseline="central"' + halo(11.5) + '><tspan fill="' + INK + '">' +
        escape(spot.name) + '</tspan>' + numbers + ' dx="' + 4 * PT + '">' + windText(reading) +
        "</tspan></text>";
    }
    var top = xy[1] + LABEL_GAP * PT;
    return '<text x="' + xy[0] + '" y="' + top + '" text-anchor="middle" dominant-baseline="hanging"' +
      halo(12) + '>' + numbers + '>' + windText(reading) + '</tspan></text>' +
      '<text x="' + xy[0] + '" y="' + (top + 16 * PT) + '" text-anchor="middle"' +
      ' dominant-baseline="hanging" fill="' + INK + '"' + halo(11.5) + '>' + escape(spot.name) + "</text>";
  }

  function escape(text) {
    return text.replace(/&/g, "&amp;").replace(/</g, "&lt;");
  }

  /* A "Dublin Bay" tab tucked in the top-left corner and the distance under the box. */
  function insetNotes(frame) {
    var inside = (2.5 + 1.5 / 2) * PT, pad = 2.5 * PT;
    return '<rect class="tab" x="' + (frame.x + inside - pad) + '" y="' + (frame.y + inside - pad) +
      '" height="' + (9.5 * 1.17 * PT + 2 * pad) + '" fill="' + FRAME + '"/>' +
      '<text class="tab" x="' + (frame.x + inside) + '" y="' + (frame.y + inside) +
      '" dominant-baseline="hanging" font-size="' + 9.5 * PT + '" font-weight="bold" fill="white">' +
      "Dublin Bay</text>" +
      '<text x="' + frame.x + '" y="' + (frame.y + frame.h + 4 * PT) + '" dominant-baseline="hanging"' +
      ' font-size="' + 9 * PT + '" fill="' + NOTE + '">↑ 40 km north</text>';
  }

  function insetBox(main) {
    var b = INSET_BOX;
    return { x: main.x + b[0] * main.w, y: main.y + (1 - b[1] - b[3]) * main.h, w: b[2] * main.w, h: b[3] * main.h };
  }

  function texts(data, hour, main, height) {
    var footer = FOOTER.map(function (line, i) {
      return '<text x="' + WIDTH / 2 + '" y="' + (main.y + main.h * 1.012 + (i + 0.85) * 7 * 1.2 * PT) +
        '" text-anchor="middle" font-size="' + 7 * PT + '" fill="#555">' + escape(line) + "</text>";
    }).join("");
    return '<text x="' + WIDTH / 2 + '" y="' + (main.y - 6 * PT - 4) + '" text-anchor="middle"' +
      ' font-size="' + 15 * PT + '" font-weight="bold" fill="' + INK + '">' + data.title + " · " +
      hour + ":00</text>" + footer;
  }

  function render(data, hour, coast, prefix) {
    var top = PAD + 15 * PT * 0.76 + 6 * PT + 4;  // cap height of the title, then its 6 pt pad
    var main = fit(WICKLOW, { x: (WIDTH - MAP_WIDTH) / 2, y: top, w: MAP_WIDTH, h: 10000 });
    main.y = top;
    var inset = fit(DUBLIN_BAY, insetBox(main));
    var height = Math.ceil(main.y + main.h * 1.012 + 2 * 7 * 1.2 * PT + PAD);
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + WIDTH + " " + height +
      '" font-family="' + FONT + '" letter-spacing="' + SPACING + '"><rect width="100%" height="100%" fill="white"/>' +
      base(main, coast, prefix + "main-" + hour) + spots(main, data, hour) + frameRect(main, "#8aa3b5", 1) +
      base(inset, coast, prefix + "inset-" + hour) + spots(inset, data, hour) + frameRect(inset, FRAME, 1.5) +
      insetNotes(inset) + texts(data, hour, main, height) + "</svg>";
  }

  /* The tab's width depends on the font; a canvas measures it even while the map is hidden. */
  function sizeTab(holder) {
    var rect = holder.querySelector("rect.tab");
    var context = document.createElement("canvas").getContext("2d");
    context.font = "bold " + 9.5 * PT + "px " + FONT;
    rect.setAttribute("width", context.measureText("Dublin Bay").width + 5 * PT);
  }

  /* On a wide screen a click opens the map large, with the hours one key or button apart;
     past the day's first or last hour it goes on to the day before or after, opening that
     page's large map (FR-9.7). A phone already pinch-zooms the sharp SVG. */
  function enlarger(data, coast, days) {
    var dialog = document.createElement("dialog"), hours = data.hours, shown = 0;
    dialog.className = "map-zoom";
    dialog.tabIndex = -1;  // takes the focus itself, so no button lights up on opening
    dialog.innerHTML = '<div class="zoom-bar"><button type="button" class="zoom-step" data-step="-1"' +
      ' aria-label="Earlier hour">‹</button><span class="zoom-hours"></span><button type="button"' +
      ' class="zoom-step" data-step="1" aria-label="Later hour">›</button><button type="button"' +
      ' class="zoom-close" aria-label="Close">×</button></div><div class="zoom-map"></div>';
    dialog.querySelector(".zoom-hours").innerHTML = hours.map(function (h) {
      return '<button type="button" data-hour="' + h + '">' + h + ":00</button>";
    }).join("");
    function show(index) {
      if (index < 0 || index >= hours.length) return otherDay(index < 0);
      shown = index;
      var holder = dialog.querySelector(".zoom-map");
      holder.innerHTML = render(data, hours[shown], coast, "zoom-");
      sizeTab(holder);
      dialog.querySelectorAll(".zoom-hours button").forEach(function (b, i) {
        b.classList.toggle("on", i === shown);
      });
    }
    dialog.addEventListener("click", function (event) {
      var button = event.target.closest("button");
      if (event.target === dialog || (button && button.classList.contains("zoom-close"))) dialog.close();
      else if (button && button.dataset.step) show(shown + Number(button.dataset.step));
      else if (button && button.dataset.hour) show(hours.indexOf(button.dataset.hour));
    });
    dialog.addEventListener("keydown", function (event) {
      if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        show(shown + (event.key === "ArrowLeft" ? -1 : 1));
        event.preventDefault();
      }
    });
    function otherDay(earlier) {
      var page = earlier ? days.previous : days.next;
      if (page) location.href = page + (earlier ? "#map-last" : "#map-first");
    }
    document.body.appendChild(dialog);
    return function open(hour) { show(hours.indexOf(hour)); dialog.showModal(); dialog.focus(); };
  }

  /* The map a step from the day before or after asked for, if any. */
  function askedFor(hours) {
    if (location.hash === "#map-first") return hours[0];
    if (location.hash === "#map-last") return hours[hours.length - 1];
    return null;
  }

  var WIDE = window.matchMedia("(min-width: 900px)");
  var script = document.currentScript;
  var data = JSON.parse(document.getElementById("map-data").textContent);
  fetch(script.dataset.coast).then(function (r) { return r.json(); }).then(function (coast) {
    var open = enlarger(data, coast, document.querySelector(".maps").dataset);
    document.querySelectorAll(".windmap").forEach(function (holder) {
      holder.innerHTML = render(data, holder.dataset.hour, coast, "");
      sizeTab(holder);
      holder.addEventListener("click", function () { if (WIDE.matches) open(holder.dataset.hour); });
    });
    var hour = askedFor(data.hours);
    if (hour && WIDE.matches) open(hour);
  });
})();
