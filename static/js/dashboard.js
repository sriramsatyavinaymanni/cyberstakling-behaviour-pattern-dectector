"use strict";

(() => {
  const data = window.DASHBOARD_DATA;
  const colors = ["#c3f36b", "#82c9d9", "#ff886f", "#f0ca68", "#b49be8", "#82d3a8"];
  const gridColor = "rgba(151, 166, 157, 0.12)";
  const labelColor = "#86928b";

  function baseOptions() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 500 },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#202a26",
          borderColor: "#3a4740",
          borderWidth: 1,
          titleColor: "#edf1ed",
          bodyColor: "#c5cec8",
          padding: 10,
        },
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: labelColor, maxRotation: 0, autoSkip: true, maxTicksLimit: 8, font: { size: 9 } }, border: { display: false } },
        y: { beginAtZero: true, grid: { color: gridColor }, ticks: { color: labelColor, precision: 0, font: { size: 9 } }, border: { display: false } },
      },
    };
  }

  function makeChart(id, config) {
    const canvas = document.getElementById(id);
    if (canvas && window.Chart) new Chart(canvas, config);
  }

  function renderCharts() {
    if (!data || !window.Chart) return;

    makeChart("messagesChart", {
      type: "bar",
      data: {
        labels: data.daily_counts.map((item) => item.day.slice(5)),
        datasets: [{
          data: data.daily_counts.map((item) => item.count),
          backgroundColor: "rgba(195, 243, 107, .75)",
          borderColor: "#c3f36b",
          borderWidth: 1,
          borderRadius: 2,
          maxBarThickness: 19,
        }],
      },
      options: baseOptions(),
    });

    const byDayAndSender = new Map();
    for (const row of data.logs) {
      const day = row.timestamp.slice(0, 10);
      if (!byDayAndSender.has(day)) byDayAndSender.set(day, new Map());
      const senderCounts = byDayAndSender.get(day);
      senderCounts.set(row.sender_id, (senderCounts.get(row.sender_id) || 0) + 1);
    }
    const senderNames = data.sender_counts.slice(0, 6).map((item) => item.sender);
    const trendDates = [...byDayAndSender.keys()].sort();
    makeChart("contactTrendChart", {
      type: "line",
      data: {
        labels: trendDates.map((day) => day.slice(5)),
        datasets: senderNames.map((sender, index) => ({
          label: sender,
          data: trendDates.map((day) => byDayAndSender.get(day).get(sender) || 0),
          borderColor: colors[index % colors.length],
          backgroundColor: colors[index % colors.length],
          pointRadius: 1.5,
          pointHoverRadius: 4,
          borderWidth: 1.5,
          tension: 0.25,
        })),
      },
      options: {
        ...baseOptions(),
        plugins: {
          ...baseOptions().plugins,
          legend: { display: senderNames.length > 0, position: "bottom", labels: { color: labelColor, boxWidth: 7, boxHeight: 7, padding: 12, font: { size: 8 } } },
        },
      },
    });

    makeChart("senderChart", {
      type: "bar",
      data: {
        labels: data.sender_counts.map((item) => item.sender),
        datasets: [{ data: data.sender_counts.map((item) => item.count), backgroundColor: colors, borderRadius: 2, maxBarThickness: 25 }],
      },
      options: { ...baseOptions(), indexAxis: "y", scales: { x: baseOptions().scales.y, y: { ...baseOptions().scales.x, ticks: { ...baseOptions().scales.x.ticks, autoSkip: false } } } },
    });

    makeChart("platformChart", {
      type: "bar",
      data: {
        labels: data.platform_counts.map((item) => item.platform),
        datasets: [{ data: data.platform_counts.map((item) => item.count), backgroundColor: ["#82c9d9", "#b49be8", "#f0ca68", "#ff886f", "#82d3a8"], borderRadius: 2, maxBarThickness: 28 }],
      },
      options: baseOptions(),
    });

    const riskColors = { "Low concern": "#91b578", "Pattern detected": "#d2c96f", "Elevated indicator": "#e5a661", "High-risk communication pattern": "#e87e6b" };
    const riskChart = document.getElementById("riskChart");
    if (riskChart) {
      const labels = data.risk_distribution.map((item) => item.name);
      new Chart(riskChart, {
        type: "doughnut",
        data: { labels, datasets: [{ data: data.risk_distribution.map((item) => item.count), backgroundColor: labels.map((name) => riskColors[name] || "#82c9d9"), borderColor: "#171f1d", borderWidth: 4, hoverOffset: 3 }] },
        options: { responsive: true, maintainAspectRatio: false, cutout: "72%", plugins: { legend: { display: false }, tooltip: baseOptions().plugins.tooltip } },
      });
      const legend = document.getElementById("riskLegend");
      if (legend) {
        legend.innerHTML = labels.map((name, index) => `<span class="legend-item"><i class="legend-swatch" style="background:${riskColors[name] || colors[index % colors.length]}"></i>${name}</span>`).join("");
      }
    }
  }

  function setupFilters() {
    const body = document.getElementById("logTableBody");
    if (!body) return;
    const filters = {
      search: document.getElementById("searchInput"),
      sender: document.getElementById("senderFilter"),
      receiver: document.getElementById("receiverFilter"),
      date: document.getElementById("dateFilter"),
      platform: document.getElementById("platformFilter"),
      risk: document.getElementById("riskFilter"),
    };
    const rows = [...body.querySelectorAll("tr")];
    const visibleCount = document.getElementById("visibleCount");
    const recordCount = document.getElementById("recordCount");
    const noResults = document.getElementById("noResults");

    function applyFilters() {
      const query = filters.search.value.trim().toLowerCase();
      let visible = 0;
      for (const row of rows) {
        const matches = (!query || row.innerText.toLowerCase().includes(query))
          && (!filters.sender.value || row.dataset.sender === filters.sender.value)
          && (!filters.receiver.value || row.dataset.receiver === filters.receiver.value)
          && (!filters.date.value || row.dataset.timestamp?.startsWith(filters.date.value))
          && (!filters.platform.value || row.dataset.platform === filters.platform.value)
          && (!filters.risk.value || row.dataset.risk === filters.risk.value);
        row.hidden = !matches;
        if (matches) visible += 1;
      }
      if (visibleCount) visibleCount.textContent = `Showing ${visible} record${visible === 1 ? "" : "s"}`;
      if (recordCount) recordCount.textContent = `${visible} / ${rows.length} RECORDS`;
      if (noResults) noResults.hidden = visible > 0;
    }

    for (const control of Object.values(filters)) {
      control.addEventListener(control.tagName === "INPUT" ? "input" : "change", applyFilters);
    }
    document.getElementById("clearFilters")?.addEventListener("click", () => {
      for (const control of Object.values(filters)) control.value = "";
      applyFilters();
    });
    applyFilters();
  }

  document.addEventListener("click", (event) => {
    const closeButton = event.target.closest(".flash-close");
    if (closeButton) closeButton.closest(".flash")?.remove();
  });

  renderCharts();
  setupFilters();
})();
