// PulseOps dashboard — vanilla JS, no build step.
// Connects to the server with Socket.IO, gets a live update every
// 2 seconds, and redraws the charts, service cards and incident feed.
// If the WebSocket drops, it falls back to polling /api/* every 5s.
const MAX_POINTS = 30; // keep the last 30 samples (about 1 minute)
const labels = [], cpuData = [], memData = [], netData = [];

function makeChart(id, label, color) {
  return new Chart(document.getElementById(id), {
    type: "line",
    data: { labels, datasets: [{ label, data: [], borderColor: color, backgroundColor: color + "33", fill: true, tension: 0.3, pointRadius: 0 }] },
    options: { responsive: true, animation: false,
      scales: { y: { min: 0, max: 100, ticks: { color: "#9ca3af" }, grid: { color: "#1f2937" } },
                x: { ticks: { color: "#9ca3af", maxTicksLimit: 8 }, grid: { color: "#1f2937" } } },
      plugins: { legend: { labels: { color: "#e5e7eb" } } } },
  });
}
// Network chart needs a bigger Y axis, so patch it after creation.
const cpuChart = makeChart("cpuChart", "CPU %", "#22c55e");
const memChart = makeChart("memChart", "Memory %", "#38bdf8");
const netChart = makeChart("netChart", "Network Mbps", "#f59e0b");
netChart.options.scales.y.max = 300;
const charts = { cpu: cpuChart, mem: memChart, net: netChart };

function pushPoint(chart, value) {
  chart.data.datasets[0].data.push(value);
  if (chart.data.datasets[0].data.length > MAX_POINTS) chart.data.datasets[0].data.shift();
  chart.update("none");
}

function renderServices(services) {
  const healthy = services.filter(s => s.status === "healthy").length;
  document.getElementById("stat-healthy").textContent = healthy + " / " + services.length;
  document.getElementById("services").innerHTML = services.map(s =>
    `<div class="service-row"><span>${s.name} <small style="color:#9ca3af">· ${s.region} · uptime ${s.uptime_pct}%</small></span>` +
    `<span>CPU ${s.cpu}% · MEM ${s.memory}% · <span class="status ${s.status}">${s.status}</span></span></div>`
  ).join("");
}

function renderIncidents(incidents) {
  const open = incidents.filter(i => i.status !== "resolved").length;
  document.getElementById("stat-incidents").textContent = open;
  document.getElementById("incidents").innerHTML = incidents.slice(0, 10).map(i =>
    `<li><span class="badge ${i.severity}">${i.severity}</span><strong>${i.service}</strong> — ${i.title} <small style="color:#9ca3af">(${i.status})</small></li>`
  ).join("") || "<li>No incidents — all quiet.</li>";
}

function onUpdate(data) {
  const m = data.metrics;
  document.getElementById("stat-cpu").textContent = m.cpu;
  document.getElementById("stat-mem").textContent = m.memory;
  document.getElementById("stat-net").textContent = m.network_mbps;
  document.getElementById("stat-rps").textContent = m.requests_per_sec;
  labels.push(new Date(m.timestamp).toLocaleTimeString());
  if (labels.length > MAX_POINTS) labels.shift();
  pushPoint(cpuChart, m.cpu); pushPoint(memChart, m.memory); pushPoint(netChart, m.network_mbps);
  if (data.services) renderServices(data.services);
  if (data.incidents) renderIncidents(data.incidents);
  if (data.log) {
    const el = document.getElementById("logs");
    el.textContent += "\n" + data.log;
    el.scrollTop = el.scrollHeight;
  }
}

function setLive(on) {
  document.getElementById("live-dot").classList.toggle("on", on);
  document.getElementById("live-label").textContent = on ? "Live" : "Reconnecting…";
}

const socket = io();
socket.on("connect", () => setLive(true));
socket.on("disconnect", () => setLive(false));
socket.on("metrics", onUpdate);

// Fallback: if Socket.IO never connects, poll the REST API instead.
setInterval(async () => {
  if (socket.connected) return;
  try {
    const [m, s, i] = await Promise.all([
      fetch("/api/metrics").then(r => r.json()),
      fetch("/api/services").then(r => r.json()),
      fetch("/api/incidents").then(r => r.json()),
    ]);
    onUpdate({ metrics: m, services: s, incidents: i });
  } catch (e) { /* server down — keep trying */ }
}, 5000);

setInterval(() => {
  document.getElementById("clock").textContent = new Date().toLocaleTimeString();
}, 1000);
