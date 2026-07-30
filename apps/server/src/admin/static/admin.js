(function () {
  'use strict';

  let metricsData = null;
  let pollTimer = null;

  // DOM refs
  const $ = (id) => document.getElementById(id);

  // Tab switching
  document.querySelectorAll('.tab').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.querySelectorAll('.tab').forEach(function (t) { t.classList.remove('active'); });
      document.querySelectorAll('.tab-content').forEach(function (c) { c.classList.remove('active'); });
      btn.classList.add('active');
      var tab = btn.getAttribute('data-tab');
      document.getElementById('tab-' + tab).classList.add('active');
    });
  });

  // Chart instances
  var charts = {};

  function initChart(id, type, label, color, fill) {
    var ctx = document.getElementById(id);
    if (!ctx) return null;
    charts[id] = new Chart(ctx, {
      type: type,
      data: {
        labels: [],
        datasets: [{
          label: label,
          data: [],
          borderColor: color,
          backgroundColor: fill || color + '33',
          borderWidth: 2,
          fill: !!fill,
          tension: 0.2,
          pointRadius: 0,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 300 },
        scales: {
          x: { display: false },
          y: {
            beginAtZero: true,
            ticks: {
              color: '#8b949e',
              font: { size: 10 },
              maxTicksLimit: 5,
            },
            grid: { color: '#30363d33' },
          }
        },
        plugins: {
          legend: { display: false },
        },
      }
    });
  }

  // Initialize charts
  initChart('overviewLLMChart', 'line', 'LLM Latency', '#58a6ff', true);
  initChart('overviewSystemChart', 'line', 'CPU', '#3fb950', true);
  initChart('llmLatencyChart', 'line', 'Latency (ms)', '#58a6ff', true);
  initChart('llmTPSChart', 'line', 'Tokens/s', '#d29922', true);
  initChart('audioLatencyChart', 'line', 'Pipeline (ms)', '#f0883e', true);
  initChart('systemResourceChart', 'line', '%', '#58a6ff', true);

  // Helper: format number
  function fmt(v, d) { return (v != null && v !== undefined) ? Number(v).toFixed(d || 0) : '--'; }

  // Update overview cards
  function updateOverview(d) {
    var ac = d && d.aircraft ? d.aircraft.count || 0 : 0;
    var ctrl = d && d.controllers ? d.controllers.count || 0 : 0;
    var llm = d && d.llm || {};
    var audio = d && d.audio || {};
    var sys = d && d.system || {};
    var http = d && d.http || {};

    $('ovAircraft').textContent = ac;
    $('ovControllers').textContent = ctrl;
    $('ovLLMLatency').textContent = llm.average_latency_ms ? fmt(llm.average_latency_ms, 0) + 'ms' : '--';
    $('ovAudioLatency').textContent = audio.average_total_ms ? fmt(audio.average_total_ms, 0) + 'ms' : '--';
    $('ovCPU').textContent = sys.cpu_percent != null ? fmt(sys.cpu_percent, 0) + '%' : '--';
    $('ovRAM').textContent = sys.memory_percent != null ? fmt(sys.memory_percent, 0) + '%' : '--';
    $('ovHTTP').textContent = http.total_requests != null ? fmt(http.total_requests) : '--';
    $('ovUptime').textContent = sys.uptime_seconds ? fmt(sys.uptime_seconds / 3600, 1) + 'h' : '--';
  }

  // Update LLM tab
  function updateLLM(llm) {
    if (!llm) return;
    $('llmAvgLatency').textContent = llm.average_latency_ms ? fmt(llm.average_latency_ms, 0) + 'ms' : '--';
    $('llmAvgTPS').textContent = llm.average_tokens_per_sec ? fmt(llm.average_tokens_per_sec, 1) : '--';
    $('llmTotal').textContent = llm.total_requests != null ? fmt(llm.total_requests) : '--';
    $('llmModel').textContent = llm.model || '--';
  }

  // Update audio tab
  function updateAudio(audio) {
    if (!audio) return;
    $('audSTT').textContent = audio.average_stt_ms ? fmt(audio.average_stt_ms, 0) + 'ms' : '--';
    $('audTTS').textContent = audio.average_tts_ms ? fmt(audio.average_tts_ms, 0) + 'ms' : '--';
    $('audTotal').textContent = audio.average_total_ms ? fmt(audio.average_total_ms, 0) + 'ms' : '--';
    $('audPackets').textContent = audio.total_packets != null ? fmt(audio.total_packets) : '--';
  }

  // Update system tab
  function updateSystem(sys) {
    if (!sys) return;
    $('sysCPU').textContent = sys.cpu_percent != null ? fmt(sys.cpu_percent, 0) + '%' : '--';
    $('sysRAM').textContent = sys.memory_percent != null ? fmt(sys.memory_percent, 0) + '%' : '--';
    $('sysOllama').textContent = sys.ollama_connected ? 'Connected' : 'Disconnected';
    $('sysOllama').style.color = sys.ollama_connected ? '#3fb950' : '#f85149';
    $('sysWS').textContent = sys.active_websocket_connections != null ? fmt(sys.active_websocket_connections) : '--';
  }

  // Update aircraft table
  function updateAircraft(aircraft) {
    var tbody = $('aircraftBody');
    $('acCount').textContent = aircraft ? aircraft.count || 0 : 0;
    if (!aircraft || !aircraft.aircraft || !aircraft.aircraft.length) {
      tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:#8b949e;">No active aircraft</td></tr>';
      return;
    }
    var html = '';
    aircraft.aircraft.forEach(function (a) {
      var pos = a.position || {};
      var mot = a.motion || {};
      var rad = a.radios || {};
      var lat = pos.lat != null ? Number(pos.lat).toFixed(2) : '--';
      var lon = pos.lon != null ? Number(pos.lon).toFixed(2) : '--';
      var alt = pos.alt_msl_ft != null ? fmt(pos.alt_msl_ft) : '--';
      var gs = mot.groundspeed_kn != null ? fmt(mot.groundspeed_kn) : '--';
      var hdg = pos.heading_mag != null ? fmt(pos.heading_mag, 0) : '--';
      var com1 = rad.com1_freq_mhz != null ? rad.com1_freq_mhz.toFixed(3) : '--';
      var sqk = rad.transponder_code || '--';
      var lastSeen = a.last_seen_ago_s != null ? fmt(a.last_seen_ago_s, 0) + 's' : '--';
      html += '<tr><td>' + esc(a.callsign) + '</td><td>' + lat + '</td><td>' + lon + '</td><td>' + alt + '</td><td>' + gs + '</td><td>' + hdg + '</td><td>' + com1 + '</td><td>' + sqk + '</td><td>' + lastSeen + '</td></tr>';
    });
    tbody.innerHTML = html;
  }

  // Update controller table
  function updateControllers(controllers) {
    $('ctrlCount').textContent = controllers ? controllers.count || 0 : 0;
    $('wsConnCount').textContent = controllers ? controllers.websocket_connections || 0 : 0;
    var tbody = $('controllerBody');
    if (!controllers || !controllers.controllers || !controllers.controllers.length) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#8b949e;">No controllers active</td></tr>';
      return;
    }
    var html = '';
    controllers.controllers.forEach(function (c) {
      var cls = c.status === 'online' ? 'status-online' : 'status-offline';
      var uptime = c.uptime_seconds ? fmt(c.uptime_seconds / 3600, 1) + 'h' : '--';
      html += '<tr><td>' + esc(c.position) + '</td><td>' + esc(c.callsign) + '</td><td>' + c.frequency_mhz.toFixed(3) + '</td><td>' + esc(c.airport_icao || '--') + '</td><td class="' + cls + '">' + c.status + '</td><td>' + c.active_aircraft_count + '</td><td>' + uptime + '</td></tr>';
    });
    tbody.innerHTML = html;
  }

  function esc(s) {
    if (!s) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  // Update charts with latest data
  function updateCharts(d) {
    var llm = d && d.llm || {};
    var audio = d && d.audio || {};
    var sys = d && d.system || {};

    // Helper: push sample to chart
    function pushToChart(id, samples, key) {
      var ch = charts[id];
      if (!ch || !samples || !samples.length) return;
      var labels = samples.map(function (s) {
        var t = s.t ? s.t.slice(11, 19) : '';
        return t;
      });
      var values = samples.map(function (s) { return s.v; });
      ch.data.labels = labels;
      ch.data.datasets[0].data = values;
      ch.update('none');
    }

    pushToChart('overviewLLMChart', llm.latency_samples, 'v');
    pushToChart('llmLatencyChart', llm.latency_samples, 'v');
    pushToChart('llmTPSChart', llm.tps_samples, 'v');
    pushToChart('audioLatencyChart', audio.pipeline_samples, 'v');

    // System resource chart: combine CPU + RAM
    var sysCh = charts['systemResourceChart'];
    if (sysCh) {
      if (sys.cpu_percent != null) {
        var now = new Date().toLocaleTimeString();
        sysCh.data.labels.push(now);
        sysCh.data.datasets[0].data.push(sys.cpu_percent);
        // Add RAM data if dataset exists
        if (sysCh.data.datasets.length < 2) {
          sysCh.data.datasets.push({
            label: 'RAM',
            data: [],
            borderColor: '#d29922',
            backgroundColor: '#d2992233',
            borderWidth: 2,
            fill: true,
            tension: 0.2,
            pointRadius: 0,
          });
        }
        sysCh.data.datasets[1].data.push(sys.memory_percent);
        // Keep last 60 points
        if (sysCh.data.labels.length > 60) {
          sysCh.data.labels.shift();
          sysCh.data.datasets[0].data.shift();
          sysCh.data.datasets[1].data.shift();
        }
        sysCh.update('none');
      }
    }

    // Overview system chart (CPU only)
    var ovSysCh = charts['overviewSystemChart'];
    if (ovSysCh && sys.cpu_percent != null) {
      var now2 = new Date().toLocaleTimeString();
      ovSysCh.data.labels.push(now2);
      ovSysCh.data.datasets[0].data.push(sys.cpu_percent);
      if (ovSysCh.data.labels.length > 60) {
        ovSysCh.data.labels.shift();
        ovSysCh.data.datasets[0].data.shift();
      }
      ovSysCh.update('none');
    }
  }

  // Fetch all data
  function fetchAll() {
    var base = '/api/v1/admin';

    Promise.all([
      fetch(base + '/metrics').then(function (r) { return r.json(); }).catch(function () { return null; }),
      fetch(base + '/aircraft').then(function (r) { return r.json(); }).catch(function () { return null; }),
      fetch(base + '/controllers').then(function (r) { return r.json(); }).catch(function () { return null; }),
    ]).then(function (results) {
      metricsData = results[0];
      var aircraft = results[1];
      var controllers = results[2];

      updateOverview(metricsData);
      if (metricsData) {
        updateLLM(metricsData.llm);
        updateAudio(metricsData.audio);
        updateSystem(metricsData.system);
        updateCharts(metricsData);
      }
      updateAircraft(aircraft);
      updateControllers(controllers);

      $('lastUpdate').textContent = new Date().toLocaleTimeString();
    });
  }

  // SSE event stream for live updates
  function connectSSE() {
    var evtSource = new EventSource('/api/v1/admin/events');
    evtSource.onmessage = function (e) {
      try {
        var data = JSON.parse(e.data);
        metricsData = data;
        updateOverview(data);
        updateLLM(data.llm);
        updateAudio(data.audio);
        updateSystem(data.system);
        updateCharts(data);
        $('lastUpdate').textContent = new Date().toLocaleTimeString();
      } catch (err) { /* ignore parse errors */ }
    };
    evtSource.onerror = function () {
      // SSE connection lost -> fall back to polling
      evtSource.close();
      pollTimer = setInterval(fetchAll, 5000);
    };
    return evtSource;
  }

  // Init: try SSE, fall back to polling
  var sse = connectSSE();
  // Also poll aircraft/controllers separately (these are not in SSE)
  setInterval(function () {
    fetch('/api/v1/admin/aircraft').then(function (r) { return r.json(); }).then(updateAircraft).catch(function () {});
    fetch('/api/v1/admin/controllers').then(function (r) { return r.json(); }).then(updateControllers).catch(function () {});
  }, 5000);

  // Initial fetch
  fetchAll();

})();
