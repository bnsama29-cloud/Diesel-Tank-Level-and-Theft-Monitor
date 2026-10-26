(() => {
  const dashboard = document.getElementById("dashboard");
  const leftColumn = document.getElementById("left-column");
  const columnSplitter = document.getElementById("column-splitter");
  const rowSplitter = document.getElementById("row-splitter");
  const sizes = { left: 25, interpretation: 42 };
  const frameHeight = Math.max(620, Math.min(1100, window.screen.availHeight - 180));
  const $ = id => document.getElementById(id);

  const setText = (id, value) => { $(id).textContent = value; };

  const applySizes = () => {
    dashboard.style.setProperty("--left-size", `${sizes.left}%`);
    dashboard.style.setProperty("--interpretation-size", `${sizes.interpretation}%`);
  };
  applySizes();

  const installDrag = (splitter, axis) => {
    splitter.addEventListener("pointerdown", event => {
      event.preventDefault();
      splitter.classList.add("dragging");
      splitter.setPointerCapture(event.pointerId);
    });
    splitter.addEventListener("pointermove", event => {
      if (!splitter.hasPointerCapture(event.pointerId)) return;
      if (axis === "column") {
        const rect = dashboard.getBoundingClientRect();
        sizes.left = Math.min(45, Math.max(18, ((event.clientX - rect.left) / rect.width) * 100));
      } else {
        const rect = leftColumn.getBoundingClientRect();
        sizes.interpretation = Math.min(70, Math.max(25, ((event.clientY - rect.top) / rect.height) * 100));
      }
      applySizes();
    });
    const stopDrag = () => {
      splitter.classList.remove("dragging");
      if ($("history-chart")._fullLayout && window.Plotly) {
        window.Plotly.Plots.resize($("history-chart"));
      }
    };
    splitter.addEventListener("pointerup", stopDrag);
    splitter.addEventListener("pointercancel", stopDrag);
  };
  installDrag(columnSplitter, "column");
  installDrag(rowSplitter, "row");

  $("enlarge-simulation").addEventListener("click", () => {
    const panel = $("simulation-panel");
    if (document.fullscreenElement) document.exitFullscreen();
    else if (panel.requestFullscreen) panel.requestFullscreen();
  });

  const render = args => {
    const latest = args.latest;
    const notice = $("status-notice");
    const error = $("fetch-error");
    notice.className = "notice";
    error.hidden = !args.fetch_error;
    error.textContent = args.fetch_error || "";
    setText("freshness", latest
      ? `${args.freshness} · Last received ${args.age_seconds}s ago`
      : "Waiting for data");

    if (!latest) {
      notice.classList.add("error");
      notice.innerHTML = "<strong>Waiting for telemetry</strong><span>Start Wokwi to receive live readings.</span>";
      setText("litres", "—");
      setText("level", "—");
      setText("generator", "—");
      setText("pump", "—");
      setText("runtime", "—");
      setText("sensor-note", "No sensor reading received yet.");
    } else {
      const stale = args.freshness !== "LIVE";
      const theft = args.status === "Suspected theft";
      notice.classList.add(stale || theft ? "danger" : latest.level_percent <= 20 ? "warning" : "normal");
      notice.innerHTML = `<strong>${escapeHtml(stale ? `DATA STALE · ${args.status}` : args.status)}</strong><span>${escapeHtml(args.explanation)}${stale ? " Displayed values are the last received, not current." : ""}</span>`;
      setText("litres", `${latest.litres.toFixed(1)} L`);
      setText("level", `${latest.level_percent.toFixed(1)}%`);
      setText("generator", latest.generator_on ? "ON" : "OFF");
      setText("pump", latest.pump_on ? "ON" : "OFF");
      setText("runtime", latest.hours_left === null ? "—" : `${latest.hours_left.toFixed(1)} h`);
      setText("sensor-note", `Sensor distance: ${latest.distance_cm.toFixed(1)} cm · ${
        latest.hours_left === null
          ? "Awaiting enough generator-on history for runtime."
          : "Runtime uses observed generator-on consumption."
      }`);
    }

    const chart = $("history-chart");
    const emptyChart = $("empty-chart");
    if (args.chart && window.Plotly) {
      chart.hidden = false;
      emptyChart.hidden = true;
      const data = args.chart.data || [];
      const layout = {
        ...(args.chart.layout || {}),
        autosize: true,
        height: undefined,
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { color: "#d9e6f2" },
        margin: { l: 42, r: 12, t: 38, b: 32 },
      };
      window.Plotly.react(chart, data, layout, {
        responsive: true,
        displayModeBar: false,
      });
    } else {
      chart.hidden = true;
      emptyChart.hidden = false;
    }
    window.parent.postMessage({
      isStreamlitMessage: true,
      type: "streamlit:setFrameHeight",
      height: frameHeight,
    }, "*");
  };

  const escapeHtml = value => String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  window.addEventListener("message", event => {
    if (event.data && event.data.type === "streamlit:render") {
      render(event.data.args);
    }
  });
  window.parent.postMessage({
    type: "streamlit:componentReady",
    apiVersion: 1,
  }, "*");
})();
