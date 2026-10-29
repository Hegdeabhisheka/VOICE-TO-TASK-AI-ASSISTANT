"""Three.js (r128) animated background driven by the Interaction Score and the assistant state."""
from __future__ import annotations

import json

_STATES = ("idle", "listening", "processing", "success", "error")

_TEMPLATE = r"""<!DOCTYPE html>
<!-- vtai-bg3d -->
<html lang="en"><head><meta charset="utf-8">
<meta name="vtai-component" content="vtai-bg3d">
<title>vtai-bg3d</title>
<style>
  html, body { margin:0; height:100%; overflow:hidden; pointer-events:none;
    background: radial-gradient(ellipse at 30% 20%, #0b1030 0%, #05060f 55%, #020208 100%); }
  canvas { display:block; position:fixed; inset:0; width:100%; height:100%; pointer-events:none; }
  #flash { position:fixed; inset:0; opacity:0; pointer-events:none; mix-blend-mode:screen;
    background: radial-gradient(circle at 50% 50%, var(--fc, #39ff14) 0%, transparent 62%); }
  #hud { position:fixed; left:16px; bottom:12px; pointer-events:none; user-select:none;
    font:11px/1.2 ui-monospace, Menlo, Consolas, monospace; letter-spacing:.2em;
    color:rgba(190,220,255,.45); text-shadow:0 0 8px rgba(0,229,255,.35); }
  body.nogl { background:linear-gradient(130deg,#0a0f2e,#1b0f3d,#06111f,#0a0f2e);
    background-size:300% 300%; animation:drift 20s ease-in-out infinite; }
  body.nogl::after { content:""; position:fixed; inset:0; opacity:.18; pointer-events:none;
    background:radial-gradient(circle at 50% 50%, var(--fc, #00e5ff) 0%, transparent 45%); }
  @keyframes drift { 0%{background-position:0% 50%} 50%{background-position:100% 50%} 100%{background-position:0% 50%} }
</style></head>
<body><div id="flash"></div><div id="hud"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
(function () {
  'use strict';
  var CFG = __CFG__;
  var STATES = ['idle', 'listening', 'processing', 'success', 'error'];
  var TIERS = [
    { max: 25,  name: 'DORMANT',          a: 0x7c4dff, b: 0x2f6bff },
    { max: 50,  name: 'WARMING UP',       a: 0x00e5ff, b: 0x1e90ff },
    { max: 75,  name: 'IN FLOW',          a: 0xffc233, b: 0xff7a18 },
    { max: 101, name: 'HYPER-PRODUCTIVE', a: 0x39ff14, b: 0x00ffc8 }
  ];
  var hudEl = document.getElementById('hud');
  var flashEl = document.getElementById('flash');
  var mode = { score: CFG.score, state: CFG.state, level: CFG.level, t0: 0 };
  var now = 0;

  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
  function smooth(x) { x = clamp(x, 0, 1); return x * x * (3 - 2 * x); }
  function tierOf(s) {
    for (var i = 0; i < TIERS.length; i++) { if (s < TIERS[i].max) { return TIERS[i]; } }
    return TIERS[TIERS.length - 1];
  }
  function hex6(n) { return '#' + ('000000' + n.toString(16)).slice(-6); }
  function updateHud() {
    hudEl.textContent = mode.state.toUpperCase() + ' \u00b7 ' + tierOf(mode.score).name +
      ' \u00b7 SCORE ' + Math.round(mode.score);
  }
  function fallback() {
    document.body.classList.add('nogl');
    document.body.style.setProperty('--fc', hex6(tierOf(mode.score).a));
    updateHud();
  }
  function setFlashColor() {
    flashEl.style.setProperty('--fc', mode.state === 'error' ? '#ff2a55' : '#39ff14');
  }
  function setMode(score, state, level, restart) {
    score = clamp(Number(score) || 0, 0, 100);
    if (STATES.indexOf(state) < 0) { state = 'idle'; }
    if (state !== mode.state || restart) { mode.t0 = now; }
    mode.score = score; mode.state = state; mode.level = clamp(Number(level) || 0, 0, 1);
    setFlashColor(); updateHud();
  }

  updateHud(); setFlashColor();
  if (typeof THREE === 'undefined') { fallback(); return; }
  try { init(); } catch (err) { fallback(); }

  function init() {
    var VERT = `
      attribute float aSeed;
      uniform float uTime, uRadius, uPulse, uRipple, uLevel, uBurst, uJitter;
      uniform float uSwirlAngle, uSwirlAmt, uSize, uPixelRatio, uFogNear, uFogFar;
      varying float vSeed;
      varying float vFog;
      void main() {
        vec3 nrm = normalize(position);
        float shell = length(position);
        float r = uRadius * shell;
        float wave = sin(nrm.y * 7.0 + nrm.x * 3.0 - uTime * 4.5 + aSeed * 6.2831853);
        r *= 1.0 + uPulse + uRipple * wave * (0.55 + 0.9 * uLevel);
        r += uBurst * (0.6 + aSeed * 2.4);
        r *= 1.0 + uSwirlAmt * 0.22 * sin(aSeed * 40.0 + uTime * 3.0);
        vec3 p = nrm * r;
        float ang = uSwirlAngle * (0.35 + 0.65 * (1.0 - abs(nrm.y))) * (0.7 + 0.6 * aSeed);
        float cs = cos(ang);
        float sn = sin(ang);
        p = vec3(cs * p.x + sn * p.z, p.y, -sn * p.x + cs * p.z);
        p += uJitter * 0.14 * vec3(sin(aSeed * 91.7 + uTime * 43.0),
                                   sin(aSeed * 57.3 + uTime * 51.0),
                                   sin(aSeed * 33.1 + uTime * 47.0));
        vec4 mv = modelViewMatrix * vec4(p, 1.0);
        gl_Position = projectionMatrix * mv;
        float dist = max(-mv.z, 0.001);
        vFog = clamp((dist - uFogNear) / (uFogFar - uFogNear), 0.0, 1.0);
        gl_PointSize = max(1.0, uSize * uPixelRatio * (0.55 + aSeed * 0.9) * (1.0 + uLevel * 0.4) * (50.0 / dist));
        vSeed = aSeed;
      }`;
    var FRAG = `
      uniform vec3 uColorA;
      uniform vec3 uColorB;
      uniform float uBright;
      uniform float uOpacity;
      varying float vSeed;
      varying float vFog;
      void main() {
        float d = length(gl_PointCoord - vec2(0.5));
        if (d > 0.5) { discard; }
        float a = pow(1.0 - d * 2.0, 1.6);
        vec3 col = mix(uColorA, uColorB, vSeed) * (0.8 + uBright);
        gl_FragColor = vec4(col, a * uOpacity * (1.0 - vFog * 0.9));
      }`;

    var renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    renderer.setPixelRatio(dpr);
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setClearColor(0x000000, 0);
    document.body.insertBefore(renderer.domElement, document.body.firstChild);

    var scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x05060f, 0.018);
    var camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 400);
    function fitDistance() {
      var a = window.innerWidth / Math.max(1, window.innerHeight);
      return 10 * (a < 1 ? 1 + (1 - a) * 0.7 : 1);
    }
    var baseZ = fitDistance();
    camera.position.set(0, 0, baseZ);

    // ---- smoothed state (everything eases toward targets; nothing jumps)
    var neutral = 0x2a2f5c;
    var S = { ca: new THREE.Color(neutral), cb: new THREE.Color(neutral), tint: new THREE.Color(0x39ff14),
              tintAmt: 0, ripple: 0, scale: 0.85, swirl: 0, ringGlow: 0.1, spin: 0.4, ringSpin: 0.4,
              jitter: 0, bright: 0.2, radius: 1.4, ringScale: 1, lvl: 0 };
    var Tca = new THREE.Color(), Tcb = new THREE.Color(), Ttint = new THREE.Color(0x39ff14);
    var outA = new THREE.Color(neutral), outB = new THREE.Color(neutral);

    // ---- voice orb: ~3000 additive particles on a sphere shell, animated in the vertex shader
    var N = 3000, pos = new Float32Array(N * 3), seeds = new Float32Array(N), i;
    for (i = 0; i < N; i++) {
      var z = Math.random() * 2 - 1, th = Math.random() * Math.PI * 2;
      var rr = Math.sqrt(1 - z * z), sh = 0.9 + Math.random() * 0.2;
      pos[i * 3] = rr * Math.cos(th) * sh; pos[i * 3 + 1] = z * sh; pos[i * 3 + 2] = rr * Math.sin(th) * sh;
      seeds[i] = Math.random();
    }
    var pgeo = new THREE.BufferGeometry();
    pgeo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    pgeo.setAttribute('aSeed', new THREE.BufferAttribute(seeds, 1));
    var U = {
      uTime: { value: 0 }, uRadius: { value: 1.4 }, uPulse: { value: 0 }, uRipple: { value: 0 },
      uLevel: { value: 0 }, uBurst: { value: 0 }, uJitter: { value: 0 }, uSwirlAngle: { value: 0 },
      uSwirlAmt: { value: 0 }, uSize: { value: 1 }, uPixelRatio: { value: dpr }, uFogNear: { value: 9 },
      uFogFar: { value: 34 }, uColorA: { value: outA }, uColorB: { value: outB },
      uBright: { value: 0.3 }, uOpacity: { value: 0.9 }
    };
    var points = new THREE.Points(pgeo, new THREE.ShaderMaterial({
      uniforms: U, vertexShader: VERT, fragmentShader: FRAG,
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
    points.frustumCulled = false;
    scene.add(points);

    // ---- wireframe icosahedron core + inner glow
    var core = new THREE.Mesh(new THREE.IcosahedronGeometry(1, 1), new THREE.MeshBasicMaterial({
      color: 0xffffff, wireframe: true, transparent: true, opacity: 0.4,
      blending: THREE.AdditiveBlending, depthWrite: false }));
    var glow = new THREE.Mesh(new THREE.SphereGeometry(1, 32, 24), new THREE.MeshBasicMaterial({
      color: 0xffffff, transparent: true, opacity: 0.2, blending: THREE.AdditiveBlending, depthWrite: false }));
    scene.add(core); scene.add(glow);

    // ---- three orbit rings
    var ringsGroup = new THREE.Group();
    scene.add(ringsGroup);
    var rings = [{ r: 2.5, tx: 1.15, ty: 0.0, sp: 0.6 }, { r: 3.15, tx: 0.45, ty: 0.9, sp: -0.45 },
                 { r: 3.8, tx: 1.55, ty: -0.5, sp: 0.32 }].map(function (def) {
      var mesh = new THREE.Mesh(new THREE.TorusGeometry(1, 0.009, 8, 220), new THREE.MeshBasicMaterial({
        color: 0xffffff, transparent: true, opacity: 0.3, blending: THREE.AdditiveBlending, depthWrite: false }));
      var pivot = new THREE.Group();
      pivot.rotation.x = def.tx; pivot.rotation.y = def.ty;
      pivot.add(mesh); ringsGroup.add(pivot);
      return { mesh: mesh, pivot: pivot, def: def };
    });

    // ---- distant starfield
    var SN = 1400, spos = new Float32Array(SN * 3);
    for (i = 0; i < SN; i++) {
      var sz = Math.random() * 2 - 1, sth = Math.random() * Math.PI * 2, sr = Math.sqrt(1 - sz * sz);
      var dist = 45 + Math.random() * 60;
      spos[i * 3] = sr * Math.cos(sth) * dist; spos[i * 3 + 1] = sz * dist; spos[i * 3 + 2] = sr * Math.sin(sth) * dist;
    }
    var sgeo = new THREE.BufferGeometry();
    sgeo.setAttribute('position', new THREE.BufferAttribute(spos, 3));
    var stars = new THREE.Points(sgeo, new THREE.PointsMaterial({
      color: 0xaec2ff, size: 0.45, transparent: true, opacity: 0.65, depthWrite: false,
      blending: THREE.AdditiveBlending, fog: false }));
    scene.add(stars);

    // ---- input: mouse parallax (the iframe is click-through, so also listen on the parent page)
    var mx = 0, my = 0;
    function onMove(e) {
      var w = (e.view && e.view.innerWidth) || window.innerWidth;
      var h = (e.view && e.view.innerHeight) || window.innerHeight;
      mx = (e.clientX / w - 0.5) * 2; my = (e.clientY / h - 0.5) * 2;
    }
    window.addEventListener('mousemove', onMove, { passive: true });
    try { if (window.parent && window.parent !== window) { window.parent.addEventListener('mousemove', onMove, { passive: true }); } }
    catch (e2) { /* cross-origin parent: parallax simply stays idle */ }
    window.addEventListener('resize', function () {
      camera.aspect = window.innerWidth / Math.max(1, window.innerHeight);
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
      baseZ = fitDistance();
    });
    // Optional live updates without recreating the iframe:
    //   iframe.contentWindow.postMessage({type:'vtai-bg3d', score:60, state:'listening', level:0.4}, '*')
    window.addEventListener('message', function (e) {
      var d = e.data;
      if (d && d.type === 'vtai-bg3d') { setMode(d.score, d.state, d.level, !!d.restart); }
    });
    window.VoiceBg = { update: setMode };

    var reduce = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    var last = performance.now(), dt = 0.016, spinAngle = 0, swirlAngle = 0;
    function ease(rate) { return 1 - Math.exp(-rate * dt); }

    function frame() {
      requestAnimationFrame(frame);
      var t = performance.now();
      dt = Math.min(0.05, (t - last) / 1000); last = t; now += dt;

      var score = mode.score / 100, tier = tierOf(mode.score), age = now - mode.t0, st = mode.state;
      if (st === 'success' && age > 2.8) { st = 'idle'; }   // transient states settle back to idle
      if (st === 'error' && age > 1.8) { st = 'idle'; }
      var hyper = smooth((score - 0.6) / 0.4);              // tighter + faster when Hyper-Productive
      var mood = (0.55 + 0.85 * score + 0.5 * hyper) * (reduce ? 0.4 : 1);
      var wob = 0.72 + 0.28 * Math.sin(now * 9.0) * Math.sin(now * 3.3 + 1.0);
      var liveLvl = clamp(Math.max(mode.level, 0.12) * wob, 0, 1);

      Tca.setHex(tier.a); Tcb.setHex(tier.b);
      var T = { ripple: 0, scale: 1, swirl: 0, ringGlow: 0.4 + 0.2 * score, spin: 1, ringSpin: 1,
                jitter: 0, tintAmt: 0, bright: 0.45 + 0.4 * score, lvl: 0 };
      if (st === 'listening') {
        T.ripple = 0.1 + 0.42 * liveLvl; T.scale = 1 + 0.42 * liveLvl; T.ringGlow = 1; T.spin = 1.3;
        T.bright = 1; T.lvl = liveLvl;
      } else if (st === 'processing') {
        T.swirl = 1; T.ringSpin = 4.5; T.spin = 2.4; T.ripple = 0.08; T.ringGlow = 0.9; T.bright = 0.95;
      } else if (st === 'success') {
        Ttint.setHex(0x39ff14); T.tintAmt = age < 1.4 ? 1 : 0; T.ringGlow = 1; T.spin = 1.6; T.bright = 1;
      } else if (st === 'error') {
        Ttint.setHex(0xff2a55); T.tintAmt = age < 1.2 ? 1 : 0; T.jitter = age < 0.8 ? 1 : 0;
        T.spin = 0.6; T.ringGlow = 0.8;
      }

      S.ca.lerp(Tca, ease(2.4)); S.cb.lerp(Tcb, ease(2.4)); S.tint.lerp(Ttint, ease(10));
      S.tintAmt += (T.tintAmt - S.tintAmt) * ease(6);
      S.ripple += (T.ripple - S.ripple) * ease(6);
      S.scale += (T.scale - S.scale) * ease(10);
      S.swirl += (T.swirl - S.swirl) * ease(2.2);
      S.ringGlow += (T.ringGlow - S.ringGlow) * ease(3);
      S.spin += (T.spin - S.spin) * ease(2.5);
      S.ringSpin += (T.ringSpin - S.ringSpin) * ease(2.5);
      S.jitter += (T.jitter - S.jitter) * ease(14);
      S.bright += (T.bright - S.bright) * ease(3);
      S.lvl += (T.lvl - S.lvl) * ease(12);
      S.radius += ((1.68 - 0.26 * hyper) - S.radius) * ease(1.6);
      S.ringScale += ((1 - 0.15 * hyper) - S.ringScale) * ease(1.6);

      var burst = 0, flash = 0;
      if (mode.state === 'success') {
        burst = (age < 0.12 ? age / 0.12 : Math.exp(-(age - 0.12) * 2.4)) * 1.1;
        flash = 0.34 * Math.min(1, age / 0.06) * Math.exp(-age * 3.0);
      } else if (mode.state === 'error') {
        flash = 0.16 * Math.min(1, age / 0.05) * Math.exp(-age * 4.0);
      }
      flashEl.style.opacity = flash.toFixed(3);

      spinAngle += dt * 0.22 * mood * S.spin;
      swirlAngle += dt * (0.12 * mood + 7.0 * S.swirl);
      var pulse = 0.035 * Math.sin(now * 1.15 * (0.8 + 0.4 * score));   // idle "breathing"

      outA.copy(S.ca).lerp(S.tint, S.tintAmt * 0.85);
      outB.copy(S.cb).lerp(S.tint, S.tintAmt * 0.85);
      U.uTime.value = now; U.uRadius.value = S.radius * S.scale; U.uPulse.value = pulse;
      U.uRipple.value = S.ripple; U.uLevel.value = S.lvl; U.uBurst.value = burst; U.uJitter.value = S.jitter;
      U.uSwirlAngle.value = swirlAngle; U.uSwirlAmt.value = S.swirl; U.uBright.value = S.bright;
      points.rotation.y = spinAngle; points.rotation.x = 0.35 * Math.sin(now * 0.17);

      var orbR = S.radius * S.scale * (1 + pulse * 1.4);
      core.scale.setScalar(orbR * 0.62); core.rotation.y = spinAngle * 1.7; core.rotation.x = spinAngle * 0.9;
      core.material.color.copy(outA); core.material.opacity = 0.2 + 0.45 * S.bright;
      glow.scale.setScalar(orbR * 0.36 * (1 + 0.12 * Math.sin(now * 3.0)));
      glow.material.color.copy(outB); glow.material.opacity = 0.12 + 0.26 * S.bright + flash * 0.8;

      ringsGroup.rotation.y = Math.sin(now * 0.12) * 0.25;
      for (var k = 0; k < rings.length; k++) {
        var rg = rings[k];
        rg.pivot.scale.setScalar(rg.def.r * S.ringScale * (1 + 0.35 * (S.scale - 1) * (1 + 0.3 * k)));
        rg.mesh.rotation.z += dt * rg.def.sp * S.ringSpin * mood;
        rg.mesh.material.color.copy(k % 2 ? outB : outA);
        rg.mesh.material.opacity = 0.12 + 0.62 * S.ringGlow;
      }

      stars.rotation.y += dt * 0.004 * mood; stars.rotation.x += dt * 0.0015 * mood;
      camera.position.x += (mx * 1.3 - camera.position.x) * ease(2.4) + (Math.random() - 0.5) * 0.22 * S.jitter;
      camera.position.y += (-my * 0.8 - camera.position.y) * ease(2.4) + (Math.random() - 0.5) * 0.22 * S.jitter;
      camera.position.z += (baseZ - camera.position.z) * ease(3);
      camera.lookAt(0, 0, 0);
      renderer.render(scene, camera);
    }
    frame();
  }
})();
</script></body></html>
"""


def build_background_html(score: int, state: str, level: float = 0.0) -> str:
    """Return a self-contained HTML document with the Three.js scene.

    `score` (0-100) selects the mood palette and rotation speed, `state` selects the live
    behaviour (idle / listening / processing / success / error) and `level` (0-1) drives the
    audio-reactive scale in the listening state. Invalid inputs are clamped to safe defaults.
    """
    try:
        score_i = max(0, min(100, int(round(float(score)))))
    except (TypeError, ValueError, OverflowError):
        score_i = 0
    state = state if state in _STATES else "idle"
    try:
        level_f = max(0.0, min(1.0, float(level)))
    except (TypeError, ValueError):
        level_f = 0.0
    if level_f != level_f:  # NaN
        level_f = 0.0
    cfg = json.dumps({"score": score_i, "state": state, "level": level_f})
    return _TEMPLATE.replace("__CFG__", cfg)