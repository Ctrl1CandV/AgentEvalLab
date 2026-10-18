// Renders a static frontend submission in headless Chromium for the visual judging step (PLAN-005 WP6).
// Runs inside the bubblewrap sandbox: node render_frontend.mjs <playwright-core dir> <site dir> <output dir> <states json>
// Writes desktop.png, phone.png, form-error.png and form-success.png when it can, and render.json with objective
// measurements. Candidate JavaScript runs in the page, so the sandbox, not this script, provides isolation.
import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const [playwrightDirectory, site, output, statesJson] = process.argv.slice(2);
const { chromium } = await import(pathToFileURL(join(playwrightDirectory, "index.mjs")).href);
const states = JSON.parse(statesJson);
const MAX_HEIGHT = 2600;
const result = { screenshots: {}, overflow: {}, rolesPresent: [], formStates: {}, errors: [] };
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM, args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"] });
const url = pathToFileURL(join(site, "index.html")).href;

async function capture(name, viewport) {
  const page = await browser.newPage({ viewport, deviceScaleFactor: 1 });
  try {
    await page.goto(url, { waitUntil: "load", timeout: 15_000 });
    await page.waitForTimeout(300);
    const size = await page.evaluate(() => ({ width: document.documentElement.scrollWidth, height: document.documentElement.scrollHeight }));
    result.overflow[name] = size.width > viewport.width;
    const height = Math.min(size.height, MAX_HEIGHT);
    await page.screenshot({ path: join(output, `${name}.png`), clip: { x: 0, y: 0, width: viewport.width, height } });
    result.screenshots[name] = { file: `${name}.png`, width: viewport.width, height, pageHeight: size.height };
    return page;
  } catch (error) {
    result.errors.push(`${name}: ${error instanceof Error ? error.message.split("\n")[0] : "render failed"}`);
    await page.close();
    return null;
  }
}

async function formShot(page, name, expected) {
  const form = page.locator("[data-role=signup-form]").first();
  if (await form.count() === 0) { result.errors.push(`${name}: no signup-form`); return; }
  await form.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  result.formStates[name] = await page.evaluate(text => document.body.innerText.includes(text), expected);
  await form.screenshot({ path: join(output, `${name}.png`) });
  result.screenshots[name] = { file: `${name}.png` };
}

async function submit(form) {
  const button = form.locator("button[type=submit], input[type=submit], button:not([type])").first();
  if (await button.count()) await button.click({ timeout: 5_000 });
  else await form.evaluate(element => element.requestSubmit ? element.requestSubmit() : element.submit());
}

const desktop = await capture("desktop", { width: 1440, height: 900 });
const phone = await capture("phone", { width: 390, height: 844 });
if (phone) await phone.close();
if (desktop) {
  try {
    result.rolesPresent = await desktop.evaluate(() => [...new Set([...document.querySelectorAll("[data-role]")].map(element => element.getAttribute("data-role")))].sort());
    const form = desktop.locator("[data-role=signup-form]").first();
    if (await form.count()) {
      await submit(form);
      await desktop.waitForTimeout(400);
      await formShot(desktop, "form-error", states.error);
      const fill = async (selector, action) => { const field = form.locator(selector).first(); if (await field.count()) await action(field); };
      await fill("[name=title]", field => field.fill("The Left Hand of Darkness"));
      await fill("select[name=district]", async field => {
        const values = await field.locator("option").evaluateAll(options => options.map(option => option.value).filter(Boolean));
        if (values.length) await field.selectOption(values[0]);
      });
      await fill("[name=email]", field => field.fill("reader@example.com"));
      await fill("input[name=condition]", field => field.check());
      await submit(form);
      await desktop.waitForTimeout(400);
      await formShot(desktop, "form-success", states.success);
    } else result.errors.push("form: no signup-form");
  } catch (error) {
    result.errors.push(`form: ${error instanceof Error ? error.message.split("\n")[0] : "interaction failed"}`);
  }
  await desktop.close();
}
await browser.close();
await writeFile(join(output, "render.json"), JSON.stringify(result, null, 2));
