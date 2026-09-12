(function () {
  "use strict";

  function getRoot(rootId) {
    return document.getElementById(rootId);
  }

  function detectWebGL() {
    try {
      var canvas = document.createElement("canvas");
      var gl =
        canvas.getContext("webgl2") ||
        canvas.getContext("webgl") ||
        canvas.getContext("experimental-webgl");
      if (!gl) return { ok: false, renderer: "unavailable" };
      var info = null;
      try {
        var dbg = gl.getExtension("WEBGL_debug_renderer_info");
        if (dbg) info = gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL);
      } catch (e) {
        info = null;
      }
      return { ok: true, renderer: info || "GPU info unavailable" };
    } catch (e) {
      return { ok: false, renderer: "error" };
    }
  }

  function showFallback(rootId, reason) {
    var root = getRoot(rootId);
    if (!root) return;
    var canvas = root.querySelector("canvas");
    if (canvas) canvas.style.display = "none";
    var toolbar = root.querySelector(".fw-cam-toolbar");
    if (toolbar) toolbar.style.display = "none";
    var panel = root.querySelector(".fw-diag-panel");
    if (panel) {
      panel.style.display = "flex";
      var reasonEl = panel.querySelector(".fw-diag-reason");
      if (reasonEl) reasonEl.textContent = reason || "Unknown rendering error";
    }
    var hud = root.querySelector(".fw-hud");
    if (hud) hud.style.display = "none";
  }

  function setHud(rootId, text) {
    var root = getRoot(rootId);
    if (!root) return;
    var hud = root.querySelector(".fw-hud");
    if (hud) hud.textContent = text;
  }

  function makeTextSprite(THREE, text, opts) {
    opts = opts || {};
    var fontSize = opts.fontSize || 42;
    var color = opts.color || "#eef1fb";
    var padding = 16;
    var canvas = document.createElement("canvas");
    var ctx = canvas.getContext("2d");
    ctx.font = "700 " + fontSize + "px Inter, Segoe UI, Arial, sans-serif";
    var textWidth = ctx.measureText(text).width;
    canvas.width = Math.ceil(textWidth + padding * 2);
    canvas.height = Math.ceil(fontSize * 1.6);
    ctx.font = "700 " + fontSize + "px Inter, Segoe UI, Arial, sans-serif";
    ctx.textBaseline = "middle";
    ctx.shadowColor = "rgba(0,0,0,0.85)";
    ctx.shadowBlur = 8;
    ctx.fillStyle = color;
    ctx.fillText(text, padding, canvas.height / 2);
    var texture = new THREE.CanvasTexture(canvas);
    texture.needsUpdate = true;
    var material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false });
    var sprite = new THREE.Sprite(material);
    var scale = opts.scale || 0.012;
    sprite.scale.set(canvas.width * scale, canvas.height * scale, 1);
    return sprite;
  }

  function makeRadialTexture(colorInner, colorOuter, size) {
    size = size || 128;
    var canvas = document.createElement("canvas");
    canvas.width = canvas.height = size;
    var ctx = canvas.getContext("2d");
    var g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
    g.addColorStop(0, colorInner);
    g.addColorStop(1, colorOuter);
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, size, size);
    return canvas;
  }

  // -------------------------------------------------------------------
  // CameraRig — genuine full free-orbit spherical camera controller.
  // Left-drag = orbit (full 360 horizontal, near-full vertical).
  // Right-drag / Shift+drag = pan target. Wheel / pinch = smooth zoom.
  // Named view presets, fit, reset, auto-rotate all animate via damping,
  // never snap. update() must be called once per animation frame.
  // -------------------------------------------------------------------
  function CameraRig(THREE, camera, canvas, opts) {
    opts = opts || {};
    var target = new THREE.Vector3(opts.targetX || 0, opts.targetY || 0, opts.targetZ || 0);
    var theta = opts.theta !== undefined ? opts.theta : Math.PI / 4;
    var phi = opts.phi !== undefined ? opts.phi : Math.PI / 3;
    var radius = opts.radius || 16;
    var thetaT = theta, phiT = phi, radiusT = radius;
    var targetT = target.clone();
    var minRadius = opts.minRadius || radius * 0.22;
    var maxRadius = opts.maxRadius || radius * 3.2;
    var autoRotate = false;
    var dragging = false;
    var panning = false;
    var lastX = 0, lastY = 0;
    var touchPinchDist = null;
    var defaults = { theta: theta, phi: phi, radius: radius, target: target.clone() };

    function clampPhi(p) {
      return Math.max(0.045, Math.min(Math.PI - 0.045, p));
    }
    function wrapDelta(a, b) {
      var d = (b - a) % (Math.PI * 2);
      if (d > Math.PI) d -= Math.PI * 2;
      if (d < -Math.PI) d += Math.PI * 2;
      return d;
    }

    function apply() {
      var sinPhi = Math.sin(phi);
      camera.position.set(
        target.x + radius * sinPhi * Math.sin(theta),
        target.y + radius * Math.cos(phi),
        target.z + radius * sinPhi * Math.cos(theta)
      );
      camera.lookAt(target);
    }
    apply();

    function update() {
      if (autoRotate && !dragging && !panning) {
        thetaT += 0.0028;
      }
      theta += wrapDelta(theta, thetaT) * 0.14;
      phi += (phiT - phi) * 0.14;
      radius += (radiusT - radius) * 0.14;
      target.lerp(targetT, 0.14);
      apply();
    }

    canvas.addEventListener("contextmenu", function (e) {
      e.preventDefault();
    });
    canvas.addEventListener("pointerdown", function (e) {
      if (e.button === 2 || e.shiftKey) {
        panning = true;
      } else {
        dragging = true;
      }
      lastX = e.clientX;
      lastY = e.clientY;
      canvas.style.cursor = panning ? "move" : "grabbing";
      try {
        canvas.setPointerCapture(e.pointerId);
      } catch (err) {
        /* ignore */
      }
    });
    canvas.addEventListener("pointerup", function () {
      dragging = false;
      panning = false;
      canvas.style.cursor = "grab";
    });
    canvas.addEventListener("pointerleave", function () {
      dragging = false;
      panning = false;
    });
    canvas.addEventListener("pointermove", function (e) {
      if (!dragging && !panning) return;
      var dx = e.clientX - lastX;
      var dy = e.clientY - lastY;
      lastX = e.clientX;
      lastY = e.clientY;
      if (dragging) {
        thetaT -= dx * 0.0072;
        phiT = clampPhi(phiT - dy * 0.0072);
      } else if (panning) {
        var right = new THREE.Vector3(Math.cos(theta), 0, -Math.sin(theta));
        var up = new THREE.Vector3(0, 1, 0);
        var panScale = radius * 0.0016;
        targetT.addScaledVector(right, -dx * panScale);
        targetT.addScaledVector(up, dy * panScale);
      }
    });
    canvas.addEventListener(
      "wheel",
      function (e) {
        e.preventDefault();
        radiusT *= 1 + e.deltaY * 0.0011;
        radiusT = Math.max(minRadius, Math.min(maxRadius, radiusT));
      },
      { passive: false }
    );

    function touchDist(t) {
      var dx = t[0].clientX - t[1].clientX;
      var dy = t[0].clientY - t[1].clientY;
      return Math.sqrt(dx * dx + dy * dy);
    }
    canvas.addEventListener(
      "touchstart",
      function (e) {
        if (e.touches.length === 1) {
          dragging = true;
          panning = false;
          lastX = e.touches[0].clientX;
          lastY = e.touches[0].clientY;
        } else if (e.touches.length === 2) {
          dragging = false;
          panning = false;
          touchPinchDist = touchDist(e.touches);
        }
      },
      { passive: true }
    );
    canvas.addEventListener(
      "touchmove",
      function (e) {
        if (e.touches.length === 1 && dragging) {
          var dx = e.touches[0].clientX - lastX;
          var dy = e.touches[0].clientY - lastY;
          lastX = e.touches[0].clientX;
          lastY = e.touches[0].clientY;
          thetaT -= dx * 0.0072;
          phiT = clampPhi(phiT - dy * 0.0072);
        } else if (e.touches.length === 2 && touchPinchDist !== null) {
          var d = touchDist(e.touches);
          var scale = touchPinchDist / d;
          radiusT = Math.max(minRadius, Math.min(maxRadius, radiusT * scale));
          touchPinchDist = d;
        }
      },
      { passive: true }
    );
    canvas.addEventListener("touchend", function () {
      dragging = false;
      panning = false;
      touchPinchDist = null;
    });

    var VIEWS = {
      front: { theta: 0, phi: Math.PI / 2 },
      back: { theta: Math.PI, phi: Math.PI / 2 },
      left: { theta: -Math.PI / 2, phi: Math.PI / 2 },
      right: { theta: Math.PI / 2, phi: Math.PI / 2 },
      top: { phi: 0.12 },
      bottom: { phi: Math.PI - 0.12 },
      iso: { theta: Math.PI / 4, phi: Math.PI / 3 },
    };

    return {
      update: update,
      setView: function (name) {
        autoRotate = false;
        var v = VIEWS[name];
        if (!v) return;
        if (v.theta !== undefined) thetaT = v.theta;
        if (v.phi !== undefined) phiT = clampPhi(v.phi);
      },
      zoomIn: function () {
        radiusT = Math.max(minRadius, radiusT * 0.72);
      },
      zoomOut: function () {
        radiusT = Math.min(maxRadius, radiusT * 1.35);
      },
      fit: function () {
        thetaT = defaults.theta;
        phiT = defaults.phi;
        radiusT = defaults.radius * 1.1;
        targetT.copy(defaults.target);
      },
      reset: function () {
        thetaT = defaults.theta;
        phiT = defaults.phi;
        radiusT = defaults.radius;
        targetT.copy(defaults.target);
        autoRotate = false;
      },
      toggleAutoRotate: function () {
        autoRotate = !autoRotate;
        return autoRotate;
      },
      isAutoRotate: function () {
        return autoRotate;
      },
      getTarget: function () {
        return target;
      },
      focusOn: function (pos, dist) {
        targetT.set(pos.x, pos.y, pos.z);
        if (dist) radiusT = Math.max(minRadius, Math.min(maxRadius, dist));
      },
      isInteracting: function () {
        return dragging || panning;
      },
    };
  }

  // -------------------------------------------------------------------
  // Floating glass camera toolbar
  // -------------------------------------------------------------------
  var TOOLBAR_BUTTONS = [
    { action: "reset", label: "\u21bb Reset", group: 1 },
    { action: "fit", label: "\u2318 Fit", group: 1 },
    { action: "zoomin", label: "\uff0b Zoom In", group: 1 },
    { action: "zoomout", label: "\u2212 Zoom Out", group: 1 },
    { action: "front", label: "Front", group: 2 },
    { action: "back", label: "Back", group: 2 },
    { action: "left", label: "Left", group: 2 },
    { action: "right", label: "Right", group: 2 },
    { action: "top", label: "Top", group: 2 },
    { action: "bottom", label: "Bottom", group: 2 },
    { action: "iso", label: "Isometric", group: 2 },
    { action: "autorotate", label: "\u25b6 Auto Rotate", group: 3 },
  ];

  function buildToolbar(rootId, rig) {
    var root = getRoot(rootId);
    if (!root) return;
    var bar = document.createElement("div");
    bar.className = "fw-cam-toolbar";
    var html = "";
    var lastGroup = null;
    for (var i = 0; i < TOOLBAR_BUTTONS.length; i++) {
      var b = TOOLBAR_BUTTONS[i];
      if (lastGroup !== null && b.group !== lastGroup) html += '<span class="fw-cam-sep"></span>';
      lastGroup = b.group;
      html += '<button type="button" class="fw-cam-btn" data-action="' + b.action + '">' + b.label + "</button>";
    }
    bar.innerHTML = html;
    root.appendChild(bar);
    bar.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-action]");
      if (!btn) return;
      var action = btn.getAttribute("data-action");
      if (action === "zoomin") rig.zoomIn();
      else if (action === "zoomout") rig.zoomOut();
      else if (action === "fit") rig.fit();
      else if (action === "reset") {
        rig.reset();
        var card = root.querySelector(".fw-detail-card");
        if (card) card.style.display = "none";
      } else if (action === "autorotate") {
        var on = rig.toggleAutoRotate();
        btn.classList.toggle("active", on);
      } else {
        rig.setView(action);
      }
    });
  }

  // -------------------------------------------------------------------
  // Picking: hover highlight + click focus + detail card
  // Register pickable objects with: { object, meta } where meta has
  // { title, rows:[[label,value]...], observation, source }.
  // For InstancedMesh, register once with meta = function(instanceId).
  // -------------------------------------------------------------------
  function setupPicking(rootId, THREE, camera, canvas, pickables, rig, opts) {
    opts = opts || {};
    var raycaster = new THREE.Raycaster();
    var mouse = new THREE.Vector2();
    var root = getRoot(rootId);
    var hoveredEntry = null;
    var hoveredInstanceId = -1;

    function metaFor(entry, instanceId) {
      if (typeof entry.meta === "function") return entry.meta(instanceId);
      return entry.meta;
    }

    function pick(clientX, clientY) {
      var rect = canvas.getBoundingClientRect();
      mouse.x = ((clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(mouse, camera);
      var objects = pickables.map(function (p) {
        return p.object;
      });
      var hits = raycaster.intersectObjects(objects, false);
      if (!hits.length) return null;
      var hit = hits[0];
      var entry = null;
      for (var i = 0; i < pickables.length; i++) {
        if (pickables[i].object === hit.object) {
          entry = pickables[i];
          break;
        }
      }
      if (!entry) return null;
      return { entry: entry, instanceId: hit.instanceId !== undefined ? hit.instanceId : -1, point: hit.point };
    }

    canvas.addEventListener("pointermove", function (e) {
      if (rig.isInteracting()) return;
      var hit = pick(e.clientX, e.clientY);
      canvas.style.cursor = hit ? "pointer" : "grab";
      if (hoveredEntry && (!hit || hoveredEntry.entry !== hit.entry || hoveredInstanceId !== hit.instanceId)) {
        if (hoveredEntry.entry.onUnhover) hoveredEntry.entry.onUnhover(hoveredInstanceId);
        hoveredEntry = null;
        hoveredInstanceId = -1;
      }
      if (hit && (!hoveredEntry || hoveredEntry.entry !== hit.entry || hoveredInstanceId !== hit.instanceId)) {
        hoveredEntry = hit;
        hoveredInstanceId = hit.instanceId;
        if (hit.entry.onHover) hit.entry.onHover(hit.instanceId);
      }
      var tip = root.querySelector(".fw-hover-tip");
      if (tip) {
        if (hit) {
          var m = metaFor(hit.entry, hit.instanceId);
          tip.style.display = "block";
          var rect2 = root.getBoundingClientRect();
          tip.style.left = e.clientX - rect2.left + 14 + "px";
          tip.style.top = e.clientY - rect2.top + 12 + "px";
          tip.textContent = m ? m.title : "";
        } else {
          tip.style.display = "none";
        }
      }
    });

    canvas.addEventListener("click", function (e) {
      var hit = pick(e.clientX, e.clientY);
      if (!hit) return;
      var m = metaFor(hit.entry, hit.instanceId);
      if (!m) return;
      rig.focusOn(hit.point, opts.focusDistance || 6);
      showDetailCard(rootId, m);
    });
  }

  function showDetailCard(rootId, meta) {
    var root = getRoot(rootId);
    if (!root) return;
    var card = root.querySelector(".fw-detail-card");
    if (!card) return;
    var rows = (meta.rows || [])
      .map(function (r) {
        return '<div class="fw-detail-row"><span>' + r[0] + "</span><b>" + r[1] + "</b></div>";
      })
      .join("");
    card.innerHTML =
      '<button type="button" class="fw-detail-close">\u2715</button>' +
      '<div class="fw-detail-title">' +
      (meta.title || "") +
      "</div>" +
      rows +
      (meta.observation ? '<div class="fw-detail-obs">' + meta.observation + "</div>" : "") +
      '<div class="fw-detail-source">Source: ' +
      (meta.source || "claims.csv / fraud_indicators.csv") +
      "</div>";
    card.style.display = "block";
    var closeBtn = card.querySelector(".fw-detail-close");
    if (closeBtn)
      closeBtn.addEventListener("click", function () {
        card.style.display = "none";
      });
  }

  function attachResize(canvas, renderer, camera) {
    var parent = canvas.parentElement;
    function doResize() {
      var w = parent.clientWidth;
      var h = parent.clientHeight;
      if (w < 10 || h < 10) return;
      var pr = Math.min(window.devicePixelRatio || 1, 2);
      renderer.setPixelRatio(pr);
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    }
    doResize();
    if (window.ResizeObserver) {
      var ro = new ResizeObserver(function () {
        doResize();
      });
      ro.observe(parent);
    } else {
      window.addEventListener("resize", doResize);
    }
    return doResize;
  }

  function bootstrapScene(rootId, buildFn, data) {
    var root = getRoot(rootId);
    if (!root) return;
    var status = detectWebGL();
    var webglEl = root.querySelector(".fw-diag-webgl");
    var gpuEl = root.querySelector(".fw-diag-gpu");
    if (webglEl) webglEl.textContent = status.ok ? "AVAILABLE" : "UNAVAILABLE";
    if (gpuEl) gpuEl.textContent = status.renderer;
    if (!status.ok) {
      showFallback(rootId, "WebGL is not available in this browser or GPU context.");
      return;
    }
    try {
      buildFn(rootId, data);
    } catch (err) {
      showFallback(rootId, "Render error \u2014 " + (err && err.message ? err.message : String(err)));
    }
  }

  window.FW = window.FW || {};
  window.FW.detectWebGL = detectWebGL;
  window.FW.showFallback = showFallback;
  window.FW.setHud = setHud;
  window.FW.makeTextSprite = makeTextSprite;
  window.FW.makeRadialTexture = makeRadialTexture;
  window.FW.CameraRig = CameraRig;
  window.FW.buildToolbar = buildToolbar;
  window.FW.setupPicking = setupPicking;
  window.FW.showDetailCard = showDetailCard;
  window.FW.attachResize = attachResize;
  window.FW.bootstrapScene = bootstrapScene;
})();
