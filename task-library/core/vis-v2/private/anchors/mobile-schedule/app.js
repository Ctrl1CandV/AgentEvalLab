const C = window.CONTENT;
const $ = selector => document.querySelector(selector);
const saved = new Set();
let day = 0;
const STAR = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z"/></svg>';
$("#brand").textContent = C.brand;
$("#venue").textContent = C.venue;

C.days.forEach((entry, index) => {
  const tab = document.createElement("button");
  tab.type = "button";
  tab.role = "tab";
  tab.id = `tab-${index}`;
  tab.dataset.role = "day-tab";
  tab.setAttribute("aria-controls", `panel-${index}`);
  tab.textContent = entry.label;
  tab.addEventListener("click", () => select(index));
  tab.addEventListener("keydown", event => {
    if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
      const next = (index + (event.key === "ArrowRight" ? 1 : C.days.length - 1)) % C.days.length;
      select(next);
      document.getElementById(`tab-${next}`).focus();
    }
  });
  $("#tabs").append(tab);
  const panel = document.createElement("section");
  panel.id = `panel-${index}`;
  panel.role = "tabpanel";
  panel.setAttribute("aria-labelledby", tab.id);
  const list = document.createElement("ol");
  list.className = "sessions";
  entry.sessions.forEach((session, position) => {
    const key = `${index}:${position}`;
    const item = document.createElement("li");
    item.className = "session";
    item.dataset.role = "session";
    item.innerHTML = `<time></time><div class="info"><h2></h2><p class="room"></p></div><button type="button" class="fav" data-role="favourite-button" aria-pressed="false">${STAR}</button>`;
    item.querySelector("time").textContent = session.time;
    item.querySelector("h2").textContent = session.title;
    item.querySelector(".room").textContent = session.room;
    const button = item.querySelector(".fav");
    button.setAttribute("aria-label", `Save ${session.title}`);
    button.addEventListener("click", () => {
      saved.has(key) ? saved.delete(key) : saved.add(key);
      button.setAttribute("aria-pressed", String(saved.has(key)));
      item.classList.toggle("is-saved", saved.has(key));
      count();
    });
    list.append(item);
  });
  panel.append(list);
  $("#panels").append(panel);
});
function count() { $('[data-role="saved-count"]').textContent = C.savedFormat.replace("{n}", saved.size); }
function select(index) {
  day = index;
  document.querySelectorAll('[role="tab"]').forEach((tab, position) => {
    tab.setAttribute("aria-selected", String(position === day));
    tab.tabIndex = position === day ? 0 : -1;
  });
  document.querySelectorAll('[role="tabpanel"]').forEach((panel, position) => { panel.hidden = position !== day; });
}
select(0);
count();
