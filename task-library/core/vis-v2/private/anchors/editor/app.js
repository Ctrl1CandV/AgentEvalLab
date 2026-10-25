const C = window.CONTENT;
const $ = selector => document.querySelector(selector);
const notes = C.notes.map(note => ({ ...note }));
let current = 0;
let dirty = false;

$("#brand").textContent = C.brand;
$("#tagline").textContent = C.tagline;
$("#title-label").textContent = C.labels.title;
$("#body-label").textContent = C.labels.body;
$("#save").textContent = C.labels.save;

const excerpt = body => body.split("\n")[0];
function renderList() {
  $('[data-role="note-list"]').replaceChildren(...notes.map((note, index) => {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.role = "note-item";
    button.className = "note";
    if (index === current) button.setAttribute("aria-current", "true");
    button.innerHTML = '<span class="note-title"></span><span class="note-excerpt"></span>';
    button.children[0].textContent = note.title;
    button.children[1].textContent = excerpt(note.body);
    button.addEventListener("click", () => open(index));
    item.append(button);
    return item;
  }));
}
function setStatus(unsaved) {
  dirty = unsaved;
  const status = $('[data-role="save-status"]');
  status.textContent = unsaved ? C.status.unsaved : C.status.saved;
  status.classList.toggle("unsaved", unsaved);
}
function open(index) {
  current = index;
  $("#title").value = notes[index].title;
  $("#body").value = notes[index].body;
  setStatus(false);
  renderList();
}
for (const field of ["#title", "#body"]) $(field).addEventListener("input", () => setStatus(true));
$("#editor").addEventListener("submit", event => {
  event.preventDefault();
  notes[current] = { title: $("#title").value, body: $("#body").value };
  setStatus(false);
  renderList();
});
document.addEventListener("keydown", event => {
  if ((event.metaKey || event.ctrlKey) && event.key === "s") { event.preventDefault(); $("#editor").requestSubmit(); }
});
open(0);
