// Keep in sync with the crons in wrangler.toml (FR-7.1).
const JOBS = {
  "17 5 * * *": "daily",
  "17 15 * * *": "daily",
  "17 18 * * SUN": "weekly",
};

export function jobFor(cron) {
  const job = JOBS[cron];
  if (!job) throw new Error(`No job for cron "${cron}"`);
  return job;
}
