
const $ = (id) => document.getElementById(id);
const api = {
  list: (tag, text) => fetch(`/resources?${new URLSearchParams({ tag: tag || "", text: text || "" })}`).then(r => r.json()),
  add: (b) => fetch("/resources", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) }).then(r => r.json()),
  edit: (id, b) => fetch(`/resources/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) }).then(r => r.json()),
  del: (id) => fetch(`/resources/${id}`, { method: "DELETE" }).then(r => r.json()),
  exp: (fmt) => fetch(`/export?fmt=${fmt}`).then(r => r.text()),
  imp: (payload, fmt, mode) => fetch("/import", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ payload, fmt, mode }) }).then(r => r.json()),
};

function formBody() {
  return { title: $("f-title").value, url: $("f-url").value, tags: $("f-tags").value.split(",").map(s => s.trim()).filter(Boolean), notes: $("f-notes").value };
}
function setMsg(text, ok = true) { const m = $("form-msg"); m.textContent = text; m.className = "msg " + (ok ? "ok" : "err"); }

async function refresh() {
  const data = await api.list($("q-tag").value, $("q-text").value);
  const ul = $("list"); ul.innerHTML = "";
  $("empty").hidden = data.resources.length !== 0;
  for (const r of data.resources) {
    const li = document.createElement("li");
    li.innerHTML = `<div class="item"><strong>${r.id}. ${escapeHtml(r.title)}</strong>
      <a href="${escapeHtml(r.url)}" target="_blank" rel="noopener">${escapeHtml(r.url)}</a>
      <div class="tags">${r.tags.map(t => `<span class="tag">${escapeHtml(t)}</span>`).join("")}</div></div>`;
    const btns = document.createElement("div"); btns.className = "row";
    const e = document.createElement("button"); e.textContent = "Edit"; e.onclick = () => load(r);
    const d = document.createElement("button"); d.textContent = "Delete"; d.onclick = async () => { await api.del(r.id); refresh(); };
    btns.append(e, d); li.append(btns); ul.append(li);
  }
}
function escapeHtml(s) { return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function load(r) { $("f-id").value = r.id; $("f-title").value = r.title; $("f-url").value = r.url; $("f-tags").value = r.tags.join(", "); $("f-notes").value = r.notes || ""; setMsg("Edit #" + r.id); }

$("res-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const id = $("f-id").value, body = formBody();
  const res = id ? await api.edit(id, body) : await api.add(body);
  if (res.ok) { setMsg((id ? "Updated #" : "Added #") + res.resource.id); $("res-form").reset(); $("f-id").value = ""; refresh(); }
  else setMsg("Validation failed: " + res.errors.map(e => `${e.field}:${e.code}`).join(", "), false);
});
$("reset").onclick = () => { $("res-form").reset(); $("f-id").value = ""; setMsg(""); };
$("do-filter").onclick = refresh;
$("exp-json").onclick = async () => download("resources.json", await api.exp("json"), "application/json");
$("exp-csv").onclick = async () => download("resources.csv", await api.exp("csv"), "text/csv");
$("imp-file").addEventListener("change", async (ev) => {
  const f = ev.target.files[0]; if (!f) return;
  const fmt = f.name.endsWith(".csv") ? "csv" : "json";
  const res = await api.imp(await f.text(), fmt, $("imp-mode").value);
  setMsg(res.ok ? `Import succeeded +${res.added}/~${res.updated}` : "Import failed: " + res.errors.map(e => e.code).join(", "), res.ok);
  refresh();
});
function download(name, text, type) {
  const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; a.click();
}
refresh();
