// Keep in sync with the crons in wrangler.toml (FR-7.1, FR-10.1).
// "record" stays in the Worker; the others start a GitHub job.
const JOBS = {
  "17 5 * * *": "daily",
  "17 15 * * *": "daily",
  "17 18 * * SUN": "weekly",
  "7 * * * *": "record",
};

export function jobFor(cron) {
  const job = JOBS[cron];
  if (!job) throw new Error(`No job for cron "${cron}"`);
  return job;
}
