# Today in AI

Daily AI newsletter served as one static page at `https://sumiya.page/ainews.html`.

```
sources.yaml ──► fetch ──► items (every allowed URL)
                              │
threads.json + last editions ─┼─► Claude (submit_edition tool, schema-bound)
                              │
                         validate: schema · thread names · link provenance · leak lint
                              │  (rejected → retry with the exact problems, max 3)
                              ▼
               data/editions/YYYY-MM-DD.json  ──► build (Jinja, deterministic) ──► dist/ainews.html ──► S3
```

The model writes data. It never touches HTML, so the design cannot drift and production chatter has no field to land in.

## Layout

| Path | What it is |
|---|---|
| `data/editions/*.json` | One file per edition. Source of truth. |
| `data/threads.json` | Storyline registry: start date, color, active flag. |
| `data/sources.yaml` | Pinned feeds and channel ids. Edit to add or remove sources. |
| `data/state.json` | Seen-URL ledger (60 days) so overlapping fetch windows never repeat an item. |
| `templates/` | Page markup, CSS, and script (the locked design). |
| `newsletter/` | `fetch`, `run`, `build`, `lint`, `schema`, `check_sources`, `prompt.md`. |
| `logs/run-*.json` | Per-run gaps and validation attempts. Private; never rendered. |

## Commands

```bash
pip install -r requirements.txt
python -m newsletter.build            # rebuild dist/ainews.html from data
python -m newsletter.check_sources    # probe feeds, resolve missing YouTube ids (needs internet)
python -m newsletter.run              # full daily run (needs ANTHROPIC_API_KEY)
./tests/run_checks.sh                 # offline: build + reject a bad edition + accept a good one
S3_BUCKET=... ./deploy.sh             # upload; set CLOUDFRONT_DISTRIBUTION_ID to invalidate
```

## Daily run

`.github/workflows/daily.yml` runs every day at 14:43 UTC (07:43 PDT, 06:43 PST) and can also be started by hand with `gh workflow run daily.yml`. It generates the edition, commits `data/` and `logs/` back to `main`, builds, and deploys to S3 with CloudFront invalidation. Pull before editing locally, since the bot pushes daily.

It needs repo secrets `ANTHROPIC_API_KEY` and `AWS_DEPLOY_ROLE_ARN` (an IAM role trusting GitHub OIDC for this repo's `main` branch, allowed `s3:PutObject` on the key and `cloudfront:CreateInvalidation`), and repo variables `S3_BUCKET`, `CLOUDFRONT_DISTRIBUTION_ID`, and optionally `AWS_REGION`.

Each `logs/run-YYYY-MM-DD.json` records the model's token usage per attempt under `usage`.

A failed run leaves yesterday's page up and shows as a red run in Actions. Nothing is published half-built.

## Rules the code enforces

- Every link in an edition must be a URL fetched that day.
- Exactly one lead story; 3 to 5 top stories; known thread names only.
- Reader text is rejected if it narrates source gaps or production ("blogs were quiet", "compiled at", "scheduled run").
- Threads with no substantive update for 10 days go inactive and drop out of the prompt; they stay in the Storylines view.
- One edition per date. Re-running the same day is a no-op.
