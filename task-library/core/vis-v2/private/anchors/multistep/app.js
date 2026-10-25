const C = window.CONTENT;
const $ = selector => document.querySelector(selector);
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
let step = 1;

$("#brand").textContent = C.brand;
$("#title").textContent = C.title;
$("#name-label").textContent = C.fields.name;
$("#email-label").textContent = C.fields.email;
$("#back").textContent = C.buttons.back;
$("#next").textContent = C.buttons.next;
$("#submit").textContent = C.buttons.submit;
C.steps.forEach((name, index) => {
  $(`#legend-${index + 1}`).textContent = name;
  const item = document.createElement("li");
  item.innerHTML = '<span class="dot"></span><span class="name"></span>';
  item.children[1].textContent = name;
  $("#steps").append(item);
});
C.plans.forEach((plan, index) => {
  const option = document.createElement("div");
  option.className = "plan";
  option.innerHTML = `<input type="radio" name="plan" id="plan-${index}" aria-describedby="plan-note-${index}"><label for="plan-${index}"></label><p id="plan-note-${index}"></p>`;
  option.querySelector("input").value = plan;
  option.querySelector("input").checked = index === 0;
  option.querySelector("label").textContent = plan;
  option.querySelector("p").textContent = C.planNotes[plan];
  $("#plans").append(option);
});

function show(next) {
  step = next;
  document.querySelectorAll(".step").forEach(section => { section.hidden = Number(section.dataset.step) !== step; });
  $('[data-role="step-indicator"]').textContent = `Step ${step} of ${C.steps.length} · ${C.steps[step - 1]}`;
  [...$("#steps").children].forEach((item, index) => {
    item.classList.toggle("done", index + 1 < step);
    item.classList.toggle("current", index + 1 === step);
  });
  $("#back").hidden = step === 1;
  $("#next").hidden = step === C.steps.length;
  $("#submit").hidden = step !== C.steps.length;
  if (step === C.steps.length) {
    const plan = document.querySelector('input[name="plan"]:checked').value;
    const summary = $('[data-role="review-summary"]');
    summary.replaceChildren();
    for (const [term, value] of [[C.fields.name, $("#name").value.trim()], [C.fields.email, $("#email").value.trim()], ["Plan", plan]]) {
      const dt = document.createElement("dt"), dd = document.createElement("dd");
      dt.textContent = term; dd.textContent = value;
      summary.append(dt, dd);
    }
  }
}
function fail(message) {
  const error = $('[data-role="form-error"]');
  error.textContent = message;
  error.hidden = false;
  $("#email").setAttribute("aria-invalid", "true");
  $("#email").focus();
}
$("#next").addEventListener("click", () => {
  if (step === 1) {
    if (!$("#name").value.trim() || !EMAIL.test($("#email").value.trim())) return fail(C.states.error);
    $('[data-role="form-error"]').hidden = true;
    $("#email").removeAttribute("aria-invalid");
  }
  show(step + 1);
});
$("#back").addEventListener("click", () => show(step - 1));
$("#form").addEventListener("submit", event => {
  event.preventDefault();
  const success = $('[data-role="form-success"]');
  success.textContent = C.states.success;
  success.hidden = false;
  $("#back").hidden = true;
  $("#submit").hidden = true;
  $("#steps").lastElementChild.classList.add("done");
});
show(1);
