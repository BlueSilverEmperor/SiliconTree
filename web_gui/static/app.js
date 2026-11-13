(() => {
  const STAGE_ORDER = ["IF", "ID", "EX", "MEM", "WB"];
  const STAGE_LABELS = {
    IF: "IF · FETCH",
    ID: "ID · DECODE",
    EX: "EX · EXECUTE",
    MEM: "MEM · MEMORY",
    WB: "WB · WRITEBACK",
  };

  const BUS_NODES = {
    REG_FILE: { x: 80, y: 38 },
    ALU: { x: 245, y: 38 },
    CPU_IF: { x: 80, y: 105 },
    ICACHE: { x: 245, y: 105 },
    CPU_MEM: { x: 245, y: 170 },
    L1_CACHE: { x: 420, y: 105 },
    RAM: { x: 565, y: 105 },
    DMA: { x: 420, y: 170 },
    IRQ_CTRL: { x: 565, y: 38 },
    CPU_PC: { x: 420, y: 38 },
  };

  const PKT_COLORS = {
    IFETCH: "#22d3ee",
    MEM_READ: "#34d399",
    MEM_WRITE: "#f59e0b",
    REG_ALU: "#a78bfa",
    DMA: "#e879f9",
    IRQ: "#f43f5e",
  };

  let state = null;
  let prevRegs = new Array(16).fill(0);
  let selectedCacheKey = null;
  let showL2 = false;
  let isPlaying = false;
  let speedHz = 4;
  let lastTickTs = 0;
  let tickProgress = 1.0;

  async function api(url, method = "GET", body = null) {
    const opts = { method, headers: { "Content-Type": "application/json" } };
    if (body !== null) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    if (!res.ok) return null;
    const data = await res.json();
    applyState(data);
    return data;
  }

  function applyState(data) {
    const oldRegs = state ? state.snapshot.regs : prevRegs;
    prevRegs = oldRegs;
    state = data;
    if (state.snapshot.halted && isPlaying) {
      setPlaying(false);
    }
    renderAll();
  }

  function setPlaying(playing) {
    isPlaying = playing;
    const btn = document.getElementById("btn-play");
    btn.textContent = playing ? "Pause" : "Play";
    btn.classList.toggle("btn-danger", playing);
    btn.classList.toggle("btn-primary", !playing);
  }

  function renderAll() {
    if (!state) return;
    renderTabs();
    renderTelemetry();
    renderPipelineSVG();
    renderCacheMatrix();
    renderBusSVG();
    renderRegistersAndRTN();
    renderModeHUD();
  }

  function renderTabs() {
    const nav = document.getElementById("mode-tabs");
    if (nav.childElementCount === 0) {
      state.catalog.forEach((m) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "mode-tab";
        btn.dataset.modeId = m.id;
        btn.textContent = m.title;
        btn.title = `${m.category}: ${m.description}`;
        btn.addEventListener("click", () => {
          setPlaying(false);
          selectedCacheKey = null;
          showL2 = false;
          api(`/api/mode/${m.id}`, "POST");
        });
        nav.appendChild(btn);
      });
    }
    Array.from(nav.children).forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.modeId === state.mode_id);
    });
  }

  function renderTelemetry() {
    const s = state.snapshot;
    document.getElementById("stat-cycle").textContent = String(s.cycle).padStart(3, "0");
    document.getElementById("stat-retired").textContent = s.instructions_retired;
    document.getElementById("stat-cpi").textContent = Number(s.cpi).toFixed(2);
    document.getElementById("stat-pc").textContent = `0x${s.pc.toString(16).toUpperCase().padStart(4, "0")}`;
    const pill = document.getElementById("stat-state");
    pill.textContent = s.halted ? "HALTED" : isPlaying ? "RUNNING" : "PAUSED";
    pill.style.color = s.halted ? "var(--amber)" : isPlaying ? "var(--emerald)" : "var(--text-secondary)";

    document.getElementById("pipeline-meta").textContent =
      `Stalls: ${s.stall_cycles} · Flushes: ${s.speculative_flushes} · Predictor: ${s.predictor_mode}`;
    document.getElementById("pred-meta").textContent =
      `Mispredictions: ${s.predictor_mispredictions}`;
    document.getElementById("bus-meta").textContent =
      `${s.bus_topology} · ${s.dma_active ? "DMA ACTIVE (CYCLE STEAL)" : `DMA: ${s.dma_words_transferred}w`}`;
  }

  function svgEl(tag, attrs = {}, text = null) {
    const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, String(v)));
    if (text !== null) el.textContent = text;
    return el;
  }

  function renderPipelineSVG() {
    const svg = document.getElementById("pipeline-svg");
    svg.innerHTML = "";
    const s = state.snapshot;

    const defs = svgEl("defs");
    const marker = svgEl("marker", {
      id: "arrow-cyan",
      markerWidth: 7,
      markerHeight: 7,
      refX: 6,
      refY: 3.5,
      orient: "auto",
    });
    marker.appendChild(svgEl("polygon", { points: "0 0, 7 3.5, 0 7", fill: "#22d3ee" }));
    defs.appendChild(marker);
    svg.appendChild(defs);

    const boxW = 212;
    const gap = 26;
    const startX = 16;
    const boxY = 34;
    const boxH = 122;
    const stageCenters = {};

    STAGE_ORDER.forEach((name, idx) => {
      const x = startX + idx * (boxW + gap);
      stageCenters[name] = { cx: x + boxW / 2, top: boxY, cy: boxY + boxH / 2 };
      const slot = s.stages[name];

      let cls = "stage-card";
      if (slot.is_bubble) {
        if (slot.stall_reason) cls += " stall";
      } else if (slot.l1_warmed_speculatively) {
        cls += " warm";
      } else if (slot.is_speculative) {
        cls += " spec";
      } else if (name === "IF" || name === "ID") {
        cls += " active";
      } else {
        cls += " committed";
      }

      const g = svgEl("g");
      g.appendChild(svgEl("rect", { x, y: boxY, width: boxW, height: boxH, rx: 8, class: cls }));
      g.appendChild(svgEl("rect", { x: x + 1, y: boxY + 1, width: boxW - 2, height: 24, rx: 7, class: "stage-hdr" }));
      g.appendChild(svgEl("text", { x: x + 10, y: boxY + 17, class: "stage-title" }, STAGE_LABELS[name]));

      const opText = slot.is_bubble
        ? (slot.stall_reason ? `STALL: ${slot.stall_reason}` : "NOP / BUBBLE")
        : `0x${slot.pc.toString(16).toUpperCase().padStart(4, "0")}: ${slot.text.slice(0, 18)}`;
      g.appendChild(svgEl("text", { x: x + 10, y: boxY + 48, class: "stage-op" }, opText));

      if (!slot.is_bubble && slot.rtn) {
        g.appendChild(svgEl("text", { x: x + 10, y: boxY + 70, class: "stage-rtn" }, slot.rtn.slice(0, 26)));
      }

      const badges = [];
      if (slot.is_speculative) badges.push({ label: "SPEC", fill: "#f59e0b" });
      if (slot.l1_warmed_speculatively) badges.push({ label: "L1-WARM!", fill: "#f43f5e" });
      if (slot.mispredicted) badges.push({ label: "MISPRED", fill: "#f43f5e" });
      if (slot.forwarded_from && slot.forwarded_from.length) badges.push({ label: "FWD", fill: "#22d3ee" });
      if (slot.mem_cycles_left > 0) badges.push({ label: `MEM:${slot.mem_cycles_left}c`, fill: "#f59e0b" });
      if (slot.ex_cycles_left > 0) badges.push({ label: `ALU:${slot.ex_cycles_left}c`, fill: "#a78bfa" });

      let bx = x + 10;
      badges.slice(0, 3).forEach((b) => {
        g.appendChild(svgEl("text", { x: bx, y: boxY + boxH - 12, class: "stage-badge", fill: b.fill }, b.label));
        bx += b.label.length * 7.2 + 10;
      });

      svg.appendChild(g);

      if (idx < STAGE_ORDER.length - 1) {
        const ax1 = x + boxW + 3;
        const ax2 = x + boxW + gap - 3;
        const ay = boxY + boxH / 2;
        svg.appendChild(svgEl("line", {
          x1: ax1, y1: ay, x2: ax2, y2: ay,
          stroke: "#3b4c66", "stroke-width": 2, "marker-end": "url(#arrow-cyan)"
        }));
      }
    });

    // Forwarding arcs
    (s.forwarding_events || []).slice(0, 2).forEach((fwd, i) => {
      const srcName = fwd.from_stage === "MEM_WB" ? "MEM" : "WB";
      const src = stageCenters[srcName];
      const dst = stageCenters["EX"];
      if (!src || !dst) return;
      const arcY = 14 + i * 10;
      const d = `M ${src.cx} ${src.top} L ${src.cx} ${arcY} L ${dst.cx + i * 14} ${arcY} L ${dst.cx + i * 14} ${dst.top}`;
      svg.appendChild(svgEl("path", { d, class: "fwd-arc", "marker-end": "url(#arrow-cyan)" }));
      svg.appendChild(svgEl("text", {
        x: (src.cx + dst.cx) / 2,
        y: arcY - 3,
        fill: "#22d3ee",
        "font-family": "var(--font-mono)",
        "font-size": 10,
        "text-anchor": "middle",
      }, `FWD R${fwd.reg}=0x${fwd.value.toString(16).toUpperCase()}`));
    });
  }

  function renderCacheMatrix() {
    const s = state.snapshot;
    const hasL2 = s.l2_lines && s.l2_lines.length > 0;
    const togBtn = document.getElementById("btn-toggle-l2");
    togBtn.hidden = !hasL2;
    togBtn.textContent = showL2 ? "View L1" : "View L2";

    const total = s.l1_hits + s.l1_misses;
    const rate = total > 0 ? Math.round((s.l1_hits / total) * 100) : 0;
    document.getElementById("cache-stats").textContent =
      `H:${s.l1_hits} M:${s.l1_misses} (${rate}%) CM:${s.l1_conflict_misses}`;

    const lines = showL2 && hasL2 ? s.l2_lines : s.l1_lines;
    const grid = document.getElementById("cache-grid");
    grid.innerHTML = "";
    let selectedLine = null;

    lines.forEach((ln) => {
      const key = `${showL2 ? "L2" : "L1"}-${ln.set_index}-${ln.way_index}`;
      const isSel = selectedCacheKey === key;
      if (isSel) selectedLine = ln;

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "cache-cell";
      if (ln.valid) btn.classList.add("valid");
      if (ln.speculative_warm && ln.valid) btn.classList.add("spec-warm");
      else if (ln.last_access_cycle === s.cycle && s.cycle > 0) {
        if (ln.last_access_type.includes("HIT")) btn.classList.add("hit-flash");
        else if (ln.last_access_type.includes("MISS") || ln.last_access_type.includes("FILL")) btn.classList.add("miss-flash");
      }
      if (isSel) btn.classList.add("selected");

      const flags = `${ln.valid ? "V" : "-"}${ln.dirty ? "D" : "-"}${ln.speculative_warm && ln.valid ? "!" : ""}`;
      btn.innerHTML = `
        <div class="cache-cell-top"><span>S${ln.set_index} W${ln.way_index}</span><span>[${flags}]</span></div>
        <div>${ln.valid ? `TAG 0x${ln.tag.toString(16).toUpperCase()}` : "EMPTY"}</div>
      `;
      btn.addEventListener("click", () => {
        selectedCacheKey = key;
        renderCacheMatrix();
      });
      grid.appendChild(btn);
    });

    const insp = document.getElementById("cache-inspector");
    if (selectedLine && selectedLine.valid) {
      const words = selectedLine.data_words.slice(0, 4).map((w) => w.toString(16).toUpperCase().padStart(8, "0")).join(" ");
      insp.textContent = `S${selectedLine.set_index} W${selectedLine.way_index} TAG=0x${selectedLine.tag.toString(16).toUpperCase()} SPEC=${selectedLine.speculative_warm} | ${words}`;
    } else {
      insp.textContent = "Click any cache line to inspect 64-byte words. [!] = Speculatively Warmed.";
    }
  }

  function renderBusSVG() {
    const svg = document.getElementById("bus-svg");
    svg.innerHTML = "";
    const s = state.snapshot;

    const tracks = [
      ["REG_FILE", "ALU", false],
      ["CPU_IF", "ICACHE", false],
      ["CPU_MEM", "L1_CACHE", false],
      ["L1_CACHE", "RAM", false],
      ["DMA", "RAM", s.dma_active],
      ["IRQ_CTRL", "CPU_PC", false],
    ];
    tracks.forEach(([a, b, isDma]) => {
      const pa = BUS_NODES[a];
      const pb = BUS_NODES[b];
      svg.appendChild(svgEl("line", {
        x1: pa.x, y1: pa.y, x2: pb.x, y2: pb.y,
        class: isDma ? "bus-track dma-active" : "bus-track",
      }));
    });

    Object.entries(BUS_NODES).forEach(([name, pos]) => {
      const g = svgEl("g");
      g.appendChild(svgEl("rect", {
        x: pos.x - 42, y: pos.y - 14, width: 84, height: 28, rx: 5, class: "bus-chip",
      }));
      g.appendChild(svgEl("text", { x: pos.x, y: pos.y + 4, class: "bus-chip-label" }, name));
      svg.appendChild(g);
    });

    // Packet interpolation layer
    const pktLayer = svgEl("g", { id: "bus-packet-layer" });
    svg.appendChild(pktLayer);
    updateBusPackets();
  }

  function updateBusPackets() {
    const layer = document.getElementById("bus-packet-layer");
    if (!layer || !state) return;
    layer.innerHTML = "";
    const pkts = state.snapshot.bus_packets || [];
    pkts.forEach((p) => {
      const src = BUS_NODES[p.src];
      const dst = BUS_NODES[p.dst];
      if (!src || !dst) return;
      const done = Math.max(0, p.cycles_total - p.cycles_remaining);
      const frac = Math.min(1, (done + tickProgress) / Math.max(1, p.cycles_total));
      const x = src.x + (dst.x - src.x) * frac;
      const y = src.y + (dst.y - src.y) * frac;
      const col = PKT_COLORS[p.kind] || "#22d3ee";
      layer.appendChild(svgEl("circle", { cx: x, cy: y, r: 6, fill: col }));
      layer.appendChild(svgEl("circle", { cx: x, cy: y, r: 2.2, fill: "#ffffff" }));
    });
  }

  function renderRegistersAndRTN() {
    const s = state.snapshot;
    const grid = document.getElementById("reg-grid");
    grid.innerHTML = "";
    for (let i = 0; i < 16; i++) {
      const val = s.regs[i];
      const spec = s.spec_regs[i];
      const cell = document.createElement("div");
      cell.className = "reg-cell";
      if (spec !== val) cell.classList.add("spec-diff");
      else if (val !== prevRegs[i]) cell.classList.add("changed");

      const alias = i === 0 ? "ZR" : i === 14 ? "SP" : i === 15 ? "RA" : "";
      const hex = `0x${val.toString(16).toUpperCase().padStart(8, "0")}`;
      cell.innerHTML = `<span class="reg-name">R${i}${alias ? ` (${alias})` : ""}</span><span>${hex}</span>`;
      grid.appendChild(cell);
    }

    const log = document.getElementById("rtn-log");
    log.innerHTML = "";
    (s.rtn_log || []).forEach((line) => {
      const div = document.createElement("div");
      div.className = "rtn-line";
      if (line.includes("FLUSH")) div.classList.add("flush");
      else if (line.includes("SPEC")) div.classList.add("spec");
      div.textContent = line;
      log.appendChild(div);
    });
    log.scrollTop = log.scrollHeight;
  }

  function renderModeHUD() {
    const body = document.getElementById("mode-hud-body");
    const badge = document.getElementById("outcome-badge");
    const out = state.outcome;
    const hud = state.mode_hud;

    badge.textContent = out.title.toUpperCase();
    badge.style.color = out.finished ? (out.victory ? "var(--emerald)" : "var(--crimson)") : "var(--cyan)";
    body.innerHTML = "";

    const msgBox = document.createElement("div");
    msgBox.className = "hud-alert";
    if (out.finished && out.victory) msgBox.classList.add("success");
    else if (out.finished && !out.victory) msgBox.classList.add("danger");
    msgBox.textContent = out.message;

    if (state.mode_id === "spectrescope") {
      if (hud.leak_detected) {
        msgBox.classList.add("danger");
        msgBox.textContent = `RED ALERT: Speculative L1 leak @ ${hud.leaked_addresses.join(", ")}`;
      }
      const controls = document.createElement("div");
      controls.className = "hud-group";

      const lfenceBtn = document.createElement("button");
      lfenceBtn.type = "button";
      lfenceBtn.className = `btn ${hud.lfence_enabled ? "btn-emerald" : "btn-danger"}`;
      lfenceBtn.textContent = hud.lfence_enabled ? "LFENCE: ON (Protected)" : "LFENCE: OFF (Vulnerable)";
      lfenceBtn.addEventListener("click", () => {
        setPlaying(false);
        api("/api/spectre/lfence", "POST", {});
      });

      const probeBtn = document.createElement("button");
      probeBtn.type = "button";
      probeBtn.className = "btn btn-primary";
      probeBtn.textContent = "Flush+Reload Probe";
      probeBtn.addEventListener("click", () => api("/api/spectre/probe", "POST", {}));

      controls.appendChild(lfenceBtn);
      controls.appendChild(probeBtn);

      const bars = document.createElement("div");
      bars.className = "probe-bars";
      const map = new Map((hud.probe_results || []).map((r) => [r.slot, r]));
      for (let i = 0; i < (hud.num_probe_slots || 8); i++) {
        const slot = document.createElement("div");
        slot.className = "probe-slot";
        const r = map.get(i);
        if (r) {
          if (r.hit) slot.classList.add("hit");
          slot.textContent = `#${i}: ${r.latency}c${r.hit ? " HIT!" : ""}`;
        } else {
          slot.textContent = `#${i}: --`;
        }
        bars.appendChild(slot);
      }

      body.appendChild(controls);
      body.appendChild(msgBox);
      body.appendChild(bars);
    } else if (state.mode_id === "silicon_heist") {
      const grp = document.createElement("div");
      grp.className = "hud-group";

      const dmaBtn = document.createElement("button");
      dmaBtn.type = "button";
      dmaBtn.className = "btn btn-primary";
      dmaBtn.textContent = "Trigger DMA Escape";
      dmaBtn.addEventListener("click", () => api("/api/heist/dma", "POST", {}));

      const meter = document.createElement("div");
      meter.className = "meter";
      const pct = Math.min(100, Math.round((hud.stealth_noise / Math.max(1, hud.max_noise)) * 100));
      const fill = document.createElement("div");
      fill.className = `meter-fill ${pct >= 80 ? "crit" : pct >= 40 ? "warn" : ""}`;
      fill.style.width = `${pct}%`;
      meter.appendChild(fill);

      const lbl = document.createElement("span");
      lbl.className = "panel-meta num";
      lbl.textContent = `State: ${hud.stealth_state} · Lockers: ${hud.lockers_touched}/${hud.total_lockers} · Noise: ${hud.stealth_noise}/${hud.max_noise}`;

      grp.appendChild(dmaBtn);
      grp.appendChild(meter);
      grp.appendChild(lbl);
      body.appendChild(grp);
      body.appendChild(msgBox);
    } else if (state.mode_id === "silicon_deathmatch") {
      const grp = document.createElement("div");
      grp.className = "hud-group";

      const meter = document.createElement("div");
      meter.className = "meter";
      const pct = Math.max(0, Math.min(100, Math.round((hud.thermal_hp / Math.max(1, hud.max_thermal_hp)) * 100)));
      const fill = document.createElement("div");
      fill.className = `meter-fill ${pct < 30 ? "crit" : pct < 60 ? "warn" : ""}`;
      fill.style.width = `${pct}%`;
      meter.appendChild(fill);

      const hpLbl = document.createElement("span");
      hpLbl.className = "panel-meta num";
      hpLbl.textContent = `Wave ${hud.wave_index + 1}/${hud.total_waves} · Thermal HP ${hud.thermal_hp}% · L1 ${hud.l1_associativity}-Way`;

      const up4 = document.createElement("button");
      up4.type = "button";
      up4.className = "btn";
      up4.textContent = "Draft: 4-Way L1";
      up4.addEventListener("click", () => api("/api/deathmatch/upgrade", "POST", { upgrade_id: "CACHE_4WAY" }));

      const upCool = document.createElement("button");
      upCool.type = "button";
      upCool.className = "btn";
      upCool.textContent = "Draft: Vapor Sink";
      upCool.addEventListener("click", () => api("/api/deathmatch/upgrade", "POST", { upgrade_id: "COOLING_SINK" }));

      const nextWave = document.createElement("button");
      nextWave.type = "button";
      nextWave.className = "btn btn-primary";
      nextWave.textContent = "Next Wave";
      nextWave.disabled = !hud.upgrade_draft_open;
      nextWave.addEventListener("click", () => api("/api/deathmatch/next_wave", "POST", {}));

      grp.appendChild(meter);
      grp.appendChild(hpLbl);
      grp.appendChild(up4);
      grp.appendChild(upCool);
      grp.appendChild(nextWave);
      body.appendChild(grp);
      body.appendChild(msgBox);
    } else if (state.mode_id === "silicon_forensic") {
      const grp = document.createElement("div");
      grp.className = "hud-group";

      const scrub = document.createElement("input");
      scrub.type = "range";
      scrub.min = 0;
      scrub.max = Math.max(1, hud.crash_cycle);
      scrub.value = hud.inspected_cycle;
      scrub.addEventListener("input", (e) => api("/api/forensic/scrub", "POST", { cycle: Number(e.target.value) }));

      const lbl = document.createElement("span");
      lbl.className = "panel-meta num";
      lbl.textContent = `Scrub: ${hud.inspected_cycle}/${hud.crash_cycle} · Dirty Tags: ${(hud.dirty_tags || []).join(", ") || "None"}`;

      const sub = document.createElement("button");
      sub.type = "button";
      sub.className = "btn btn-primary";
      sub.textContent = "Submit Dirty Tag Evidence";
      sub.addEventListener("click", () => api("/api/forensic/submit", "POST", {}));

      grp.appendChild(scrub);
      grp.appendChild(lbl);
      grp.appendChild(sub);
      body.appendChild(grp);
      body.appendChild(msgBox);
    } else if (state.mode_id === "architect_tycoon") {
      const grp = document.createElement("div");
      grp.className = "hud-group";

      const clk = document.createElement("input");
      clk.type = "range";
      clk.min = "1.0";
      clk.max = "4.5";
      clk.step = "0.2";
      clk.value = hud.clock_ghz;
      clk.addEventListener("change", (e) => api("/api/tycoon/configure", "POST", { clock_ghz: Number(e.target.value) }));

      const assocBtn = document.createElement("button");
      assocBtn.type = "button";
      assocBtn.className = "btn";
      assocBtn.textContent = `L1: ${hud.l1_associativity}-Way`;
      assocBtn.addEventListener("click", () => {
        const next = hud.l1_associativity === 1 ? 2 : hud.l1_associativity === 2 ? 4 : 1;
        api("/api/tycoon/configure", "POST", { l1_associativity: next });
      });

      const fwdBtn = document.createElement("button");
      fwdBtn.type = "button";
      fwdBtn.className = "btn";
      fwdBtn.textContent = `Forwarding: ${hud.forwarding_enabled ? "ON" : "OFF"}`;
      fwdBtn.addEventListener("click", () => api("/api/tycoon/configure", "POST", { forwarding_enabled: !hud.forwarding_enabled }));

      const evalBtn = document.createElement("button");
      evalBtn.type = "button";
      evalBtn.className = "btn btn-primary";
      evalBtn.textContent = "Evaluate Contract";
      evalBtn.addEventListener("click", () => api("/api/tycoon/evaluate", "POST", {}));

      const stats = document.createElement("span");
      stats.className = "panel-meta num";
      stats.textContent = `${hud.clock_ghz.toFixed(1)} GHz · Area ${hud.die_area_mm2}/${hud.max_area_mm2} mm2 · Power ${hud.power_watts}/${hud.max_power_w} W`;

      grp.appendChild(clk);
      grp.appendChild(assocBtn);
      grp.appendChild(fwdBtn);
      grp.appendChild(evalBtn);
      grp.appendChild(stats);
      body.appendChild(grp);
      body.appendChild(msgBox);
    } else {
      body.appendChild(msgBox);
    }
  }

  // Transport listeners
  document.getElementById("btn-play").addEventListener("click", () => {
    setPlaying(!isPlaying);
    lastTickTs = performance.now();
  });
  document.getElementById("btn-step").addEventListener("click", () => {
    setPlaying(false);
    tickProgress = 1.0;
    api("/api/step", "POST", { count: 1 });
  });
  document.getElementById("btn-rewind").addEventListener("click", () => {
    setPlaying(false);
    tickProgress = 1.0;
    api("/api/rewind", "POST", { count: 1 });
  });
  document.getElementById("btn-reset").addEventListener("click", () => {
    setPlaying(false);
    tickProgress = 1.0;
    api("/api/reset", "POST", {});
  });
  document.getElementById("speed-slider").addEventListener("input", (e) => {
    speedHz = Number(e.target.value);
    document.getElementById("speed-label").textContent = `${speedHz} Hz`;
  });
  document.getElementById("btn-toggle-l2").addEventListener("click", () => {
    showL2 = !showL2;
    selectedCacheKey = null;
    renderCacheMatrix();
  });

  function frameLoop(ts) {
    if (isPlaying && state && !state.snapshot.halted) {
      const interval = 1000 / Math.max(1, speedHz);
      const elapsed = ts - lastTickTs;
      tickProgress = Math.min(1, elapsed / interval);
      updateBusPackets();
      if (elapsed >= interval) {
        lastTickTs = ts;
        tickProgress = 0;
        api("/api/step", "POST", { count: 1 });
      }
    }
    requestAnimationFrame(frameLoop);
  }

  api("/api/state").then(() => {
    lastTickTs = performance.now();
    requestAnimationFrame(frameLoop);
  });
})();

