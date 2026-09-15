/* Recruiting Funnel Dashboard.
 *
 * This file draws; it does not calculate. Every figure it renders was computed
 * by recruiting_funnel.metrics and written to data/dashboard.json at build
 * time, including one pre-computed slice per filter value. A KPI is therefore
 * defined in exactly one place, and the browser cannot disagree with the
 * spreadsheet or the weekly deck about what "time to fill" means.
 */

const REPO_URL = "https://github.com/Gantaaa/recruiting-funnel-dashboard";
const SVG_NS = "http://www.w3.org/2000/svg";

const state = { payload: null, slice: null, funnelMode: "funnel" };

/* ---------------------------------------------------------------- helpers */

const $ = (selector) => document.querySelector(selector);

const fmtInt = (n) => (n == null ? "—" : Number(n).toLocaleString("en-US"));
const fmtPct = (n, digits = 1) =>
  n == null ? "—" : `${(n * 100).toFixed(digits)}%`;
const fmtDays = (n) => (n == null ? "—" : `${Math.round(n)}`);

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else if (key === "html") node.innerHTML = value;
    else if (key === "text") node.textContent = value;
    else if (value !== null && value !== undefined) node.setAttribute(key, value);
  }
  for (const child of [].concat(children)) {
    if (child) node.appendChild(child);
  }
  return node;
}

function svgEl(tag, attrs = {}) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value !== null && value !== undefined) node.setAttribute(key, value);
  }
  return node;
}

/** A rect whose data-end corners are rounded and whose baseline end is square. */
function barPath(x, y, width, height, radius, side) {
  const r = Math.max(0, Math.min(radius, side === "right" ? width : height));
  if (side === "right") {
    return `M${x},${y} H${x + width - r} A${r},${r} 0 0 1 ${x + width},${y + r}` +
      ` V${y + height - r} A${r},${r} 0 0 1 ${x + width - r},${y + height} H${x} Z`;
  }
  return `M${x},${y + r} A${r},${r} 0 0 1 ${x + r},${y} H${x + width - r}` +
    ` A${r},${r} 0 0 1 ${x + width},${y + r} V${y + height} H${x} Z`;
}

/* --------------------------------------------------------------- tooltips */

const tooltip = () => $("#tooltip");

function showTooltip(event, title, rows) {
  const node = tooltip();
  node.innerHTML = "";
  node.appendChild(el("strong", { text: title }));
  for (const row of rows) {
    node.appendChild(el("div", { class: "t-row", text: row }));
  }
  node.hidden = false;
  moveTooltip(event);
}

function moveTooltip(event) {
  const node = tooltip();
  const pad = 14;
  const box = node.getBoundingClientRect();
  let x = event.clientX + pad;
  let y = event.clientY + pad;
  if (x + box.width > window.innerWidth - 8) x = event.clientX - box.width - pad;
  if (y + box.height > window.innerHeight - 8) y = event.clientY - box.height - pad;
  node.style.left = `${Math.max(8, x)}px`;
  node.style.top = `${Math.max(8, y)}px`;
}

function hideTooltip() {
  tooltip().hidden = true;
}

/** Attach hover/focus tooltip behaviour to a chart mark. */
function bindTooltip(node, title, rows) {
  node.addEventListener("mouseenter", (e) => showTooltip(e, title, rows));
  node.addEventListener("mousemove", moveTooltip);
  node.addEventListener("mouseleave", hideTooltip);
  node.setAttribute("tabindex", "0");
  node.setAttribute("role", "img");
  node.setAttribute("aria-label", `${title}. ${rows.join(". ")}`);
  node.addEventListener("focus", (e) => {
    const box = node.getBoundingClientRect();
    showTooltip(
      { clientX: box.left + box.width / 2, clientY: box.top },
      title,
      rows
    );
  });
  node.addEventListener("blur", hideTooltip);
}

/* ------------------------------------------------------------- stat tiles */

