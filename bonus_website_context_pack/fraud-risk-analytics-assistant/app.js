const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
let currentColumns = [];
let currentRows = [];

function renderTable(columns, rows) {
  const table = $(".results table");
  table.innerHTML = `<thead><tr>${columns.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${rows.length ? rows.map((row) => `<tr>${row.map((value, i) => `<td>${columns[i]?.toLowerCase() === "review priority" ? `<span class="priority">${esc(value)}</span>` : esc(value)}</td>`).join("")}</tr>`).join("") : `<tr><td colspan="${Math.max(columns.length,1)}">No records matched this question.</td></tr>`}</tbody>`;
}

function renderChart(rows) {
  const chart = $(".chart");
  if (!rows.length) { chart.innerHTML = "<p>No chart available for this result.</p>"; return; }
  const points = rows.slice(0, 12).map((row, index) => ({
    label: String(row[0] ?? index + 1).slice(-5),
    value: row.slice(1).map((v) => Number(String(v).replace(/[^0-9.-]/g,""))).find(Number.isFinite) ?? 0,
  }));
  const max = Math.max(...points.map((p) => Math.abs(p.value)), 1);
  chart.innerHTML = points.map((p) => `<div class="barwrap" title="${esc(p.label)}: ${esc(p.value)}"><i class="bar" style="height:${Math.max(7,Math.round(Math.abs(p.value)/max*92))}%"></i><small>${esc(p.label)}</small></div>`).join("");
}

function filters() {
  return Object.fromEntries([...document.querySelectorAll("[data-filter]")].map((input) => [input.dataset.filter,input.value.trim()]).filter(([,v]) => v && !v.startsWith("All ")));
}

async function runQuery() {
  const question = $("#question").value.trim();
  const message = $("#query-message");
  const button = $("#run-query");
  if (!question) { message.textContent = "Enter a question first."; message.className = "query-message error"; $("#question").focus(); return; }
  button.disabled = true; button.textContent = "Working…";
  message.textContent = "Creating and checking a safe query…"; message.className = "query-message";
  try {
    const response = await fetch("/api/query", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question,filters:filters()})});
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || payload.error || "The request could not be completed safely.");
    currentColumns = payload.columns || [];
    currentRows = Array.isArray(payload.rows) ? payload.rows : (payload.data || []);
    const isSample = payload.status === "validated_sample";
    $("#answer").classList.remove("hidden");
    $("#status").textContent = "Validated"; $("#status").className = "status";
    $("#row-count").textContent = payload.row_count ?? currentRows.length;
    $("#data-source").textContent = payload.source || "Approved Gold analytics";
    $("#result-kind").textContent = isSample ? "Local sample result" : "Live Snowflake result";
    $("#sqlstatus").textContent = isSample ? "Validated local sample" : "Validated server-side";
    $(".sql pre").textContent = payload.sql || "Validated SQL was not returned.";
    $(".sql").open = true;
    $("#download-csv").disabled = false;
    $("#answer-title").textContent = payload.title || "Query results";
    renderTable(currentColumns,currentRows); renderChart(currentRows);
    message.textContent = `Answer ready · ${currentRows.length} row${currentRows.length === 1 ? "" : "s"} returned`;
    setTimeout(() => $("#answer").scrollIntoView({behavior:"smooth",block:"start"}), 100);
  } catch (error) {
    message.textContent = error.message; message.className = "query-message error";
    $("#status").textContent = "Safe error"; $("#status").className = "status error";
  } finally { button.disabled = false; button.textContent = "Get answer"; }
}

function downloadCsv() {
  if (!currentColumns.length) { $("#query-message").textContent = "Run a question before downloading results."; return; }
  const quote = (v) => `"${String(v ?? "").replace(/"/g,'""')}"`;
  const csv = [currentColumns,...currentRows].map((row) => row.map(quote).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"}));
  const link = document.createElement("a"); link.href=url; link.download="filtered-fraud-risk-results.csv"; link.click(); URL.revokeObjectURL(url);
}

async function copySql() {
  const sql = $(".sql pre").textContent.trim();
  if (!sql) return;
  try {
    await navigator.clipboard.writeText(sql);
  } catch (_) {
    const box = document.createElement("textarea"); box.value = sql; document.body.append(box); box.select(); document.execCommand("copy"); box.remove();
  }
  $("#copy-status").textContent = "Copied";
  setTimeout(() => { $("#copy-status").textContent = ""; }, 1800);
}

async function loadFreshness() {
  try {
    const response = await fetch("/api/freshness");
    const payload = await response.json();
    if (!response.ok) throw new Error();
    $("#data-freshness").textContent = payload.latest_transaction_date || "No data available";
  } catch (_) {
    $("#data-freshness").textContent = "Unavailable";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  $("#run-query").addEventListener("click",runQuery);
  $("#question").addEventListener("keydown",(event)=>{if(event.key==="Enter")runQuery();});
  document.querySelectorAll("[data-question]").forEach((button)=>button.addEventListener("click",()=>{$("#question").value=button.dataset.question;runQuery();}));
  $("#download-csv").addEventListener("click",downloadCsv);
  $("#copy-sql").addEventListener("click",copySql);
  loadFreshness();
});
