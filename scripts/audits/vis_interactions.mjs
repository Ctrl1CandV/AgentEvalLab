// Success audit of VIS functional checks (vis-001), from the public task: the page is opened in headless Chromium in
// the sandbox and its form is exercised, where the grader reads the files statically.
//
//   node scripts/audits/vis_interactions.mjs <request.json> <result.json>             (driver, outside the sandbox)
//   node scripts/audits/vis_interactions.mjs --page <playwright> <site> <out> <content> (inside the sandbox)
//
// Units: the three form states shown by interaction (empty on load; error after an empty submission and after an
// invalid email; success after a valid submission), every field labelled at run time with the required options, the
// fixed copy visible, a skip link to existing content, and no horizontal scrolling at 1440 and 390 pixels.
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, readdirSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

if (process.argv[2] === "--page") {
  const [playwrightDirectory, site, output, contentPath] = process.argv.slice(3);
  const { chromium } = await import(pathToFileURL(join(playwrightDirectory, "index.mjs")).href);
  const content = JSON.parse(readFileSync(contentPath, "utf8"));
  const states = content.form.states;
  const result = { errors: [] };
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM, args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"] });
  const url = pathToFileURL(join(site, "index.html")).href;
  const open = async (width, height) => {
    const page = await browser.newPage({ viewport: { width, height } });
    await page.goto(url, { waitUntil: "load", timeout: 15_000 });
    await page.waitForTimeout(300);
    return page;
  };
  const visibleText = page => page.evaluate(() => document.body.innerText);
  const submit = async form => {
    const button = form.locator("button[type=submit], input[type=submit], button:not([type])").first();
    if (await button.count()) {
      try { await button.click({ timeout: 5_000 }); } catch { await button.evaluate(element => element.click()); }
    } else await form.evaluate(element => element.requestSubmit ? element.requestSubmit() : element.submit());
    await form.page().waitForTimeout(400);
  };
  const fill = async (form, email) => {
    const set = async (selector, action) => { const field = form.locator(selector).first(); if (await field.count()) await action(field); };
    await set("[name=title]", field => field.fill("The Left Hand of Darkness"));
    await set("select[name=district]", async field => {
      const values = await field.locator("option").evaluateAll(options => options.map(option => option.value).filter(Boolean));
      if (values.length) await field.selectOption(values[0]);
    });
    await set("[name=email]", field => field.fill(email));
    await set("input[name=condition]", async field => { try { await field.check({ timeout: 3_000 }); } catch { await field.evaluate(element => { if (!element.checked) element.click(); }); } });
  };
  try {
    for (const [name, width, height] of [["desktop", 1440, 900], ["phone", 390, 844]]) {
      const page = await open(width, height);
      result[`overflow-${name}`] = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
      await page.close();
    }
    let page = await open(1440, 900);
    const text = await visibleText(page);
    const required = [content.brand, ...content.nav, content.hero.h1, content.hero.sub, content.hero.cta_primary, content.hero.cta_secondary,
      ...content.features.flatMap(feature => [feature.title, feature.body])];
    result.missingCopy = required.filter(entry => !text.includes(entry));
    result.footer = /©\s*2026\s*BookLoop/.test(text) && ["Rules", "Privacy", "Contact"].every(word => text.includes(word));
    result.emptyOnLoad = text.includes(states.empty);
    result.skipLink = await page.evaluate(() => {
      const link = [...document.querySelectorAll("a[href^='#']")].find(anchor => /skip|main|content/i.test(anchor.textContent ?? ""));
      return !!link && link.getAttribute("href").length > 1 && !!document.getElementById(link.getAttribute("href").slice(1));
    });
    const form = page.locator("[data-role=signup-form]").first();
    result.fields = await page.evaluate(() => {
      const form = document.querySelector("[data-role=signup-form]");
      if (!form) return { error: "no signup-form" };
      const field = name => form.querySelector(`[name=${name}]`);
      const labelled = element => !!element && (element.labels?.length ?? 0) > 0 && [...element.labels].some(label => label.textContent.trim());
      const radios = [...form.querySelectorAll("input[name=condition]")];
      const options = [...(field("district")?.querySelectorAll("option") ?? [])].map(option => option.textContent.trim());
      // The brief requires labels, an email field and the listed choices; "required" is behaviour, which the states
      // unit exercises, so the HTML attribute itself is not demanded.
      return {
        title: labelled(field("title")), district: labelled(field("district")), email: labelled(field("email")),
        emailType: field("email")?.type === "email",
        radios: radios.length === 3 && radios.every(labelled), radioLabels: radios.map(radio => [...radio.labels].map(label => label.textContent.trim()).join(" ")),
        options,
      };
    });
    if (await form.count()) {
      await submit(form);
      result.errorAfterEmpty = (await visibleText(page)).includes(states.error);
      await fill(form, "not-an-email");
      await submit(form);
      const afterInvalid = await visibleText(page);
      result.successAfterInvalidEmail = afterInvalid.includes(states.success);
      result.errorAfterInvalidEmail = afterInvalid.includes(states.error);
      await page.close();
      page = await open(1440, 900);
      const fresh = page.locator("[data-role=signup-form]").first();
      await fill(fresh, "reader@example.com");
      await submit(fresh);
      result.successAfterValid = (await visibleText(page)).includes(states.success);
    }
    await page.close();
  } catch (error) {
    result.errors.push(error instanceof Error ? error.message.split("\n")[0] : String(error));
  }
  await browser.close();
  writeFileSync(join(output, "audit.json"), JSON.stringify(result, null, 1));
  process.exit(0);
}

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const playwrightDirectory = join(root, "node_modules", "playwright-core");
const browsers = JSON.parse(readFileSync(join(playwrightDirectory, "browsers.json"), "utf8"));
const shell = browsers.browsers.find(browser => browser.name === "chromium-headless-shell");
const chromium = process.env.CHROMIUM_PATH ?? join(homedir(), ".cache", "ms-playwright", `chromium_headless_shell-${shell.revision}`, "chrome-linux", "headless_shell");
const runtimeLibraries = join(dirname(dirname(realpathSync(process.execPath))), "lib");
const request = JSON.parse(readFileSync(process.argv[2], "utf8"));
const content = join(root, request.package, "public", "content.json");
const findings = [];
const notes = ["Every page is opened directly from its files, as the task asks, in headless Chromium inside the sandbox.",
  "No horizontal scrolling and the skip link are contract requirements the functional grader does not check (the judging step sees the overflow); a miss there is a note, not a false pass.",
  "An invalid email is a defect only when the page then shows the success state; a page that leaves it to the browser's own validation shows no error copy of its own, which the brief does not forbid.",
  "The HTML required attribute is not demanded: the brief asks for required fields, and the states unit checks that an empty submission is refused."];