function renderTiles() {
  const { kpis } = state.slice;
  const trend = state.slice.weekly_trend || [];
  const recent = trend.slice(-4).reduce((sum, w) => sum + w.hires, 0);
  const prior = trend.slice(-8, -4).reduce((sum, w) => sum + w.hires, 0);
  const hiresDelta = recent - prior;

  const tiles = [
    {
      label: "Open requisitions",
      value: fmtInt(kpis.open_requisitions),
      meta: `${fmtInt(kpis.filled_requisitions)} filled this period`,
    },
    {
      label: "Hires",
      value: fmtInt(kpis.total_hires),
      meta: `${fmtInt(kpis.hires_last_30_days)} in the last 30 days`,
      delta: hiresDelta,
      deltaLabel: `${hiresDelta >= 0 ? "+" : ""}${hiresDelta} vs prior 4 weeks`,
      deltaGood: hiresDelta >= 0,
    },
    {
      label: "Avg time to fill",
      value: fmtDays(kpis.avg_time_to_fill),
      unit: "days",
      meta: `Median ${fmtDays(kpis.median_time_to_fill)} days`,
    },
    {
      label: "Offer acceptance",
      value: fmtPct(kpis.offer_acceptance_rate, 0),
      meta: "Offers accepted ÷ extended",
    },
    {
      label: "Applied → hired",
      value: fmtPct(kpis.funnel_conversion_rate, 1),
      meta: `${fmtInt(state.slice.dataset.candidates)} candidates`,
    },
    {
      label: "Requisition fill rate",
      value: fmtPct(kpis.requisition_fill_rate, 0),
      meta: `${fmtInt(state.slice.dataset.requisitions)} requisitions`,
    },
  ];

  const container = $("#tiles");
  container.innerHTML = "";
  for (const tile of tiles) {
    const value = el("div", { class: "tile-value", text: tile.value });
    if (tile.unit) value.appendChild(el("span", { class: "tile-unit", text: ` ${tile.unit}` }));

    const meta = el("div", { class: "tile-meta" });
    if (tile.delta !== undefined && tile.delta !== 0) {
      meta.appendChild(
        el("span", {
          class: `tile-delta ${tile.deltaGood ? "up" : "down"}`,
          text: `${tile.deltaGood ? "▲" : "▼"} ${tile.deltaLabel}`,
        })
      );
    } else {
      meta.textContent = tile.meta;
    }

    container.appendChild(
      el("div", { class: "tile" }, [
        el("div", { class: "tile-label", text: tile.label }),
        value,
        meta,
      ])
    );
  }
}

/* ----------------------------------------------------------- funnel chart */

