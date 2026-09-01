/**********************************************************************\
*                                Odatix                                *
************************************************************************
*
* Copyright (C) 2022 Jonathan Saussereau
*
* This file is part of Odatix.
* Odatix is free software: you can redistribute it and/or modify
* it under the terms of the GNU General Public License as published by
* the Free Software Foundation, either version 3 of the License, or
* (at your option) any later version.
*
* Odatix is distributed in the hope that it will be useful,
* but WITHOUT ANY WARRANTY; without even the implied warranty of
* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
* GNU General Public License for more details.
*
* You should have received a copy of the GNU General Public License
* along with Odatix. If not, see <https://www.gnu.org/licenses/>.
*
*/

/*
 * Background of the "tesseract" theme: a hypercube turning in 4D.
 *
 * The rotation is computed and drawn here rather than pre-rendered, because a
 * sprite sheet can only hold a handful of frames before it gets huge, and the
 * resulting stepping is very visible on a slow, continuous motion. A canvas
 * gives a smooth turn at any screen size, for 32 line segments a frame.
 *
 * The canvas only exists while the theme is on: the class of #theme is watched
 * and the animation loop is torn down as soon as another theme is picked.
 */
(function() {
    "use strict";

    var PERIOD = 44000;      // ms for one full turn
    var SIZE = 0.86;         // fraction of the smallest viewport side
    var D4 = 3.2, D3 = 4.6;  // projection distances, 4D -> 3D -> 2D
    var MARGIN = 0.445;      // half-extent the projection is normalised to

    // the 16 vertices of the hypercube, and the 32 pairs at Hamming distance 1
    var verts = [];
    for (var i = 0; i < 16; i++) {
        verts.push([(i & 1) ? 1 : -1, (i & 2) ? 1 : -1, (i & 4) ? 1 : -1, (i & 8) ? 1 : -1]);
    }
    var edges = [];
    for (var a = 0; a < 16; a++) {
        for (var b = a + 1; b < 16; b++) {
            var diff = 0;
            for (var k = 0; k < 4; k++) {
                if (verts[a][k] !== verts[b][k]) { diff++; }
            }
            if (diff === 1) { edges.push([a, b]); }
        }
    }

    // the two cells and the struts joining them get their own colour
    var CELLS = {
        inner: {color: "155, 107, 255", width: 1.0, alpha: 0.50},
        strut: {color: "255, 78, 205", width: 0.8, alpha: 0.34},
        outer: {color: "53, 230, 255", width: 1.2, alpha: 0.66}
    };
    edges.forEach(function(edge) {
        var wa = verts[edge[0]][3], wb = verts[edge[1]][3];
        edge.push(wa !== wb ? "strut" : (wa > 0 ? "outer" : "inner"));
    });

    function rotate(p, a, b, angle) {
        var c = Math.cos(angle), s = Math.sin(angle);
        var pa = p[a], pb = p[b];
        p[a] = pa * c - pb * s;
        p[b] = pa * s + pb * c;
    }

    function project(vertex, t) {
        var p = vertex.slice();
        rotate(p, 2, 3, t);      // true 4D rotation: ZW plane...
        rotate(p, 0, 3, t);      // ...and XW plane
        rotate(p, 0, 2, 0.62);   // fixed 3D orientation, so the nested cubes stay readable
        rotate(p, 1, 2, 0.38);
        var k4 = D4 / (D4 - p[3]);
        var x = p[0] * k4, y = p[1] * k4, z = p[2] * k4;
        var k3 = D3 / (D3 - z);
        return [x * k3, -y * k3];
    }

    // normalise once over the whole turn, so the hypercube never leaves its box
    var extent = 0;
    for (var f = 0; f < 240; f++) {
        for (var v = 0; v < 16; v++) {
            var pt = project(verts[v], 2 * Math.PI * f / 240);
            extent = Math.max(extent, Math.abs(pt[0]), Math.abs(pt[1]));
        }
    }
    var SCALE = MARGIN / extent;

    var canvas = null, ctx = null, frame = null, side = 0, ratio = 1;

    function resize() {
        var box = Math.min(window.innerWidth, window.innerHeight) * SIZE;
        ratio = window.devicePixelRatio || 1;
        side = Math.round(box);
        canvas.style.width = side + "px";
        canvas.style.height = side + "px";
        canvas.style.marginLeft = canvas.style.marginTop = (-side / 2) + "px";
        canvas.width = Math.round(side * ratio);
        canvas.height = Math.round(side * ratio);
    }

    function draw(now) {
        frame = window.requestAnimationFrame(draw);
        var t = 2 * Math.PI * ((now % PERIOD) / PERIOD);
        var points = verts.map(function(vertex) {
            var pt = project(vertex, t);
            return [pt[0] * SCALE, pt[1] * SCALE];
        });
        var stroke = Math.max(1, side / 320) * ratio;

        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.translate(canvas.width / 2, canvas.height / 2);
        ctx.lineCap = "round";
        ctx.lineJoin = "round";

        // two passes per cell: a wide faint one for the glow, then the line
        [[6, 0.16], [1, 1]].forEach(function(pass) {
            Object.keys(CELLS).forEach(function(name) {
                var cell = CELLS[name];
                ctx.lineWidth = cell.width * stroke * pass[0];
                ctx.strokeStyle = "rgba(" + cell.color + "," + (cell.alpha * pass[1]) + ")";
                ctx.beginPath();
                edges.forEach(function(edge) {
                    if (edge[2] !== name) { return; }
                    var p = points[edge[0]], q = points[edge[1]];
                    ctx.moveTo(p[0] * side * ratio, p[1] * side * ratio);
                    ctx.lineTo(q[0] * side * ratio, q[1] * side * ratio);
                });
                ctx.stroke();
            });
        });
    }

    function start(host) {
        if (canvas) { return; }
        canvas = document.createElement("canvas");
        canvas.id = "tesseract-bg";
        ctx = canvas.getContext("2d");
        host.insertBefore(canvas, host.firstChild);
        resize();
        window.addEventListener("resize", resize);
        if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
            frame = window.requestAnimationFrame(draw);
        } else {
            draw(0);
        }
    }

    function stop() {
        if (!canvas) { return; }
        window.cancelAnimationFrame(frame);
        window.removeEventListener("resize", resize);
        canvas.remove();
        canvas = null;
        ctx = null;
        frame = null;
    }

    function sync() {
        var host = document.getElementById("theme");
        if (host && host.classList.contains("tesseract")) {
            start(host);
        } else {
            stop();
        }
    }

    function watch() {
        var host = document.getElementById("theme");
        if (!host) {
            window.setTimeout(watch, 200);  // Dash has not rendered the layout yet
            return;
        }
        new MutationObserver(sync).observe(host, {attributes: true, attributeFilter: ["class"]});
        sync();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", watch);
    } else {
        watch();
    }
})();
