const C = window.CONTENT;
const $ = selector => document.querySelector(selector);
let yearly = false;
$("#brand").textContent = C.brand;
$("#nav-cta").textContent = C.cta;
$("#hero-heading").textContent = C.hero.heading;
$("#hero-sub").textContent = C.hero.subheading;
$("#label-monthly").textContent = C.billing.monthly;
$("#label-yearly").textContent = C.billing.yearly;
$("#billing-note").textContent = C.billing.note;
$("#plan-list").replaceChildren(...C.plans.map((plan, index) => {
  const card = document.createElement("article");
  card.className = "plan" + (index === 1 ? " featured" : "");
  card.dataset.role = "plan-card";
  card.innerHTML = `${index === 1 ? '<p class="badge">Most popular</p>' : ""}<h3></h3><p class="price-line"><span class="price" data-role="plan-price"></span><span class="per"></span></p><ul></ul><a class="cta" href="#plans"></a>`;
  card.querySelector("h3").textContent = plan.name;
  card.querySelector("ul").append(...plan.features.map(feature => Object.assign(document.createElement("li"), { textContent: feature })));
  card.querySelector(".cta").textContent = C.cta;
  return card;
}));
function render() {
  document.querySelectorAll('[data-role="plan-card"]').forEach((card, index) => {
    const price = C.plans[index].monthly * (yearly ? C.yearlyMultiple : 1);
    card.querySelector(".price").textContent = `${C.currency}${price}`;
    card.querySelector(".per").textContent = yearly ? "per year" : "per month";
  });
  $("#toggle").setAttribute("aria-checked", String(yearly));
  $("#label-monthly").classList.toggle("active", !yearly);
  $("#label-yearly").classList.toggle("active", yearly);
  $("#billing-note").classList.toggle("visible", yearly);
}
$("#toggle").addEventListener("click", () => { yearly = !yearly; render(); });
render();
