# wing-alert

Personal, open-source project: a scheduled GitHub Action that checks wingfoiling conditions on the Wicklow coast, alerts David on WhatsApp and publishes a daily report to GitHub Pages. The spec is [docs/specs/wing-alert.md](docs/specs/wing-alert.md). It is the source of truth; requirement IDs look like `FR-1.2`.

## How we work

- **Spec first.** Behaviour changes go into the spec (and get agreed) before code. If the code needs to differ from the spec, say so and update the spec in the same PR.
- **One branch and one PR per slice** (see the spec's slice table). Merge with a merge commit, not squash.
- **Merge as you go.** David gave standing approval (2026-11-01): once a PR's work is done and tests pass, merge it (merge commit) without asking. Say what was merged in the wrap-up.
- **Keep it simple.** Build what the spec asks; put ideas in the spec's "Future work" instead of building them.
- David dictates by voice: expect speech-to-text slips (spot names especially) and read for intent.

## Code rules

- **Small functions** (about 15 lines max) and small modules with one job each.
- **Plain classes and functions.** Add a `typing.Protocol` only when a second implementation really exists (e.g. a second message sender).
- **Dependencies passed in, never created inside.** Build everything in one wiring place.
- **Type hints everywhere.** Names over comments. Comments only explain *why* or cite a source.
- **Sync is fine.** It's a batch job, not a server: plain `httpx.Client`.
- **Config, not code:** spots, thresholds and schedules live in YAML.

## Tests

- `pytest`, with `respx` to fake `httpx`. Inject the clock; never depend on the real date or `sleep`.
- Test names include the requirement ID: `test_fr_1_3_skips_offshore_wind`.
- Coverage reported on every run (`pytest-cov`), aiming for 90%+.
- Tests that hit real APIs are marked `live` and only run by hand.

## Secrets and GitHub

- The repo is `daplein/wing-alert` (personal account, **public**). Pushes go over HTTPS with the `daplein` gh token (set in the repo's local git config). Use `GH_TOKEN=$(gh auth token --user daplein)` for `gh` commands.
- WhatsApp phone numbers and CallMeBot API keys live only in GitHub Actions secrets and a git-ignored `.env`. Never write them into any file, commit, PR, log or the published site.

## Docs

- Mermaid diagrams: preview them at `http://localhost:4000/<absolute path>` (md-preview).