function renderFunnel() {
  const stages = state.slice[state.funnelMode];
  const host = $("#funnel-chart");
  host.innerHTML = "";

  const rowHeight = 46;
  const gap = 10;
  const labelWidth = 74;
  const valueWidth = 128;
  const width = 900;
  const plotWidth = width - labelWidth - valueWidth;
  const height = stages.length * (rowHeight + gap);

  const svg = svgEl("svg", {
    viewBox: `0 0 ${width} ${height}`,
    role: "img",
    "aria-label": "Hiring funnel by stage",
  });

  const max = Math.max(...stages.map((s) => s.count)) || 1;
  const steps = ["--step-1", "--step-2", "--step-3", "--step-4", "--step-5"];

  stages.forEach((stage, index) => {
    const y = index * (rowHeight + gap);
    const barWidth = Math.max(2, (stage.count / max) * plotWidth);
    const group = svgEl("g", { class: "row-group" });

    group.appendChild(
      svgEl("text", {
        x: 0, y: y + rowHeight / 2 + 4, class: "series-label",
      })
    ).textContent = stage.stage;

    const bar = svgEl("path", {
      d: barPath(labelWidth, y, barWidth, rowHeight, 4, "right"),
      fill: `var(${steps[index]})`,
      class: "bar",
    });
    group.appendChild(bar);

    const count = svgEl("text", {
      x: labelWidth + barWidth + 10,
      y: y + rowHeight / 2 + 5,
      class: "value-label",
    });
    count.textContent = fmtInt(stage.count);
    group.appendChild(count);

    if (stage.conversion_from_previous != null) {
      const conv = svgEl("text", {
        x: labelWidth + barWidth + 10 + 52,
        y: y + rowHeight / 2 + 5,
        class: "tick-label",
      });
      conv.textContent = `${fmtPct(stage.conversion_from_previous, 1)} of previous`;
      group.appendChild(conv);
    }

    const hit = svgEl("rect", {
      x: labelWidth, y, width: plotWidth, height: rowHeight, class: "hit",
    });
    bindTooltip(hit, stage.stage, [
      `${fmtInt(stage.count)} candidates reached this stage`,
      stage.conversion_from_previous != null
        ? `${fmtPct(stage.conversion_from_previous, 1)} of the previous stage`
        : "Top of funnel",
    ]);
    group.appendChild(hit);

    svg.appendChild(group);
  });

  host.appendChild(svg);

  const corrected = state.slice.funnel;
  const legacy = state.slice.funnel_legacy;
  const note = $("#funnel-note");
  if (state.funnelMode === "funnel_legacy") {
    const lost = corrected[1].count - legacy[1].count;
    note.textContent =
      `This is how the original spreadsheet counted the funnel: it read each candidate's ` +
      `current stage, so everyone who was rejected or withdrew fell back to "Applied" no ` +
      `matter how far they actually got. It hides ${fmtInt(lost)} candidates who reached the ` +
      `screen, and reports applied→screen conversion as ` +
      `${fmtPct(legacy[1].conversion_from_previous, 1)} instead of ` +
      `${fmtPct(corrected[1].conversion_from_previous, 1)}.`;
    note.hidden = false;
  } else {
    note.textContent =
      `A candidate counts toward every stage they reached, evidenced by that stage's date, ` +
      `rather than only the stage they ended on. Someone rejected after an onsite still ` +
      `interviewed onsite.`;
    note.hidden = false;
  }
}

/* ------------------------------------------------- weekly small multiples */

/* `kind` distinguishes a flow (events counted within each week, which sums and
   belongs on a zero baseline) from a stock (a level measured at each week end,
   which does not sum and would be squashed against the top of a zero-based
   axis). Summing a stock is how a dashboard ends up reporting "300 open
   requisitions" for a team that has nineteen. */
function sparkChart(title, weeks, key, unit, color, kind = "flow") {
  const width = 300;
  const height = 96;
  const padY = 10;
  const values = weeks.map((w) => w[key] ?? 0);
  const high = Math.max(...values, 1);
  const low = kind === "stock" ? Math.min(...values) : 0;
  const span = Math.max(high - low, 1);
  const stepX = width / Math.max(weeks.length - 1, 1);

  const points = values.map((value, index) => [
    index * stepX,
    padY + (1 - (value - low) / span) * (height - padY * 2),
  ]);

  const svg = svgEl("svg", {
    viewBox: `0 0 ${width} ${height}`,
    preserveAspectRatio: "none",
    role: "img",
    "aria-label": `${title}, ${weeks.length} weeks`,
  });

  svg.appendChild(
    svgEl("line", {
      x1: 0, y1: height - padY, x2: width, y2: height - padY, class: "gridline",
    })
  );

  svg.appendChild(
    svgEl("path", {
      d: points.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" "),
      class: "spark-line",
      stroke: color,
    })
  );

  const lastPoint = points[points.length - 1];
  svg.appendChild(
    svgEl("circle", {
      cx: lastPoint[0] - 1.5, cy: lastPoint[1], r: 4,
      fill: color, class: "spark-dot",
    })
  );

  // One hit band per week, wider than the mark, driving a shared crosshair.
  const crosshair = svgEl("line", { class: "crosshair", y1: 0, y2: height, x1: 0, x2: 0 });
  crosshair.style.opacity = "0";
  svg.appendChild(crosshair);

  weeks.forEach((week, index) => {
    const hit = svgEl("rect", {
      x: index * stepX - stepX / 2, y: 0, width: stepX, height, class: "hit",
    });
    hit.addEventListener("mouseenter", () => {
      crosshair.setAttribute("x1", index * stepX);
      crosshair.setAttribute("x2", index * stepX);
      crosshair.style.opacity = "1";
    });
    hit.addEventListener("mouseleave", () => { crosshair.style.opacity = "0"; });
    bindTooltip(hit, `Week ending ${week.week_ending}`, [
      `${title}: ${fmtInt(week[key])}${unit ? ` ${unit}` : ""}`,
    ]);
    svg.appendChild(hit);
  });

  const latest = values[values.length - 1];
  const summary =
    kind === "stock"
      ? `ranged ${fmtInt(Math.min(...values))}–${fmtInt(high)} over 16 weeks`
      : `${fmtInt(values.reduce((a, b) => a + b, 0))} over 16 weeks`;

  return el("div", { class: "sm" }, [
    el("div", { class: "sm-title", text: title }),
    el("div", { class: "sm-value", text: fmtInt(latest) }),
    el("div", { class: "sm-meta", text: `latest week · ${summary}` }),
    (() => { const w = el("div", { class: "chart" }); w.appendChild(svg); return w; })(),
  ]);
}

