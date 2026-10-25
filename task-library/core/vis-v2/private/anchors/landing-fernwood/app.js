const C = window.CONTENT;
const $ = selector => document.querySelector(selector);
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const ART = [
  '<path d="M60 40 h80 a18 18 0 0 1 18 18 v92 a18 18 0 0 1 -18 18 h-80 a18 18 0 0 1 -18 -18 v-92 a18 18 0 0 1 18 -18z" fill="#a35d3a"/><rect x="64" y="70" width="72" height="44" rx="10" fill="#c47a52"/><path d="M78 40 c0 -22 44 -22 44 0" stroke="#3b2a1f" stroke-width="8" fill="none"/><circle cx="100" cy="134" r="6" fill="#3b2a1f"/>',
  '<path d="M100 30 l50 26 l14 104 h-128 l14 -104z" fill="#3f6f73"/><path d="M100 30 v130" stroke="#2b4d50" stroke-width="5"/><path d="M50 56 l-24 70 h20 M150 56 l24 70 h-20" stroke="#2b4d50" stroke-width="10" stroke-linecap="round" fill="none"/><circle cx="100" cy="70" r="5" fill="#e8dcc6"/><circle cx="100" cy="100" r="5" fill="#e8dcc6"/>',
  '<ellipse cx="100" cy="150" rx="62" ry="12" fill="#55603f"/><rect x="70" y="96" width="60" height="50" rx="8" fill="#6d6d6a"/><path d="M100 96 c-18 -22 6 -36 0 -58 c22 18 26 40 0 58z" fill="#e48a3a"/><path d="M100 96 c-8 -10 2 -18 0 -28 c10 8 12 18 0 28z" fill="#f5c96a"/><path d="M56 146 l-14 18 M144 146 l14 18 M100 146 v20" stroke="#3b3b38" stroke-width="7" stroke-linecap="round"/>',
];
$("#brand").textContent = C.brand;
$("#hero-heading").textContent = C.hero.heading;
$("#hero-sub").textContent = C.hero.subheading;
$("#hero-cta").textContent = C.hero.cta;
$("#product-grid").replaceChildren(...C.products.map((product, index) => {
  const card = document.createElement("article");
  card.className = "card";
  card.dataset.role = "product-card";
  card.innerHTML = `<svg viewBox="0 0 200 180" aria-hidden="true">${ART[index % ART.length]}</svg><div class="card-body"><div class="card-head"><h3></h3><p class="price"></p></div><p class="description"></p></div>`;
  card.querySelector("h3").textContent = product.name;
  card.querySelector(".price").textContent = product.price;
  card.querySelector(".description").textContent = product.description;
  return card;
}));
const N = C.newsletter;
$("#newsletter-title").textContent = N.heading;
$("#email-label").textContent = N.emailLabel;
$("#interest-label").textContent = N.interestLabel;
$("#interest").append(...N.interests.map(name => new Option(name, name.toLowerCase())));
$("#subscribe").textContent = N.button;
$("#footer").textContent = C.footer;
const error = $('[data-role="form-error"]'), success = $('[data-role="form-success"]');
$("#newsletter-form").addEventListener("submit", event => {
  event.preventDefault();
  const email = $("#email");
  const valid = EMAIL.test(email.value.trim());
  error.hidden = valid;
  success.hidden = !valid;
  email.toggleAttribute("aria-invalid", !valid);
  if (valid) { success.textContent = N.success; error.textContent = ""; }
  else { error.textContent = N.error; success.textContent = ""; email.focus(); }
});
