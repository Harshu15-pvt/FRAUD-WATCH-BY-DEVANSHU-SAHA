(function () {
  "use strict";

  var CATEGORY_COLOR = {
    normal: 0x22d3ee,
    review: 0xf5c451,
    fraud: 0xff9f5b,
    confirmed: 0xff5c72,
    cleared: 0x3ddc97,
  };
  var CATEGORY_LABEL = {
    normal: "NORMAL",
    review: "UNDER REVIEW",
    fraud: "FLAGGED",
    confirmed: "CONFIRMED FRAUD",
    cleared: "CLEARED",
  };

  function terrainHeight(x, z) {
    return (
      1.1 * Math.sin(x / 6.2) * Math.cos(z / 6.2) +
      0.6 * Math.sin(x / 3.1 + 1.0) * Math.sin(z / 4.0)
    );
  }

  function buildTerrainMesh(THREE, size, segments, colorNear, colorFar) {
    var geo = new THREE.PlaneGeometry(size, size, segments, segments);
    geo.rotateX(-Math.PI / 2);
    var pos = geo.attributes.position;
    var colors = new Float32Array(pos.count * 3);
    var cNear = new THREE.Color(colorNear);
    var cFar = new THREE.Color(colorFar);
    for (var i = 0; i < pos.count; i++) {
      var x = pos.getX(i);
      var z = pos.getZ(i);
      var h = terrainHeight(x, z);
      pos.setY(i, h);
      var t = Math.min(1, Math.max(0, (h + 1.5) / 3));
      var c = cNear.clone().lerp(cFar, t);
      colors[i * 3] = c.r;
      colors[i * 3 + 1] = c.g;
      colors[i * 3 + 2] = c.b;
    }
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    geo.computeVertexNormals();
    var mat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.85, metalness: 0.1, flatShading: true });
    return new THREE.Mesh(geo, mat);
  }

  function addLighting(THREE, scene) {
    scene.add(new THREE.AmbientLight(0x8fa3ff, 0.55));
    var dir = new THREE.DirectionalLight(0xbfe0ff, 1.15);
    dir.position.set(14, 20, 10);
    scene.add(dir);
    var rim = new THREE.PointLight(0x8b6bf7, 0.65, 60);
    rim.position.set(-16, 10, -14);
    scene.add(rim);
    var rim2 = new THREE.PointLight(0xff9f5b, 0.35, 50);
    rim2.position.set(14, 6, 16);
    scene.add(rim2);
  }

  function addStarBackdrop(THREE, scene, count, spread) {
    var geo = new THREE.BufferGeometry();
    var pos = new Float32Array(count * 3);
    for (var s = 0; s < count; s++) {
      pos[s * 3] = (Math.random() - 0.5) * spread;
      pos[s * 3 + 1] = Math.random() * spread * 0.4 + spread * 0.05;
      pos[s * 3 + 2] = (Math.random() - 0.5) * spread;
    }
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    var mat = new THREE.PointsMaterial({ color: 0xbfe0ff, size: 0.09, transparent: true, opacity: 0.6 });
    scene.add(new THREE.Points(geo, mat));
  }

  function addBuilding(THREE, scene, x, z, w, h, d, color, opts) {
    opts = opts || {};
    var group = new THREE.Group();
    var mat = new THREE.MeshStandardMaterial({
      color: color, roughness: 0.5, metalness: 0.28,
      emissive: opts.emissive || 0x000000, emissiveIntensity: opts.emissiveIntensity || 0,
    });
    var mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
    mesh.position.set(x, h / 2 + terrainHeight(x, z), z);
    group.add(mesh);
    if (opts.cross) {
      var crossMat = new THREE.MeshBasicMaterial({ color: 0xff5c72 });
      var vBar = new THREE.Mesh(new THREE.BoxGeometry(w * 0.12, h * 0.4, 0.05), crossMat);
      var hBar = new THREE.Mesh(new THREE.BoxGeometry(w * 0.4, h * 0.12, 0.05), crossMat);
      vBar.position.set(x, h * 0.75 + terrainHeight(x, z), z + d / 2 + 0.03);
      hBar.position.copy(vBar.position);
      group.add(vBar, hBar);
    }
    scene.add(group);
    return { group: group, mesh: mesh, baseEmissive: opts.emissiveIntensity || 0 };
  }

  function addTree(THREE, scene, x, z, scale) {
    scale = scale || 1;
    var group = new THREE.Group();
    var trunk = new THREE.Mesh(
      new THREE.CylinderGeometry(0.05 * scale, 0.07 * scale, 0.5 * scale, 6),
      new THREE.MeshStandardMaterial({ color: 0x6b4a2f, roughness: 0.9 })
    );
    var baseY = terrainHeight(x, z);
    trunk.position.set(x, baseY + 0.25 * scale, z);
    var canopyMat = new THREE.MeshStandardMaterial({ color: 0x1fae82, roughness: 0.8, flatShading: true });
    var c1 = new THREE.Mesh(new THREE.ConeGeometry(0.42 * scale, 0.85 * scale, 7), canopyMat);
    c1.position.set(x, baseY + 0.85 * scale, z);
    var c2 = new THREE.Mesh(new THREE.ConeGeometry(0.3 * scale, 0.6 * scale, 7), canopyMat);
    c2.position.set(x, baseY + 1.3 * scale, z);
    group.add(trunk, c1, c2);
    scene.add(group);
  }

  function addMountain(THREE, scene, x, z, h, color) {
    var mat = new THREE.MeshStandardMaterial({ color: color, roughness: 0.95, flatShading: true });
    var cone = new THREE.Mesh(new THREE.ConeGeometry(3.4, h, 5), mat);
    cone.position.set(x, h / 2 + terrainHeight(x, z), z);
    cone.rotation.y = (x + z) * 0.3;
    scene.add(cone);
  }

  function fmtMoney(v) {
    if (v === null || v === undefined) return "\u2014";
    return "\u20b9" + Math.round(v).toLocaleString("en-IN");
  }

  // ---------------------------------------------------------------------
  // Standard scene chrome: toolbar CSS hooks live in app.py HTML, this
  // just wires the rig + toolbar + picking + HUD/FPS to a built scene.
  // ---------------------------------------------------------------------
  function finalizeScene(rootId, THREE, camera, canvas, renderer, scene, rig, pickables, onFrame, objectCount) {
    window.FW.buildToolbar(rootId, rig);
    if (pickables && pickables.length) {
      window.FW.setupPicking(rootId, THREE, camera, canvas, pickables, rig, { focusDistance: 6 });
    }
    window.FW.attachResize(canvas, renderer, camera);

    var clock = new THREE.Clock();
    var frameCount = 0;
    var fpsAccum = 0;
    var fpsLast = 0;
    function animate() {
      requestAnimationFrame(animate);
      var dt = clock.getDelta();
      fpsAccum += dt;
      frameCount++;
      if (onFrame) onFrame(clock.getElapsedTime(), dt);
      rig.update();
      renderer.render(scene, camera);
      if (fpsAccum >= 0.5) {
        fpsLast = Math.round(frameCount / fpsAccum);
        frameCount = 0;
        fpsAccum = 0;
        window.FW.setHud(
          rootId,
          "RENDERER: WebGL \u00b7 OBJECTS: " + objectCount + " \u00b7 " + fpsLast + " FPS \u00b7 LIVE"
        );
      }
    }
    animate();
  }

  function baseSetup(rootId, fov, near, far) {
    var THREE = window.THREE;
    var root = document.getElementById(rootId);
    var canvas = root.querySelector("canvas");
    var scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x060a18, 0.014);
    var camera = new THREE.PerspectiveCamera(fov, 2, near, far);
    var renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true });
    renderer.setClearColor(0x000000, 0);
    addLighting(THREE, scene);
    return { THREE: THREE, root: root, canvas: canvas, scene: scene, camera: camera, renderer: renderer };
  }

  // ---------------------------------------------------------------------
  // SCENE 1 — Fraud Intelligence City / Risk Terrain
  // ---------------------------------------------------------------------
  function buildCityScene(rootId, data) {
    var ctx = baseSetup(rootId, 45, 0.1, 200);
    var THREE = ctx.THREE, scene = ctx.scene, camera = ctx.camera, canvas = ctx.canvas, renderer = ctx.renderer;

    var terrain = buildTerrainMesh(THREE, 34, 42, 0x0d1a3d, 0x2a3f7a);
    scene.add(terrain);
    addStarBackdrop(THREE, scene, 260, 90);

    var pickables = [];
    var objectCount = 1;

    if (!data.terrainOnly) {
      var hq = addBuilding(THREE, scene, 0, -5.5, 2.6, 6.0, 2.6, 0x3a63d8);
      pickables.push({
        object: hq.mesh,
        meta: { title: "FraudWatch HQ", rows: [["Role", "Command building"], ["Represents", "Central intake & triage"]], source: "Scene landmark" },
      });
      var hosp = addBuilding(THREE, scene, 5.4, -3.2, 2.3, 2.8, 2.1, 0xeef1fb, { cross: true });
      pickables.push({ object: hosp.mesh, meta: { title: "Regional Hospital", rows: [["Role", "Health-claim landmark"]], source: "Scene landmark" } });
      var proc = addBuilding(THREE, scene, 4.2, 4.0, 2.0, 2.5, 1.8, 0x8b6bf7, { emissive: 0x8b6bf7, emissiveIntensity: 0.15 });
      pickables.push({ object: proc.mesh, meta: { title: "Claims Processing Center", rows: [["Role", "Investigation & review"]], source: "Scene landmark" } });
      addBuilding(THREE, scene, -5.6, -2.4, 1.9, 1.5, 1.7, 0xd9a066);
      objectCount += 4;

      var treeSpots = [[-8, 5], [-9, 2], [7, 6], [8, -6], [-3, 7], [3, -8], [9, 3], [-6, 8]];
      for (var t = 0; t < treeSpots.length; t++) addTree(THREE, scene, treeSpots[t][0], treeSpots[t][1], 0.8 + Math.random() * 0.4);
      var mtnSpots = [[-14, -14, 3.4], [-6, -15, 2.6], [7, -15, 3.0], [14, -13, 3.6], [13, 13, 3.0], [-13, 12, 2.8]];
      for (var m = 0; m < mtnSpots.length; m++) addMountain(THREE, scene, mtnSpots[m][0], mtnSpots[m][1], mtnSpots[m][2], 0x1c2444);
      objectCount += treeSpots.length + mtnSpots.length;
    }

    // Claim markers as InstancedMesh (perf), with hover/click picking by instance.
    var claims = data.claims || [];
    var markerBundle = null;
    var hoveredIndex = -1;
    if (claims.length) {
      var geo = new THREE.OctahedronGeometry(0.18, 0);
      var mat = new THREE.MeshStandardMaterial({ roughness: 0.3, metalness: 0.4, emissiveIntensity: 0.9 });
      var mesh = new THREE.InstancedMesh(geo, mat, claims.length);
      mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(claims.length * 3), 3);
      var dummy = new THREE.Object3D();
      var color = new THREE.Color();
      var baseY = [], phase = [];
      for (var i = 0; i < claims.length; i++) {
        var c = claims[i];
        var y = terrainHeight(c.x, c.z) + 0.35 + (c.risk === "fraud" || c.risk === "confirmed" ? 0.4 : 0);
        baseY.push(y);
        phase.push(i * 0.37);
        dummy.position.set(c.x, y, c.z);
        dummy.scale.setScalar(0.7 + Math.min(1, c.amountRank || 0.4) * 0.9);
        dummy.updateMatrix();
        mesh.setMatrixAt(i, dummy.matrix);
        color.setHex(CATEGORY_COLOR[c.risk] || CATEGORY_COLOR.normal);
        mesh.setColorAt(i, color);
      }
      mesh.instanceMatrix.needsUpdate = true;
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
      scene.add(mesh);
      markerBundle = { mesh: mesh, claims: claims, baseY: baseY, phase: phase };
      objectCount += claims.length;

      pickables.push({
        object: mesh,
        meta: function (idx) {
          var c = claims[idx];
          if (!c) return null;
          return {
            title: "Claim marker \u00b7 " + CATEGORY_LABEL[c.risk],
            rows: [
              ["Risk category", CATEGORY_LABEL[c.risk]],
              ["Amount percentile", Math.round((c.amountRank || 0) * 100) + "th"],
            ],
            observation: "Colour and elevation encode risk category and indicator score; size encodes claim amount percentile.",
            source: "claims.csv \u00b7 fraud_indicators.csv",
          };
        },
        onHover: function (idx) {
          hoveredIndex = idx;
        },
        onUnhover: function () {
          hoveredIndex = -1;
        },
      });
    }

    var target = new THREE.Vector3(0, 0.6, 0);
    var rig = window.FW.CameraRig(THREE, camera, canvas, {
      radius: data.terrainOnly ? 20 : 16, theta: Math.PI / 4, phi: Math.PI / 3.1,
      minRadius: 4, maxRadius: 46, targetY: 0.6,
    });

    function onFrame(t) {
      if (markerBundle) {
        var dummy = new THREE.Object3D();
        for (var i = 0; i < markerBundle.claims.length; i++) {
          var c = markerBundle.claims[i];
          var pulse = c.risk === "fraud" || c.risk === "confirmed" ? Math.sin(t * 2.4 + markerBundle.phase[i]) * 0.12 : 0;
          dummy.position.set(c.x, markerBundle.baseY[i] + pulse, c.z);
          var baseScale = 0.7 + Math.min(1, c.amountRank || 0.4) * 0.9;
          var hoverBoost = i === hoveredIndex ? 1.5 : 1.0;
          dummy.scale.setScalar(baseScale * hoverBoost * (1 + (c.risk === "fraud" ? 0.15 * Math.sin(t * 2.4 + markerBundle.phase[i]) : 0)));
          dummy.rotation.y = t * 0.6 + markerBundle.phase[i];
          dummy.updateMatrix();
          markerBundle.mesh.setMatrixAt(i, dummy.matrix);
        }
        markerBundle.mesh.instanceMatrix.needsUpdate = true;
      }
      if (data.autoRotate && rig.isAutoRotate() === false) {
        /* auto-rotate is opt-in via toolbar; city defaults to gentle spin only in terrain mode */
      }
    }

    if (data.autoRotate) rig.toggleAutoRotate();

    finalizeScene(rootId, THREE, camera, canvas, renderer, scene, rig, pickables, onFrame, objectCount);
  }

  // ---------------------------------------------------------------------
  // SCENE 2 — Fraud Driver Observatory (towers + pipeline + orbital network)
  // ---------------------------------------------------------------------
  function buildObservatoryScene(rootId, data) {
    var ctx = baseSetup(rootId, 48, 0.1, 300);
    var THREE = ctx.THREE, scene = ctx.scene, camera = ctx.camera, canvas = ctx.canvas, renderer = ctx.renderer;
    addStarBackdrop(THREE, scene, 220, 110);

    var floorGeo = new THREE.PlaneGeometry(70, 30);
    floorGeo.rotateX(-Math.PI / 2);
    scene.add(new THREE.Mesh(floorGeo, new THREE.MeshStandardMaterial({ color: 0x0b1230, roughness: 0.9, transparent: true, opacity: 0.6 })));

    var pickables = [];
    var objectCount = 0;

    // Zone A — fraud towers
    var towerGroup = new THREE.Group();
    towerGroup.position.x = -20;
    var types = data.claimTypes || [];
    var maxCount = Math.max(1, Math.max.apply(null, types.map(function (d) { return d.fraudCount; })));
    for (var i = 0; i < types.length; i++) {
      var d = types[i];
      var h = 0.6 + (d.fraudCount / maxCount) * 6.5;
      var radius = 0.5 + Math.min(1, d.totalCount / (data.maxTypeTotal || 1)) * 0.7;
      var color = new THREE.Color(0x4cc9f0).lerp(new THREE.Color(0xff5c72), Math.min(1, d.fraudRate / 40));
      var mat = new THREE.MeshStandardMaterial({ color: color, roughness: 0.4, metalness: 0.35, emissive: color, emissiveIntensity: 0.25 });
      var mesh = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius * 1.05, h, 10), mat);
      var tx = (i - (types.length - 1) / 2) * 2.6;
      mesh.position.set(tx, h / 2, 0);
      towerGroup.add(mesh);
      objectCount++;
      (function (dLocal, meshLocal, baseColor) {
        pickables.push({
          object: meshLocal,
          meta: {
            title: dLocal.name,
            rows: [
              ["Total claims", dLocal.totalCount.toLocaleString()],
              ["Fraud claims", dLocal.fraudCount.toLocaleString()],
              ["Fraud rate", dLocal.fraudRate.toFixed(2) + "%"],
            ],
            observation: dLocal.fraudRate > data.avgFraudRate
              ? dLocal.name + " sits above the filtered-population average fraud rate (" + data.avgFraudRate.toFixed(1) + "%)."
              : dLocal.name + " sits at or below the filtered-population average fraud rate.",
            source: "claims.csv",
          },
          onHover: function () { meshLocal.material.emissiveIntensity = 0.75; meshLocal.scale.set(1.08, 1.0, 1.08); },
          onUnhover: function () { meshLocal.material.emissiveIntensity = 0.25; meshLocal.scale.set(1, 1, 1); },
        });
      })(d, mesh, color);
      if (d.fraudRate > (data.avgFraudRate || 0)) {
        var ring = new THREE.Mesh(new THREE.TorusGeometry(radius + 0.25, 0.05, 8, 24), new THREE.MeshBasicMaterial({ color: 0xff5c72 }));
        ring.rotation.x = Math.PI / 2;
        ring.position.set(tx, h + 0.15, 0);
        towerGroup.add(ring);
      }
      var label = window.FW.makeTextSprite(THREE, d.name, { color: "#eef1fb", fontSize: 30 });
      label.position.set(tx, h + 0.9, 0);
      towerGroup.add(label);
    }
    towerGroup.add(window.FW.makeTextSprite(THREE, "FRAUD TOWERS \u00b7 CLAIM TYPE", { color: "#4cc9f0", fontSize: 34, scale: 0.014 }).translateY(8.4));
    scene.add(towerGroup);

    // Zone B — review pipeline chambers
    var pipeGroup = new THREE.Group();
    var stages = data.pipeline || [];
    var maxStage = Math.max(1, Math.max.apply(null, stages.map(function (s) { return s.count; })));
    var stageColors = [0xf5c451, 0xff9f5b, 0xff5c72, 0x3ddc97];
    var chamberX = [];
    for (var j = 0; j < stages.length; j++) {
      var s = stages[j];
      var sh = 0.6 + (s.count / maxStage) * 5.5;
      var cmat = new THREE.MeshStandardMaterial({
        color: stageColors[j % stageColors.length], transparent: true, opacity: 0.55, roughness: 0.25, metalness: 0.2,
        emissive: stageColors[j % stageColors.length], emissiveIntensity: 0.4,
      });
      var cyl = new THREE.Mesh(new THREE.CylinderGeometry(1.1, 1.1, sh, 16, 1, true), cmat);
      var sx = j * 3.4;
      cyl.position.set(sx, sh / 2, 0);
      pipeGroup.add(cyl);
      chamberX.push(sx);
      objectCount++;
      (function (sLocal, cylLocal) {
        pickables.push({
          object: cylLocal,
          meta: { title: sLocal.name + " chamber", rows: [["Indicators in stage", sLocal.count.toLocaleString()]], source: "fraud_indicators.csv" },
          onHover: function () { cylLocal.material.opacity = 0.85; },
          onUnhover: function () { cylLocal.material.opacity = 0.55; },
        });
      })(s, cyl);
      var slabel = window.FW.makeTextSprite(THREE, s.name + " \u00b7 " + s.count, { color: "#eef1fb", fontSize: 28 });
      slabel.position.set(sx, sh + 0.8, 0);
      pipeGroup.add(slabel);
    }
    pipeGroup.add(
      window.FW.makeTextSprite(THREE, "REVIEW PIPELINE", { color: "#f5c451", fontSize: 34, scale: 0.014 })
        .translateY(8.4)
        .translateX(chamberX.length ? chamberX[Math.floor(chamberX.length / 2)] : 0)
    );
    scene.add(pipeGroup);

    var flowCount = 40;
    var flowGeo = new THREE.BufferGeometry();
    var flowPos = new Float32Array(flowCount * 3);
    var flowSpan = chamberX.length > 1 ? chamberX[chamberX.length - 1] - chamberX[0] : 10;
    var flowStart = chamberX.length ? chamberX[0] : 0;
    var flowOffsets = [];
    for (var f = 0; f < flowCount; f++) {
      flowOffsets.push(Math.random());
      flowPos[f * 3] = flowStart;
      flowPos[f * 3 + 1] = 0.4 + Math.random() * 1.5;
      flowPos[f * 3 + 2] = (Math.random() - 0.5) * 1.6;
    }
    flowGeo.setAttribute("position", new THREE.BufferAttribute(flowPos, 3));
    var flowPoints = new THREE.Points(flowGeo, new THREE.PointsMaterial({ color: 0xbfe8ff, size: 0.12, transparent: true, opacity: 0.85 }));
    pipeGroup.add(flowPoints);

    // Zone C — orbital indicator network
    var orbitGroup = new THREE.Group();
    orbitGroup.position.x = 20;
    var core = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.9, 1),
      new THREE.MeshStandardMaterial({ color: 0x8b6bf7, emissive: 0x8b6bf7, emissiveIntensity: 0.6, roughness: 0.2, metalness: 0.5 })
    );
    orbitGroup.add(core);
    pickables.push({ object: core, meta: { title: "Fraud Signal Engine", rows: [["Role", "Central aggregation node"]], observation: "Represents the aggregation point for all indicator signal types.", source: "fraud_indicators.csv" } });
    objectCount++;
    orbitGroup.add(window.FW.makeTextSprite(THREE, "FRAUD SIGNAL ENGINE", { color: "#c9bdfc", fontSize: 26 }).translateY(-1.6));
    var indicators = data.indicators || [];
    var maxIndCount = Math.max(1, Math.max.apply(null, indicators.map(function (d) { return d.count; })));
    var orbitNodes = [];
    for (var k = 0; k < indicators.length; k++) {
      var ind = indicators[k];
      var nodeRadius = 0.16 + Math.min(1, ind.count / maxIndCount) * 0.3;
      var stateColor = ind.state === "confirmed" ? 0xff5c72 : ind.state === "flagged" ? 0xff9f5b : 0xf5c451;
      var node = new THREE.Mesh(
        new THREE.SphereGeometry(nodeRadius, 16, 16),
        new THREE.MeshStandardMaterial({ color: stateColor, emissive: stateColor, emissiveIntensity: 0.45, roughness: 0.3 })
      );
      var orbitRadius = 2.6 + (k % 2) * 0.9;
      var lineGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), new THREE.Vector3(orbitRadius, 0, 0)]);
      var line = new THREE.Line(lineGeo, new THREE.LineBasicMaterial({ color: 0x4cc9f0, transparent: true, opacity: 0.35 }));
      orbitGroup.add(line);
      var nlabel = window.FW.makeTextSprite(THREE, ind.name, { color: "#eef1fb", fontSize: 24 });
      orbitNodes.push({ mesh: node, line: line, label: nlabel, radius: orbitRadius, speed: 0.25 + (k % 3) * 0.09, angle: (k / Math.max(1, indicators.length)) * Math.PI * 2, height: (ind.avgScore / 100 - 0.5) * 2.2 });
      orbitGroup.add(node, nlabel);
      objectCount++;
      (function (indLocal, nodeLocal) {
        pickables.push({
          object: nodeLocal,
          meta: {
            title: indLocal.name,
            rows: [["Indicator count", indLocal.count.toLocaleString()], ["Average score", indLocal.avgScore.toFixed(1)], ["Dominant state", indLocal.state.toUpperCase()]],
            observation: "Screening signal \u2014 supports investigation prioritisation, not proof of fraud.",
            source: "fraud_indicators.csv",
          },
          onHover: function () { nodeLocal.material.emissiveIntensity = 0.9; },
          onUnhover: function () { nodeLocal.material.emissiveIntensity = 0.45; },
        });
      })(ind, node);
    }
    scene.add(orbitGroup);

    var rig = window.FW.CameraRig(THREE, camera, canvas, { radius: 30, theta: Math.PI / 2, phi: Math.PI / 2.7, minRadius: 8, maxRadius: 70 });

    function onFrame(t) {
      core.rotation.y = t * 0.4;
      core.rotation.x = t * 0.15;
      for (var n = 0; n < orbitNodes.length; n++) {
        var o = orbitNodes[n];
        var ang = o.angle + t * o.speed;
        var x = Math.cos(ang) * o.radius;
        var z = Math.sin(ang) * o.radius;
        o.mesh.position.set(x, o.height, z);
        o.label.position.set(x, o.height + 0.4, z);
        var pos = o.line.geometry.attributes.position;
        pos.setXYZ(1, x, o.height, z);
        pos.needsUpdate = true;
      }
      var fp = flowPoints.geometry.attributes.position;
      for (var p = 0; p < flowCount; p++) {
        flowOffsets[p] += 0.0028;
        if (flowOffsets[p] > 1) flowOffsets[p] = 0;
        fp.setX(p, flowStart + flowOffsets[p] * flowSpan);
      }
      fp.needsUpdate = true;
    }

    finalizeScene(rootId, THREE, camera, canvas, renderer, scene, rig, pickables, onFrame, objectCount);
  }

  // ---------------------------------------------------------------------
  // SCENE 3 — Analytics Laboratory
  // ---------------------------------------------------------------------
  function buildLabScene(rootId, data) {
    var ctx = baseSetup(rootId, 48, 0.1, 300);
    var THREE = ctx.THREE, scene = ctx.scene, camera = ctx.camera, canvas = ctx.canvas, renderer = ctx.renderer;
    addStarBackdrop(THREE, scene, 200, 100);

    var pickables = [];
    var objectCount = 0;

    var trendGroup = new THREE.Group();
    trendGroup.position.x = -13;
    var trend = data.trend || [];
    var maxFraud = Math.max(1, Math.max.apply(null, trend.map(function (d) { return d.fraud; })));
    var segW = Math.max(4, trend.length * 1.1) / Math.max(1, trend.length);
    for (var i = 0; i < trend.length; i++) {
      var td = trend[i];
      var h = 0.3 + (td.fraud / maxFraud) * 3.4;
      var t01 = td.fraud / maxFraud;
      var color = new THREE.Color(0x1c2c66).lerp(new THREE.Color(0xff5c72), t01);
      var mat = new THREE.MeshStandardMaterial({ color: color, roughness: 0.5, metalness: 0.15, emissive: color, emissiveIntensity: 0.25 });
      var bar = new THREE.Mesh(new THREE.BoxGeometry(segW * 0.72, h, 1.4), mat);
      var bx = (i - (trend.length - 1) / 2) * segW;
      bar.position.set(bx, h / 2, 0);
      trendGroup.add(bar);
      objectCount++;
      (function (tdLocal, barLocal) {
        pickables.push({
          object: barLocal,
          meta: { title: tdLocal.label, rows: [["Total claims", tdLocal.total.toLocaleString()], ["Fraud claims", tdLocal.fraud.toLocaleString()]], source: "claims.csv" },
          onHover: function () { barLocal.material.emissiveIntensity = 0.7; },
          onUnhover: function () { barLocal.material.emissiveIntensity = 0.25; },
        });
      })(td, bar);
    }
    trendGroup.add(window.FW.makeTextSprite(THREE, "MONTHLY FRAUD TREND", { color: "#4cc9f0", fontSize: 30 }).translateY(5.2));
    scene.add(trendGroup);

    var scoreGroup = new THREE.Group();
    scoreGroup.position.x = 11;
    var bins = data.scoreBins || [];
    var maxBin = Math.max(1, Math.max.apply(null, bins.map(function (b) { return b.count; })));
    for (var b = 0; b < bins.length; b++) {
      var bh = 0.4 + (bins[b].count / maxBin) * 6;
      var tt = b / Math.max(1, bins.length - 1);
      var color2 = new THREE.Color(0x22d3ee).lerp(new THREE.Color(0x8b6bf7), tt);
      var mat2 = new THREE.MeshStandardMaterial({ color: color2, roughness: 0.35, metalness: 0.3, emissive: color2, emissiveIntensity: 0.2 });
      var mesh2 = new THREE.Mesh(new THREE.BoxGeometry(0.55, bh, 0.55), mat2);
      mesh2.position.set((b - (bins.length - 1) / 2) * 0.75, bh / 2, 0);
      scoreGroup.add(mesh2);
      objectCount++;
      (function (binLocal, meshLocal) {
        pickables.push({
          object: meshLocal,
          meta: { title: "Score " + binLocal.label, rows: [["Indicator count", binLocal.count.toLocaleString()]], observation: "Screening signal \u2014 not proof of fraud.", source: "fraud_indicators.csv" },
          onHover: function () { meshLocal.material.emissiveIntensity = 0.65; },
          onUnhover: function () { meshLocal.material.emissiveIntensity = 0.2; },
        });
      })(bins[b], mesh2);
    }
    scoreGroup.add(window.FW.makeTextSprite(THREE, "INDICATOR SCORE DISTRIBUTION", { color: "#8b6bf7", fontSize: 28 }).translateY(7.6));
    scoreGroup.add(window.FW.makeTextSprite(THREE, "SCREENING SIGNAL \u2014 NOT PROOF OF FRAUD", { color: "#ff9f5b", fontSize: 22 }).translateY(-1.2));
    scene.add(scoreGroup);

    var rig = window.FW.CameraRig(THREE, camera, canvas, { radius: 24, theta: Math.PI / 2.2, phi: Math.PI / 2.9, minRadius: 6, maxRadius: 60 });
    finalizeScene(rootId, THREE, camera, canvas, renderer, scene, rig, pickables, null, objectCount);
  }

  // ---------------------------------------------------------------------
  // SCENE 4 — Claim Investigation Network
  // ---------------------------------------------------------------------
  function buildNetworkScene(rootId, data) {
    var ctx = baseSetup(rootId, 50, 0.1, 200);
    var THREE = ctx.THREE, scene = ctx.scene, camera = ctx.camera, canvas = ctx.canvas, renderer = ctx.renderer;
    addStarBackdrop(THREE, scene, 180, 60);

    var pickables = [];
    var centerColor = CATEGORY_COLOR[data.riskCategory] || CATEGORY_COLOR.normal;
    var centerNode = new THREE.Mesh(
      new THREE.IcosahedronGeometry(1.0, 1),
      new THREE.MeshStandardMaterial({ color: centerColor, emissive: centerColor, emissiveIntensity: 0.6, roughness: 0.25, metalness: 0.4 })
    );
    scene.add(centerNode);
    pickables.push({ object: centerNode, meta: { title: "CLAIM " + data.claimId, rows: [["Risk category", CATEGORY_LABEL[data.riskCategory] || "NORMAL"]], source: "claims.csv" } });
    scene.add(window.FW.makeTextSprite(THREE, "CLAIM " + data.claimId, { color: "#eef1fb", fontSize: 30 }).translateY(-1.8));

    var satellites = data.satellites || [];
    var nodes = [];
    var objectCount = 1;
    for (var i = 0; i < satellites.length; i++) {
      var s = satellites[i];
      var angle = (i / satellites.length) * Math.PI * 2;
      var radius = 4.6;
      var x = Math.cos(angle) * radius;
      var z = Math.sin(angle) * radius;
      var y = Math.sin(angle * 1.3) * 0.8;
      var color = new THREE.Color(s.color || "#4cc9f0").getHex();
      var node = new THREE.Mesh(new THREE.SphereGeometry(0.55, 20, 20), new THREE.MeshStandardMaterial({ color: color, emissive: color, emissiveIntensity: 0.45, roughness: 0.3 }));
      node.position.set(x, y, z);
      scene.add(node);
      var lineGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), new THREE.Vector3(x, y, z)]);
      scene.add(new THREE.Line(lineGeo, new THREE.LineBasicMaterial({ color: color, transparent: true, opacity: 0.55 })));
      var label = window.FW.makeTextSprite(THREE, s.label, { color: "#eef1fb", fontSize: 24 });
      label.position.set(x, y + 0.85, z);
      scene.add(label);
      var sub = window.FW.makeTextSprite(THREE, s.value, { color: "#9aa3c4", fontSize: 20 });
      sub.position.set(x, y - 0.85, z);
      scene.add(sub);
      nodes.push({ mesh: node, baseY: y, phase: i * 0.6 });
      objectCount++;
      (function (sLocal, nodeLocal) {
        pickables.push({
          object: nodeLocal,
          meta: { title: sLocal.label, rows: [["Value", sLocal.value]], source: "claims.csv \u00b7 fraud_indicators.csv" },
          onHover: function () { nodeLocal.material.emissiveIntensity = 0.85; nodeLocal.scale.setScalar(1.15); },
          onUnhover: function () { nodeLocal.material.emissiveIntensity = 0.45; nodeLocal.scale.setScalar(1); },
        });
      })(s, node);
    }

    var rig = window.FW.CameraRig(THREE, camera, canvas, { radius: 8, theta: Math.PI / 4, phi: Math.PI / 2.6, minRadius: 4, maxRadius: 26 });
    var dollyDone = false;
    function onFrame(t) {
      centerNode.rotation.y = t * 0.35;
      centerNode.rotation.x = t * 0.18;
      if (!dollyDone) {
        var p = Math.min(1, t / 1.1);
        if (p >= 1) dollyDone = true;
      }
      for (var n = 0; n < nodes.length; n++) {
        nodes[n].mesh.position.y = nodes[n].baseY + Math.sin(t * 1.6 + nodes[n].phase) * 0.12;
      }
    }
    finalizeScene(rootId, THREE, camera, canvas, renderer, scene, rig, pickables, onFrame, objectCount);
  }

  // ---------------------------------------------------------------------
  // SCENE 5 — Cosmic backdrop: black hole + accretion disk + nebula
  // Decorative only (no toolbar/picking) — auto-rotates, responds to
  // mouse parallax. Lives inside its own bounded canvas (see app.py notes
  // on why a literal full-page WebGL background isn't used).
  // ---------------------------------------------------------------------
  function buildCosmicScene(rootId, data) {
    var ctx = baseSetup(rootId, 55, 0.1, 400);
    var THREE = ctx.THREE, scene = ctx.scene, camera = ctx.camera, canvas = ctx.canvas, renderer = ctx.renderer, root = ctx.root;
    scene.fog = null;

    addStarBackdrop(THREE, scene, 600, 220);

    // Nebula clouds — additive translucent sprites
    var nebulaColors = [
      ["rgba(139,107,247,0.55)", "rgba(139,107,247,0)"],
      ["rgba(76,201,240,0.45)", "rgba(76,201,240,0)"],
      ["rgba(255,92,114,0.30)", "rgba(255,92,114,0)"],
    ];
    var nebulaGroup = new THREE.Group();
    for (var n = 0; n < 7; n++) {
      var pair = nebulaColors[n % nebulaColors.length];
      var tex = new THREE.CanvasTexture(window.FW.makeRadialTexture(pair[0], pair[1], 256));
      var sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, opacity: 0.5, blending: THREE.AdditiveBlending, depthWrite: false }));
      var a = (n / 7) * Math.PI * 2;
      var r = 40 + (n % 3) * 18;
      sprite.position.set(Math.cos(a) * r, (Math.random() - 0.5) * 20, Math.sin(a) * r - 30);
      var sc = 30 + Math.random() * 26;
      sprite.scale.set(sc, sc, 1);
      nebulaGroup.add(sprite);
    }
    scene.add(nebulaGroup);

    // Black hole: dark event horizon + glowing accretion disk
    var holeGroup = new THREE.Group();
    holeGroup.position.set(0, 0, -18);
    var horizon = new THREE.Mesh(new THREE.SphereGeometry(2.6, 32, 32), new THREE.MeshBasicMaterial({ color: 0x000000 }));
    holeGroup.add(horizon);

    var diskTex = new THREE.CanvasTexture(diskTexture());
    var diskGeo = new THREE.RingGeometry(3.0, 9.5, 96, 1);
    // give the ring proper UV mapping for a radial texture
    var uv = diskGeo.attributes.uv;
    var posAttr = diskGeo.attributes.position;
    var v3 = new THREE.Vector3();
    for (var ui = 0; ui < uv.count; ui++) {
      v3.fromBufferAttribute(posAttr, ui);
      var dist = v3.length();
      var u = (dist - 3.0) / (9.5 - 3.0);
      uv.setXY(ui, u, 0.5);
    }
    var diskMat = new THREE.MeshBasicMaterial({ map: diskTex, transparent: true, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false });
    var disk = new THREE.Mesh(diskGeo, diskMat);
    disk.rotation.x = Math.PI / 2.35;
    holeGroup.add(disk);

    var glow = new THREE.Mesh(
      new THREE.SphereGeometry(3.3, 24, 24),
      new THREE.MeshBasicMaterial({ color: 0x8b6bf7, transparent: true, opacity: 0.12, blending: THREE.AdditiveBlending, depthWrite: false })
    );
    holeGroup.add(glow);
    scene.add(holeGroup);

    // Orbiting particle stream around the black hole
    var orbitCount = 260;
    var orbitGeo = new THREE.BufferGeometry();
    var orbitPos = new Float32Array(orbitCount * 3);
    var orbitData = [];
    for (var op = 0; op < orbitCount; op++) {
      var rr = 4 + Math.random() * 7;
      var aa = Math.random() * Math.PI * 2;
      orbitData.push({ r: rr, a: aa, speed: 0.15 + Math.random() * 0.35, y: (Math.random() - 0.5) * 0.6 });
      orbitPos[op * 3] = holeGroup.position.x + Math.cos(aa) * rr;
      orbitPos[op * 3 + 1] = holeGroup.position.y + orbitData[op].y;
      orbitPos[op * 3 + 2] = holeGroup.position.z + Math.sin(aa) * rr;
    }
    orbitGeo.setAttribute("position", new THREE.BufferAttribute(orbitPos, 3));
    var orbitPoints = new THREE.Points(orbitGeo, new THREE.PointsMaterial({ color: 0xffd8a8, size: 0.1, transparent: true, opacity: 0.85, blending: THREE.AdditiveBlending }));
    scene.add(orbitPoints);

    function diskTexture() {
      var w = 512, h = 8;
      var canvas = document.createElement("canvas");
      canvas.width = w; canvas.height = h;
      var c = canvas.getContext("2d");
      var g = c.createLinearGradient(0, 0, w, 0);
      g.addColorStop(0.0, "rgba(255,255,255,0)");
      g.addColorStop(0.08, "rgba(255,216,168,0.9)");
      g.addColorStop(0.25, "rgba(255,159,91,0.85)");
      g.addColorStop(0.55, "rgba(139,107,247,0.55)");
      g.addColorStop(0.85, "rgba(76,201,240,0.25)");
      g.addColorStop(1.0, "rgba(76,201,240,0)");
      c.fillStyle = g;
      c.fillRect(0, 0, w, h);
      return canvas;
    }

    camera.position.set(0, 6, 24);
    var target = new THREE.Vector3(0, 0, -6);
    camera.lookAt(target);

    var mouseX = 0, mouseY = 0;
    root.addEventListener("pointermove", function (e) {
      var rect = root.getBoundingClientRect();
      mouseX = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouseY = ((e.clientY - rect.top) / rect.height) * 2 - 1;
    });

    window.FW.attachResize(canvas, renderer, camera);
    var clock = new THREE.Clock();
    function animate() {
      requestAnimationFrame(animate);
      var t = clock.getElapsedTime();
      holeGroup.rotation.y = t * 0.05;
      disk.rotation.z = t * 0.12;
      nebulaGroup.rotation.y = t * 0.01;
      var op = orbitGeo.attributes.position;
      for (var i = 0; i < orbitCount; i++) {
        var od = orbitData[i];
        var ang = od.a + t * od.speed;
        op.setXYZ(i, holeGroup.position.x + Math.cos(ang) * od.r, holeGroup.position.y + od.y, holeGroup.position.z + Math.sin(ang) * od.r);
      }
      op.needsUpdate = true;

      var targetCamX = mouseX * 2.4;
      var targetCamY = 6 - mouseY * 1.6;
      camera.position.x += (targetCamX - camera.position.x) * 0.03;
      camera.position.y += (targetCamY - camera.position.y) * 0.03;
      camera.lookAt(target);

      renderer.render(scene, camera);
    }
    animate();
  }

  window.FW = window.FW || {};
  window.FW.buildCityScene = buildCityScene;
  window.FW.buildObservatoryScene = buildObservatoryScene;
  window.FW.buildLabScene = buildLabScene;
  window.FW.buildNetworkScene = buildNetworkScene;
  window.FW.buildCosmicScene = buildCosmicScene;
})();