function renderTrend() {
  const weeks = state.slice.weekly_trend || [];
  const host = $("#trend-charts");
  host.innerHTML = "";
  host.appendChild(sparkChart("Applications", weeks, "applications", "", "var(--series-1)"));
  host.appendChild(sparkChart("Hires", weeks, "hires", "", "var(--series-3)"));
  host.appendChild(
    sparkChart("Open requisitions", weeks, "open_requisitions", "", "var(--series-2)", "stock")
  );
}

/* ------------------------------------------------ horizontal bar (shared) */

function horizontalBars(host, rows, options) {
  const { valueKey, formatValue, subLabel, color, target } = options;
  host.innerHTML = "";

  const usable = rows.filter((r) => r[valueKey] != null);
  if (!usable.length) {
    host.appendChild(el("p", { class: "panel-sub", text: "No data for this selection." }));
    return;
  }

  const rowHeight = 30;
  const gap = 8;
  // Size the label gutter to the longest name so a team like "Customer
  // Success" is not silently clipped. ~6.4px per character at 12.5px.
  const longest = Math.max(...usable.map((r) => String(r.name).length));
  const labelWidth = Math.min(168, Math.max(104, Math.round(longest * 6.4) + 12));
  const valueWidth = 96;
  const width = options.width || 560;
  const plotWidth = width - labelWidth - valueWidth;
  // A target line needs a clear band above the bars for its own label.
  const headerHeight = target ? 16 : 0;
  const height = headerHeight + usable.length * (rowHeight + gap);
  const max = Math.max(...usable.map((r) => r[valueKey]), target || 0) || 1;

  const svg = svgEl("svg", {
    viewBox: `0 0 ${width} ${height}`,
    role: "img",
    "aria-label": options.ariaLabel || "",
  });

  if (target) {
    const x = labelWidth + (target / max) * plotWidth;
    svg.appendChild(
      svgEl("line", {
        x1: x, y1: headerHeight - 4, x2: x, y2: height - gap, class: "target-line",
      })
    );
    const label = svgEl("text", {
      x, y: headerHeight - 9, class: "tick-label", "text-anchor": "middle",
    });
    label.textContent = `${target}-day target`;
    svg.appendChild(label);
  }

  usable.forEach((row, index) => {
    const y = headerHeight + index * (rowHeight + gap);
    const barWidth = Math.max(2, (row[valueKey] / max) * plotWidth);
    const group = svgEl("g", { class: "row-group" });

    const name = svgEl("text", {
      x: 0, y: y + rowHeight / 2 + 4, class: "series-label",
    });
    name.textContent = row.name;
    group.appendChild(name);

    group.appendChild(
      svgEl("path", {
        d: barPath(labelWidth, y, barWidth, rowHeight, 4, "right"),
        fill: typeof color === "function" ? color(row) : color,
        class: "bar",
      })
    );

    const value = svgEl("text", {
      x: labelWidth + barWidth + 9, y: y + rowHeight / 2 + 4, class: "value-label",
    });
    value.textContent = formatValue(row);
    group.appendChild(value);

    const hit = svgEl("rect", {
      x: labelWidth, y, width: plotWidth, height: rowHeight, class: "hit",
    });
    bindTooltip(hit, row.name, subLabel(row));
    group.appendChild(hit);

    svg.appendChild(group);
  });

  host.appendChild(svg);
}

