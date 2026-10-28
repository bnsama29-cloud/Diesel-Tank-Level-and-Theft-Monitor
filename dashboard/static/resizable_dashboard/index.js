(() => {
  const $ = id => document.getElementById(id);
  const setText = (id, value) => { $(id).textContent = value; };

  const setFrameHeight = () => {
    const height = window.innerWidth <= 760
      ? 1060
      : Math.max(620, Math.min(900, window.screen.availHeight - 170));
    window.parent.postMessage({
      isStreamlitMessage: true,
      type: "streamlit:setFrameHeight",
      height,
    }, "*");
  };

  const escapeHtml = value => String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

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
      notice.innerHTML = "<strong>Waiting for telemetry</strong><span>Start the Wokwi simulation to receive live readings.</span>";
      setText("litres", "—");
      setText("level", "—");
      setText("generator", "—");
      setText("pump", "—");
      setText("runtime", "—");
      setText("sensor-note", "No sensor reading received yet.");
    } else {
      const stale = args.freshness !== "LIVE";
      const theft = args.status === "Suspected theft" || latest.theft_alarm;
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
      const layout = {
        ...(args.chart.layout || {}),
        autosize: true,
        height: window.innerWidth <= 760 ? 430 : 560,
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { color: "#d9e6f2" },
        margin: { l: 42, r: 12, t: 38, b: 32 },
      };
      window.Plotly.react(chart, args.chart.data || [], layout, {
        responsive: true,
        displayModeBar: false,
      });
    } else {
      chart.hidden = true;
      emptyChart.hidden = false;
    }
    setFrameHeight();
  };

  render({
    latest: null,
    status: "Waiting for telemetry",
    explanation: "Start the Wokwi simulation to receive live readings.",
    freshness: "WAITING",
    age_seconds: null,
    chart: null,
    fetch_error: null,
  });

  window.addEventListener("message", event => {
    if (event.data && event.data.type === "streamlit:render") {
      render(event.data.args);
    }
  });
  window.addEventListener("resize", () => {
    setFrameHeight();
    const chart = $("history-chart");
    if (chart._fullLayout && window.Plotly) window.Plotly.Plots.resize(chart);
  });
  window.parent.postMessage({
    isStreamlitMessage: true,
    type: "streamlit:componentReady",
    apiVersion: 1,
  }, "*");
  window.setTimeout(setFrameHeight, 0);
})();
