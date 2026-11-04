import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { jobFor } from "../src/jobs.js";

test("fr_7_1 morning and afternoon crons start the daily job", () => {
  assert.equal(jobFor("17 5 * * *"), "daily");
  assert.equal(jobFor("17 15 * * *"), "daily");
});

test("fr_7_1 sunday cron starts the weekly job", () => {
  assert.equal(jobFor("17 18 * * SUN"), "weekly");
});

test("fr_7_1 every cron in wrangler.toml has a job", () => {
  const toml = readFileSync(new URL("../wrangler.toml", import.meta.url), "utf8");
  const crons = [...toml.matchAll(/"([^"]+ \* [^"]+)"/g)].map((match) => match[1]);
  assert.equal(crons.length, 3);
  crons.forEach((cron) => assert.ok(jobFor(cron)));
});

test("fr_7_2 unknown cron fails loudly", () => {
  assert.throws(() => jobFor("0 0 * * *"), /No job/);
});