function renderTimeToFill() {
  const rows = [...state.slice.by_department]
    .filter((r) => r.avg_time_to_fill != null)
    .sort((a, b) => b.avg_time_to_fill - a.avg_time_to_fill);

  horizontalBars($("#ttf-chart"), rows, {
    valueKey: "avg_time_to_fill",
    ariaLabel: "Average time to fill by department",
    color: "var(--series-1)",
    target: state.payload.meta.thresholds.time_to_fill_green_max,
    formatValue: (r) => `${fmtDays(r.avg_time_to_fill)} d`,
    subLabel: (r) => [
      `Average ${fmtDays(r.avg_time_to_fill)} days to fill`,
      `Median ${fmtDays(r.median_time_to_fill)} days`,
      `${fmtInt(r.hires)} hires`,
    ],
  });
}

function renderSource() {
  const rows = [...state.slice.by_source]
    .filter((r) => r.candidates > 0)
    .sort((a, b) => (b.conversion || 0) - (a.conversion || 0));

  horizontalBars($("#source-chart"), rows, {
    valueKey: "conversion",
    ariaLabel: "Applicant to hire conversion by source",
    color: "var(--series-1)",
    formatValue: (r) => fmtPct(r.conversion, 1),
    subLabel: (r) => [
      `${fmtInt(r.hires)} hires from ${fmtInt(r.candidates)} applicants`,
      `${fmtPct(r.conversion, 1)} convert to hire`,
    ],
  });
}

function renderHiresBreakdown(hostSelector, key, sortByHires, width) {
  const rows = [...state.slice[key]].filter((r) => r.candidates > 0);
  if (sortByHires) rows.sort((a, b) => b.hires - a.hires);

  horizontalBars($(hostSelector), rows, {
    valueKey: "hires",
    ariaLabel: "Hires by " + key.replace("by_", "").replace("_", " "),
    color: "var(--series-1)",
    width,
    formatValue: (r) => fmtInt(r.hires),
    subLabel: (r) => [
      `${fmtInt(r.hires)} hires from ${fmtInt(r.candidates)} candidates`,
      `${fmtPct(r.conversion, 1)} convert to hire`,
      r.avg_time_to_fill == null
        ? "No completed hires to time"
        : `Average ${fmtDays(r.avg_time_to_fill)} days to fill`,
    ],
  });
}


function renderAging() {
  const buckets = state.slice.aging_buckets;
  // Ageing is a state, not a series: status colours carry it, and every bar is
  // labelled so the colour is never the only cue.
  const tone = { "0-30": "var(--status-good)", "31-60": "var(--status-warning)", "60+": "var(--status-critical)" };
  const rows = Object.entries(buckets).map(([name, count]) => ({
    name: `${name} days`,
    count,
    tone: tone[name],
  }));

  horizontalBars($("#aging-chart"), rows, {
    valueKey: "count",
    ariaLabel: "Open requisitions by age bucket",
    color: (r) => r.tone,
    formatValue: (r) => fmtInt(r.count),
    subLabel: (r) => [`${fmtInt(r.count)} open requisitions in this band`],
  });
}

/* ------------------------------------------------------------- the tables */

