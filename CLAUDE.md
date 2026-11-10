# Today in AI

SP's daily AI newsletter, served at https://sumiya.page/ainews.html. See README.md for layout and commands.

## Current state

- Live runs work: `python -m newsletter.run` fetches, calls Claude (`claude-sonnet-5-5`, env `NEWSLETTER_MODEL` overrides) with structured outputs bound to `newsletter/schema.py`, validates, writes data, builds `dist/ainews.html`.
- Local setup: `.venv` with `requirements.txt`; `ANTHROPIC_API_KEY` in `.env` (gitignored). Load with `set -a; . ./.env; set +a`.
- Deploy: `S3_BUCKET=... CLOUDFRONT_DISTRIBUTION_ID=... ./deploy.sh`. The real bucket, distribution, and the blog-repo deploy caveat live in `CLAUDE.local.md` (gitignored).
- `.github/workflows/daily.yml` runs daily on cron at 14:43 UTC (turned on by SP 2026-11-10) and can still be triggered with `gh workflow run daily.yml`. Repo secrets `ANTHROPIC_API_KEY`, `AWS_DEPLOY_ROLE_ARN` and variables `S3_BUCKET`, `CLOUDFRONT_DISTRIBUTION_ID` are set; AWS role `todayinai-deploy` (OIDC, `main` branch only) can write `ainews.html` and invalidate the distribution. First successful end-to-end run was 2026-11-10; the 10-23 run failed at deploy because the `AWS_DEPLOY_ROLE_ARN` secret held a wrong value.
- psumiya/brief (the older profile-based generator) is retired and archived. Its AWS stack was deleted. The only piece worth porting is its Gemini video transcription.

## Known issues

- YouTube's public channel RSS feed (`/feeds/videos.xml`) intermittently or persistently 404s for real channels; `fetch.py` retries, but Yannic Kilcher failed every attempt on 2026-10-22. Planned fix: switch video fetching to the YouTube Data API.
- `tests/run_checks.sh` uses GNU `sed -i` and fails on macOS after the build step.
- bycloud's blog URL is not pinned in `data/sources.yaml`.

## Rules SP set

- Don't add or change schedules without SP's say-so. The daily newsletter cron is on.
- Ask before any deploy, AWS change, or push.
- Newsletter rules: third-party sources only; reader-facing text never mentions how it was made, source gaps, or publishing; no numbered labels; summaries attribute claims to the source and analysis is clearly the newsletter's read.
- Talking to SP: direct and committed, recommend one path, prose over bullets, no em dashes, no "X, not Y" constructions, no filler or flattery.
