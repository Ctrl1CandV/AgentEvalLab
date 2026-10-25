const C = window.CONTENT;
const $ = selector => document.querySelector(selector);
const STATUSES = ["On time", "Delayed", "Delivered"];
const statusClass = status => status.toLowerCase().replace(/\s+/g, "-");
const formatDate = iso => new Date(iso + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short" });

$("#brand").textContent = C.brand;
$("#title").textContent = C.title;
$("#kpi-total-label").textContent = C.kpis.total;
$("#kpi-delayed-label").textContent = C.kpis.delayed;
$("#chart-title").textContent = C.chartTitle;
const select = $("#region");
select.append(new Option(C.allRegions, ""), ...C.regions.map(region => new Option(region, region)));

function drawChart(rows) {
  const svg = $('[data-role="chart"]');
  svg.querySelectorAll("g").forEach(node => node.remove());
  const counts = STATUSES.map(status => rows.filter(row => row.status === status).length);
  const max = Math.max(1, ...counts);
  const ns = "http://www.w3.org/2000/svg";
  const group = document.createElementNS(ns, "g");
  STATUSES.forEach((status, index) => {
    const y = 18 + index * 54, width = Math.round((counts[index] / max) * 270);
    const label = document.createElementNS(ns, "text");
    label.setAttribute("x", 0); label.setAttribute("y", y + 22); label.setAttribute("class", "chart-label"); label.textContent = status;
    const track = document.createElementNS(ns, "rect");
    track.setAttribute("x", 96); track.setAttribute("y", y + 6); track.setAttribute("width", 270); track.setAttribute("height", 26); track.setAttribute("rx", 4); track.setAttribute("class", "chart-track");
    const bar = document.createElementNS(ns, "rect");
    bar.setAttribute("x", 96); bar.setAttribute("y", y + 6); bar.setAttribute("width", Math.max(width, 2)); bar.setAttribute("height", 26); bar.setAttribute("rx", 4); bar.setAttribute("class", `chart-bar ${statusClass(status)}`);
    const value = document.createElementNS(ns, "text");
    value.setAttribute("x", 380); value.setAttribute("y", y + 24); value.setAttribute("class", "chart-value"); value.textContent = counts[index];
    group.append(label, track, bar, value);
  });
  svg.append(group);
  $("#chart-desc").textContent = STATUSES.map((status, index) => `${status}: ${counts[index]}`).join(", ");
}

function render() {
  const region = select.value;
  const rows = region ? C.shipments.filter(row => row.region === region) : C.shipments;
  const delayed = rows.filter(row => row.status === "Delayed").length;
  $('[data-role="kpi-total"]').textContent = rows.length;
  $('[data-role="kpi-delayed"]').textContent = delayed;
  $("#kpi-total-note").textContent = region ? `in the ${region} region` : `across ${C.regions.length} regions`;
  $("#kpi-delayed-note").textContent = rows.length ? `${Math.round((delayed / rows.length) * 100)}% of shipments shown` : "no shipments shown";
  $("#breakdown").replaceChildren(...C.regions.map(name => {
    const item = document.createElement("li");
    item.className = name === region ? "current" : "";
    item.innerHTML = "<span></span><b></b>";
    item.children[0].textContent = name;
    item.children[1].textContent = C.shipments.filter(row => row.region === name).length;
    return item;
  }));
  $("#delayed-meter").style.width = `${rows.length ? (delayed / rows.length) * 100 : 0}%`;
  $("#late-list").replaceChildren(...rows.filter(row => row.status === "Delayed").slice(0, 4).map(row => {
    const item = document.createElement("li");
    item.textContent = `${row.id} · ${row.region} · due ${formatDate(row.eta)}`;
    return item;
  }));
  const body = $('[data-role="shipments-table"] tbody');
  body.replaceChildren(...rows.map(row => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<th scope="row"></th><td></td><td><span class="pill"></span></td><td></td><td class="num"></td>`;
    tr.children[0].textContent = row.id;
    tr.children[1].textContent = row.region;
    const pill = tr.querySelector(".pill");
    pill.textContent = row.status;
    pill.classList.add(statusClass(row.status));
    tr.children[3].textContent = formatDate(row.eta);
    tr.children[4].textContent = `${row.weightKg.toLocaleString("en-GB")} kg`;
    return tr;
  }));
  drawChart(rows);
}
select.addEventListener("change", render);
render();