function buildTable(caption, headers, rows) {
  const thead = el("thead", {}, [
    el("tr", {}, headers.map((h) =>
      el("th", { class: h.num ? "num" : "", text: h.label, scope: "col" })
    )),
  ]);
  const tbody = el("tbody", {}, rows.map((row) =>
    el("tr", {}, row.map((cell, index) =>
      el("td", {
        class: headers[index].num ? "num" : "",
        ...(cell instanceof Node ? {} : { text: cell }),
      }, cell instanceof Node ? [cell] : [])
    ))
  ));
  return el("table", {}, [el("caption", { text: caption }), thead, tbody]);
}

function renderRiskTable() {
  const rows = state.slice.at_risk_requisitions;
  const host = $("#risk-table");
  host.innerHTML = "";

  if (!rows.length) {
    host.appendChild(
      el("p", { class: "panel-sub", text: "No open requisition has passed 60 days." })
    );
    return;
  }

  host.appendChild(
    buildTable(
      `${rows.length} requisition${rows.length === 1 ? "" : "s"} open past 60 days.`,
      [
        { label: "Requisition" },
        { label: "Department" },
        { label: "Region" },
        { label: "Recruiter" },
        { label: "Days open", num: true },
      ],
      rows.map((r) => {
        const pill = el("span", {
          class: `pill ${r.days_open > 120 ? "pill-critical" : "pill-warning"}`,
          text: fmtInt(r.days_open),
        });
        return [r.requisition_id, r.department, r.region, r.recruiter, pill];
      })
    )
  );
}

function renderQuality() {
  const dq = state.payload.data_quality;
  const host = $("#quality-panel");
  host.innerHTML = "";

  const healthy = dq.errors === 0;
  const stats = [
    { label: "Rows checked", value: fmtInt(dq.rows) },
    { label: "Data health", value: fmtPct(dq.health, 1) },
    { label: "Errors", value: fmtInt(dq.errors) },
    { label: "Warnings", value: fmtInt(dq.warnings) },
  ];

  host.appendChild(
    el("div", { class: "quality-grid" }, stats.map((s) =>
      el("div", { class: "quality-stat" }, [
        el("div", { class: "tile-label", text: s.label }),
        el("div", { class: "tile-value", text: s.value }),
      ])
    ))
  );

  const status = el("p", { class: "panel-note" });
  status.appendChild(
    el("span", {
      class: `pill ${healthy ? "pill-good" : "pill-critical"}`,
      text: healthy ? "All checks passing" : `${dq.errors} issues`,
    })
  );
  status.appendChild(
    document.createTextNode(
      healthy
        ? "  Eleven rules run over the raw CSV before any metric is computed — impossible " +
          "calendar dates, values outside the controlled vocabulary, stage dates running " +
          "backwards, duplicate candidates, and requisitions whose rows disagree about " +
          "their own department, region or status."
        : "  See the repository's data-quality report for the full list."
    )
  );
  host.appendChild(status);
}

function renderDataTable() {
  const host = $("#data-table");
  host.innerHTML = "";

  host.appendChild(
    buildTable(
      "Funnel stages.",
      [{ label: "Stage" }, { label: "Candidates", num: true }, { label: "From previous", num: true }],
      state.slice.funnel.map((s) => [
        s.stage, fmtInt(s.count),
        s.conversion_from_previous == null ? "—" : fmtPct(s.conversion_from_previous, 1),
      ])
    )
  );

  for (const [caption, key] of [
    ["By department.", "by_department"],
    ["By team.", "by_team"],
    ["By region.", "by_region"],
    ["By candidate type.", "by_candidate_type"],
    ["By source.", "by_source"],
    ["By recruiter.", "by_recruiter"],
  ]) {
    host.appendChild(
      buildTable(
        caption,
        [
          { label: "Name" },
          { label: "Candidates", num: true },
          { label: "Hires", num: true },
          { label: "Open reqs", num: true },
          { label: "Avg TTF (days)", num: true },
        ],
        state.slice[key].map((r) => [
          r.name, fmtInt(r.candidates), fmtInt(r.hires), fmtInt(r.open_reqs),
          r.avg_time_to_fill == null ? "—" : fmtDays(r.avg_time_to_fill),
        ])
      )
    );
  }
}