for (const trial of request.trials) {
  const output = mkdtempSync(join(tmpdir(), "audit-vis-"));
  const site = join(trial.directory, "artifacts");
  const run = spawnSync("python3", [join(root, "scripts", "sandbox_exec.py"), "--rw", output, "--ro", site, "--ro", playwrightDirectory, "--ro", dirname(dirname(chromium)),
    "--ro", join(root, "scripts", "audits"), "--ro", dirname(content), "--", "/usr/bin/env", `CHROMIUM=${chromium}`, `LD_LIBRARY_PATH=${runtimeLibraries}`,
    process.execPath, join(root, "scripts", "audits", "vis_interactions.mjs"), "--page", playwrightDirectory, site, output, content], { encoding: "utf8", timeout: 180_000 });
  let audit;
  try { audit = JSON.parse(readFileSync(join(output, "audit.json"), "utf8")); } catch { audit = { errors: [`no audit result: ${run.stderr.slice(-300)}`] }; }
  rmSync(output, { recursive: true, force: true });
  const scoreRuns = readdirSync(join(trial.directory, "score-runs")).map(name => JSON.parse(readFileSync(join(trial.directory, "score-runs", name, "score.json"), "utf8")))
    .sort((left, right) => left.createdAt.localeCompare(right.createdAt));
  const checks = Object.fromEntries(scoreRuns.at(-1).evaluation.checks.map(check => [check.id.replace(/^.*?(roles|features|copy|form|states|contrast)$/, "$1"), check.passed]));
  const unit = (name, grader, problems, beyond = false) => findings.push({ trial: trial.directory, label: trial.label, item: null, unit: name,
    grader: grader === undefined ? "n/a" : grader ? "pass" : "fail",
    verdict: beyond ? (problems.length ? "note" : "true pass") : grader ? (problems.length ? "false pass" : "true pass") : (problems.length ? "true fail" : "note"),
    detail: [...problems, ...(audit.errors ?? [])].join("; ") });
  const fields = audit.fields ?? {};
  unit("form states by interaction", checks.states, [
    ...(audit.emptyOnLoad ? [] : ["the empty-state text is not shown on load"]),
    ...(audit.errorAfterEmpty ? [] : ["no error-state text after submitting the empty form"]),
    ...(audit.successAfterInvalidEmail ? ["the success state after an invalid email"] : []),
    ...(audit.successAfterValid ? [] : ["no success-state text after a valid submission"])]);
  unit("fields labelled at run time, with the required options", checks.form, [
    ...["title", "district", "email", "radios"].filter(name => !fields[name]).map(name => `${name === "radios" ? "condition choices" : name} without an associated label`),
    ...(fields.emailType === false ? ["the email field is not type=email"] : []),
    ...(["Downtown", "Jiangbei", "Shapingba", "Nan'an"].every(option => (fields.options ?? []).includes(option)) ? [] : [`area options ${JSON.stringify(fields.options)}`]),
    ...(["New", "Light wear", "Visible wear"].every(choice => (fields.radioLabels ?? []).some(label => label.includes(choice))) ? [] : [`condition labels ${JSON.stringify(fields.radioLabels)}`])]);
  unit("fixed copy visible", checks.copy, [...(audit.missingCopy ?? ["page did not load"]).map(text => `missing: ${text}`), ...(audit.footer ? [] : ["footer copy"])]);
  unit("no horizontal scrolling at 1440 and 390 pixels; skip link", undefined, [
    ...(audit["overflow-desktop"] ? ["scrolls horizontally at 1440"] : []), ...(audit["overflow-phone"] ? ["scrolls horizontally at 390"] : []),
    ...(audit.skipLink ? [] : ["no skip link to an existing target"])], true);
}
writeFileSync(process.argv[3], JSON.stringify({ findings, notes }, null, 1));
