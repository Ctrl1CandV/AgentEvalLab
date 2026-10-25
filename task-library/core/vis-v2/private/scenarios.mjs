// The functional checks of VIS v2, run in the sandbox: node scenarios.mjs <playwright-core dir> <site dir> <brief> <content.json> <out dir>
// Opens <site dir>/index.html from its files in headless Chromium and runs the brief's scenario. Writes <out dir>/checks.json
// ({check: {passed, detail}}) and the screenshots the judges see (<out dir>/<name>.png, listed in <out dir>/screenshots.json).
// Candidate JavaScript runs in the page, so the sandbox, not this script, isolates it.
import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const [playwrightDirectory, site, brief, contentPath, out] = process.argv.slice(2);
const MAX_SHOT_HEIGHT = 4_000;
const { chromium } = await import(pathToFileURL(join(playwrightDirectory, "index.mjs")).href);
const content = JSON.parse(await readFile(contentPath, "utf8"));
const results = {};
const record = (check, passed, detail = "") => { results[check] = { passed: Boolean(passed), detail: String(detail).slice(0, 300) }; };
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM, args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"] });
const url = pathToFileURL(join(site, "index.html")).href;

async function open(viewport, hash = "") {
  const page = await browser.newPage({ viewport, deviceScaleFactor: 1 });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  // Offline: anything but the page's own files is refused.
  await page.route("**/*", route => route.request().url().startsWith("file://") ? route.continue() : route.abort());
  await page.goto(url + hash, { waitUntil: "load", timeout: 15_000 });
  await page.waitForTimeout(250);
  return { page, errors };
}
const role = (page, name) => page.locator(`[data-role="${name}"]`);
const visibleText = async locator => (await locator.count()) ? (await locator.first().innerText()).replace(/\s+/g, " ").trim() : "";
const numberIn = text => { const match = String(text).replace(/,/g, "").match(/-?\d+(\.\d+)?/); return match ? Number(match[0]) : NaN; };
const settle = page => page.waitForTimeout(200);
// A click or a radio choice as a user makes it; if a decorative layer (a card-wide label, a sticky header) intercepts
// the pointer, the element's own click() is used instead, so the checks test the page's behaviour, not hit-testing.
async function press(locator) {
  try { await locator.click({ timeout: 4_000 }); } catch { await locator.evaluate(element => element.click(), undefined, { timeout: 4_000 }); }
}
async function choose(locator) {
  try { await locator.check({ timeout: 4_000 }); } catch { await locator.evaluate(element => element.click(), undefined, { timeout: 4_000 }); }
}
const shots = [];
/** A screenshot for the judges: the full page up to MAX_SHOT_HEIGHT, or one element. Never fails a check. */
async function shot(page, name, element = null) {
  try {
    if (element) await element.first().screenshot({ path: join(out, `${name}.png`), timeout: 5_000 });
    else {
      const { width } = page.viewportSize();
      const height = Math.min(MAX_SHOT_HEIGHT, await page.evaluate(() => Math.max(document.documentElement.scrollHeight, window.innerHeight)));
      await page.screenshot({ path: join(out, `${name}.png`), fullPage: true, clip: { x: 0, y: 0, width, height }, timeout: 10_000 });
    }
    shots.push(name);
  } catch { /* a missing screenshot shows as missing to the judges */ }
}

async function common(roles, hash = "") {
  // Loads, roles present, labels, no horizontal overflow at either width; the desktop and phone screenshots.
  try {
    const { page, errors } = await open({ width: 1440, height: 900 }, hash);
    const missing = [];
    for (const name of roles) if (await role(page, name).count() === 0) missing.push(name);
    record("renders", errors.length === 0 && missing.length === 0, errors.length ? `script errors: ${errors[0]}` : missing.length ? `missing roles: ${missing.join(", ")}` : "");
    const unlabelled = await page.evaluate(() => [...document.querySelectorAll("input:not([type=hidden]):not([type=submit]):not([type=button]), select, textarea")]
      .filter(element => element.offsetParent !== null || element.getClientRects().length)
      .filter(element => !(element.labels && element.labels.length) && !element.getAttribute("aria-label") && !element.getAttribute("aria-labelledby"))
      .map(element => element.outerHTML.slice(0, 60)));
    record("labels", unlabelled.length === 0, unlabelled.join(" | "));
    const wide = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    await shot(page, "desktop");
    await page.close();
    const phone = await open({ width: 390, height: 844 }, hash);
    const narrow = await phone.page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    await shot(phone.page, "phone");
    await phone.page.close();
    record("no-overflow", !wide && !narrow, `${wide ? "scrolls at 1440 " : ""}${narrow ? "scrolls at 390" : ""}`);
  } catch (error) {
    for (const check of ["renders", "labels", "no-overflow"]) if (!results[check]) record(check, false, error.message.split("\n")[0]);
  }
}

