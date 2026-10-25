const C = window.CONTENT;
const $ = selector => document.querySelector(selector);
const ICONS = { xlsx: "#1f9d6b", zip: "#c58a12", pdf: "#d1492e", md: "#5b4bd6" };
$("#brand").textContent = C.brand;
$("#title").textContent = C.title;
$("#empty-heading").textContent = C.empty.heading;
$("#empty-body").textContent = C.empty.body;
$("#empty-action").textContent = C.empty.action;
$("#error-heading").textContent = C.error.heading;
$("#error-body").textContent = C.error.body;
$("#retry").textContent = C.error.action;
$("#files").replaceChildren(...C.files.map(file => {
  const item = document.createElement("li");
  const extension = file.name.split(".").pop();
  item.innerHTML = '<span class="icon" aria-hidden="true"></span><span class="name"></span><span class="meta"></span>';
  item.querySelector(".icon").textContent = extension.toUpperCase();
  item.querySelector(".icon").style.background = ICONS[extension] ?? "#64748b";
  item.querySelector(".name").textContent = file.name;
  item.querySelector(".meta").textContent = `${file.size} · modified ${new Date(file.modified + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}`;
  return item;
}));
const STATES = ["empty", "error", "loaded"];
function show(name) {
  for (const state of STATES) $(`[data-role="state-${state}"]`).hidden = state !== name;
  document.querySelectorAll(".state-nav a").forEach(link => link.toggleAttribute("aria-current", link.hash === `#${name}`));
}
function fromHash() {
  const name = location.hash.slice(1);
  $("#loading").hidden = true;
  $("#retry").disabled = false;
  show(STATES.includes(name) ? name : "loaded");
}
$("#retry").addEventListener("click", () => {
  $("#retry").disabled = true;
  $("#loading").hidden = false;
  setTimeout(() => {
    history.replaceState(null, "", "#loaded");
    fromHash();
  }, C.retryDelayMs);
});
window.addEventListener("hashchange", fromHash);
fromHash();
