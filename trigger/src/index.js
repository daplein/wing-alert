import { jobFor } from "./jobs.js";

const DISPATCH_URL =
  "https://api.github.com/repos/daplein/wing-alert/actions/workflows/daily.yml/dispatches";

async function dispatch(job, token) {
  const response = await fetch(DISPATCH_URL, {
    method: "POST",
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "User-Agent": "wing-alert-trigger",
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: JSON.stringify({ ref: "main", inputs: { job } }),
  });
  if (!response.ok) {
    throw new Error(`GitHub answered ${response.status}: ${await response.text()}`);
  }
}

// Retry once, then fail so the error shows in the Worker's logs (FR-7.2).
async function dispatchWithRetry(job, token) {
  try {
    await dispatch(job, token);
  } catch (error) {
    console.warn(`First try failed, retrying: ${error.message}`);
    await dispatch(job, token);
  }
}

export default {
  async scheduled(controller, env) {
    const job = jobFor(controller.cron);
    await dispatchWithRetry(job, env.GITHUB_TOKEN);
    console.log(`Started the ${job} job`);
  },
};