/* ------------------------------------------------------------------ shell */

function currentSliceKey() {
  const department = $("#filter-department").value;
  const region = $("#filter-region").value;
  if (department && region) return { key: null, department, region };
  if (department) return { key: `department:${department}` };
  if (region) return { key: `region:${region}` };
  return { key: "all" };
}

function applyFilters() {
  const choice = currentSliceKey();
  const note = $("#filter-note");

  if (!choice.key) {
    // Only one dimension is pre-computed at a time, so say so rather than
    // silently showing a slice that is not what was asked for.
    note.textContent =
      `Showing ${choice.department} across all regions. Department and region ` +
      `cannot be combined — the dashboard reads pre-computed slices so that no ` +
      `metric is ever recalculated in the browser.`;
    note.hidden = false;
    state.slice = state.payload.slices[`department:${choice.department}`];
  } else {
    note.hidden = true;
    state.slice = state.payload.slices[choice.key];
  }

  renderAll();
}

function renderAll() {
  renderTiles();
  renderFunnel();
  renderTrend();
  renderTimeToFill();
  renderSource();
  renderHiresBreakdown("#team-chart", "by_team", true, 1120);
  renderHiresBreakdown("#candidate-type-chart", "by_candidate_type", false);
  renderAging();
  renderRiskTable();
  renderQuality();
  renderDataTable();
}

function initTheme() {
  const stored = localStorage.getItem("theme");
  if (stored) document.documentElement.setAttribute("data-theme", stored);

  $("#theme-toggle").addEventListener("click", () => {
    const root = document.documentElement;
    const isDark =
      root.getAttribute("data-theme") === "dark" ||
      (!root.hasAttribute("data-theme") &&
        window.matchMedia("(prefers-color-scheme: dark)").matches);
    const next = isDark ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
  });
}

function initControls() {
  const { filters } = state.payload;
  const department = $("#filter-department");
  const region = $("#filter-region");

  for (const value of filters.department) {
    department.appendChild(el("option", { value, text: value }));
  }
  for (const value of filters.region) {
    region.appendChild(el("option", { value, text: value }));
  }

  department.addEventListener("change", () => {
    if (department.value) region.value = "";
    applyFilters();
  });
  region.addEventListener("change", () => {
    if (region.value) department.value = "";
    applyFilters();
  });

  for (const button of document.querySelectorAll("[data-funnel]")) {
    button.addEventListener("click", () => {
      state.funnelMode = button.dataset.funnel;
      for (const other of document.querySelectorAll("[data-funnel]")) {
        other.classList.toggle("is-active", other === button);
      }
      renderFunnel();
    });
  }

  const toggle = $("#table-toggle");
  toggle.addEventListener("click", () => {
    const table = $("#data-table");
    const open = table.hasAttribute("hidden");
    table.toggleAttribute("hidden", !open);
    toggle.setAttribute("aria-expanded", String(open));
    toggle.textContent = open ? "Hide table" : "Show table";
  });
}

async function main() {
  $("#repo-link").href = REPO_URL;

  let payload;
  try {
    const response = await fetch("data/dashboard.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    payload = await response.json();
  } catch (error) {
    $("#main").prepend(
      el("p", {
        class: "filter-note",
        text:
          "Could not load data/dashboard.json. If you are opening this file " +
          "directly from disk, serve the docs/ folder over HTTP instead: " +
          "python3 -m http.server --directory docs",
      })
    );
    return;
  }

  state.payload = payload;
  state.slice = payload.slices.all;

  $("#as-of").textContent = new Date(payload.meta.generated_at + "T00:00:00")
    .toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });
  $("#as-of").setAttribute("datetime", payload.meta.generated_at);
  $("#row-count").textContent =
    `${fmtInt(payload.dataset.candidates)} candidates across ` +
    `${fmtInt(payload.dataset.requisitions)} requisitions · fixed seeded sample`;

  initTheme();
  initControls();
  renderAll();
}

main();