const SCENARIOS = {
  async dashboard() {
    await common(["kpi-total", "kpi-delayed", "region-filter", "shipments-table", "chart"]);
    const { page } = await open({ width: 1440, height: 900 });
    const rows = page.locator('[data-role="shipments-table"] tbody tr');
    const delayed = content.shipments.filter(row => row.status === "Delayed").length;
    record("kpis", numberIn(await visibleText(role(page, "kpi-total"))) === content.shipments.length && numberIn(await visibleText(role(page, "kpi-delayed"))) === delayed
      && await rows.count() === content.shipments.length, `${await visibleText(role(page, "kpi-total"))} / ${await visibleText(role(page, "kpi-delayed"))} / ${await rows.count()} rows`);
    const region = content.regions[2];
    await role(page, "region-filter").selectOption({ label: region });
    await settle(page);
    const own = content.shipments.filter(row => row.region === region);
    const shown = await rows.allInnerTexts();
    record("filter", shown.length === own.length && own.every(row => shown.some(text => text.includes(row.id)))
      && numberIn(await visibleText(role(page, "kpi-total"))) === own.length
      && numberIn(await visibleText(role(page, "kpi-delayed"))) === own.filter(row => row.status === "Delayed").length, `${shown.length} rows for ${region}`);
    const box = await role(page, "chart").first().boundingBox();
    record("chart", box && box.width >= 200 && box.height >= 120, box ? `${Math.round(box.width)}x${Math.round(box.height)}` : "not visible");
    await page.close();
  },
  async editor() {
    await common(["note-list", "note-item", "note-title", "note-body", "save-button", "save-status"]);
    const { page } = await open({ width: 1440, height: 900 });
    const second = content.notes[1];
    await press(role(page, "note-item").nth(1));
    await settle(page);
    record("open-note", await role(page, "note-title").inputValue() === second.title && (await role(page, "note-body").inputValue()).trim() === second.body.trim(),
      await role(page, "note-title").inputValue());
    await role(page, "note-title").fill("Renamed in the editor");
    await settle(page);
    record("unsaved", (await visibleText(role(page, "save-status"))).includes(content.status.unsaved), await visibleText(role(page, "save-status")));
    await shot(page, "unsaved");
    await press(role(page, "save-button"));
    await settle(page);
    record("save", (await visibleText(role(page, "save-status"))).includes(content.status.saved) && (await role(page, "note-item").nth(1).innerText()).includes("Renamed in the editor"),
      await visibleText(role(page, "save-status")));
    await page.close();
  },
  async multistep() {
    await common(["step-indicator", "next-button", "back-button", "submit-button", "review-summary", "form-error", "form-success"]);
    const { page } = await open({ width: 1440, height: 900 });
    const step = async () => numberIn(await visibleText(role(page, "step-indicator")));
    await page.getByLabel(content.fields.name, { exact: true }).fill("Ada Lovelace");
    await page.getByLabel(content.fields.email, { exact: true }).fill("not-an-email");
    await press(role(page, "next-button"));
    await settle(page);
    const errorShown = (await visibleText(role(page, "form-error"))).includes(content.states.error) && await role(page, "form-error").first().isVisible();
    record("validation", errorShown && await step() === 1, `step ${await step()}, error ${errorShown}`);
    await shot(page, "error");
    await page.getByLabel(content.fields.email, { exact: true }).fill("ada@example.com");
    await press(role(page, "next-button"));
    await settle(page);
    await choose(page.getByLabel(content.plans[1], { exact: true }));
    await press(role(page, "next-button"));
    await settle(page);
    const summary = await visibleText(role(page, "review-summary"));
    await shot(page, "review");
    record("review", await step() === 3 && ["Ada Lovelace", "ada@example.com", content.plans[1]].every(value => summary.includes(value)), summary);
    await press(role(page, "back-button"));
    await settle(page);
    record("navigation", await step() === 2 && await page.getByLabel(content.plans[1], { exact: true }).isChecked(), `step ${await step()}`);
    await press(role(page, "next-button"));
    await settle(page);
    await press(role(page, "submit-button"));
    await settle(page);
    record("submit", (await visibleText(role(page, "form-success"))).includes(content.states.success) && await role(page, "form-success").first().isVisible(), await visibleText(role(page, "form-success")));
    await page.close();
  },
  async "landing-fernwood"() {
    await common(["hero", "product-card", "newsletter-form", "form-error", "form-success"]);
    const { page } = await open({ width: 1440, height: 900 });
    const text = (await page.innerText("body")).replace(/\s+/g, " ");
    const missing = [content.hero.heading, content.hero.subheading, ...content.products.map(product => product.name)].filter(copy => !text.includes(copy));
    record("copy", missing.length === 0 && await role(page, "product-card").count() === content.products.length, missing.join(" | "));
    const form = role(page, "newsletter-form");
    const options = await form.locator("select option").evaluateAll(list => list.filter(option => option.value !== "").map(option => option.textContent.trim()));
    record("options", JSON.stringify(options) === JSON.stringify(content.newsletter.interests), JSON.stringify(options));
    await form.getByLabel(content.newsletter.emailLabel, { exact: true }).fill("hiker@example");
    await form.locator("select").first().selectOption({ label: content.newsletter.interests[0] });
    await press(form.locator("button[type=submit], button:not([type])").first());
    await settle(page);
    const success = async () => (await visibleText(role(page, "form-success"))).includes(content.newsletter.success) && await role(page, "form-success").first().isVisible();
    record("form-invalid", (await visibleText(role(page, "form-error"))).includes(content.newsletter.error) && !(await success()), "after hiker@example");
    await shot(page, "form-error", form);
    await form.getByLabel(content.newsletter.emailLabel, { exact: true }).fill("hiker@example.com");
    await press(form.locator("button[type=submit], button:not([type])").first());
    await settle(page);
    record("form-valid", await success(), "after hiker@example.com");
    await shot(page, "form-success", form);
    await page.close();
  },
  async "landing-quanta"() {
    await common(["billing-toggle", "plan-card", "plan-price"]);
    const { page } = await open({ width: 1440, height: 900 });
    const prices = async () => (await role(page, "plan-price").allInnerTexts()).map(numberIn);
    const monthly = content.plans.map(plan => plan.monthly);
    record("prices-monthly", JSON.stringify(await prices()) === JSON.stringify(monthly), JSON.stringify(await prices()));
    await press(role(page, "billing-toggle").first());
    await settle(page);
    record("prices-yearly", JSON.stringify(await prices()) === JSON.stringify(monthly.map(price => price * content.yearlyMultiple)), JSON.stringify(await prices()));
    await shot(page, "yearly");
    await press(role(page, "billing-toggle").first());
    await settle(page);
    record("toggle-back", JSON.stringify(await prices()) === JSON.stringify(monthly), JSON.stringify(await prices()));
    const text = (await page.innerText("body")).replace(/\s+/g, " ");
    record("copy", [content.hero.heading, ...content.plans.map(plan => plan.name)].every(copy => text.includes(copy)) && await role(page, "plan-card").count() === content.plans.length);
    await page.close();
  },
  async "mobile-schedule"() {
    await common(["day-tab", "session", "favourite-button", "saved-count"]);
    const { page } = await open({ width: 390, height: 844 });
    const visibleSessions = async () => (await role(page, "session").evaluateAll(list => list.filter(element => element.offsetParent !== null).map(element => element.innerText)));
    await press(role(page, "day-tab").nth(1));
    await settle(page);
    const day2 = await visibleSessions();
    record("tabs", day2.length === content.days[1].sessions.length && content.days[1].sessions.every(session => day2.some(text => text.includes(session.title))), `${day2.length} sessions`);
    const button = page.locator('[data-role="session"]:visible [data-role="favourite-button"]').first();
    await press(button);
    await settle(page);
    const pressed = await button.getAttribute("aria-pressed");
    const count = numberIn(await visibleText(role(page, "saved-count")));
    await shot(page, "phone-saved");
    await press(button);
    await settle(page);
    record("favourite", pressed === "true" && count === 1 && numberIn(await visibleText(role(page, "saved-count"))) === 0 && await button.getAttribute("aria-pressed") === "false",
      `aria-pressed ${pressed}, count ${count}`);
    const small = await page.locator('[data-role="favourite-button"]:visible').evaluateAll(list => list.map(element => element.getBoundingClientRect()).filter(box => box.width < 24 || box.height < 24).length);
    record("touch-targets", small === 0, `${small} favourite buttons under 24x24`);
    await page.close();
  },
  async catalogue() {
    await common(["search-input", "genre-filter", "results-count", "books-table", "sort-year"]);
    const { page } = await open({ width: 1440, height: 900 });
    const rows = page.locator('[data-role="books-table"] tbody tr');
    const count = async () => numberIn(await visibleText(role(page, "results-count")));
    await role(page, "search-input").fill("the");
    await settle(page);
    const bySearch = content.books.filter(book => book.title.toLowerCase().includes("the"));
    record("search", await rows.count() === bySearch.length && await count() === bySearch.length, `${await rows.count()} rows, count ${await count()}, expected ${bySearch.length}`);
    await role(page, "search-input").fill("");
    const genre = content.genres[1];
    await role(page, "genre-filter").selectOption({ label: genre });
    await settle(page);
    const byGenre = content.books.filter(book => book.genre === genre);
    record("genre", await rows.count() === byGenre.length && await count() === byGenre.length, `${await rows.count()} rows for ${genre}`);
    await role(page, "search-input").fill("AN");
    await settle(page);
    const both = byGenre.filter(book => book.title.toLowerCase().includes("an"));
    record("combined", await rows.count() === both.length, `${await rows.count()} rows, expected ${both.length}`);
    await role(page, "search-input").fill("");
    await role(page, "genre-filter").selectOption({ index: 0 });
    await press(role(page, "sort-year").first());
    await settle(page);
    const years = (await rows.allInnerTexts()).map(text => Number((text.match(/\b(1[5-9]\d\d|20\d\d)\b/) ?? [])[0]));
    record("sort", years.length === content.books.length && years.every((year, index) => index === 0 || years[index - 1] <= year), years.slice(0, 5).join(","));
    await page.close();
  },
  async states() {
    await common(["state-empty", "state-error", "state-loaded", "retry-button"], "#loaded");
    const shows = async (page, name, copy) => await role(page, name).count() > 0 && await role(page, name).first().isVisible() && (await visibleText(role(page, name))).includes(copy);
    const others = async (page, name) => { for (const other of ["state-empty", "state-error", "state-loaded"]) if (other !== name && await role(page, other).count() && await role(page, other).first().isVisible()) return false; return true; };
    for (const [check, hash, name, copy] of [["empty", "#empty", "state-empty", content.empty.heading], ["error", "#error", "state-error", content.error.heading],
      ["loaded", "#loaded", "state-loaded", content.files[0].name]]) {
      const { page } = await open({ width: 1440, height: 900 }, hash);
      record(check, await shows(page, name, copy) && await others(page, name), hash);
      if (check !== "loaded") await shot(page, check);
      if (check === "error") {
        await press(role(page, "retry-button").first());
        await page.waitForTimeout(content.retryDelayMs + 400);
        const listed = await visibleText(role(page, "state-loaded"));
        record("retry", await shows(page, "state-loaded", content.files[0].name) && content.files.every(file => listed.includes(file.name)) && await others(page, "state-loaded"), listed.slice(0, 80));
      }
      await page.close();
    }
  },
};

try {
  if (!SCENARIOS[brief]) throw new Error(`unknown brief ${brief}`);
  await SCENARIOS[brief]();
} catch (error) {
  results.__error = { passed: false, detail: error.message.split("\n")[0] };
}
await browser.close();
await writeFile(join(out, "checks.json"), JSON.stringify(results, null, 1));
await writeFile(join(out, "screenshots.json"), JSON.stringify(shots));
