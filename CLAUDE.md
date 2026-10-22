# Handoff from the claude.ai session (2026-10-21)

Read this before doing anything in this repo. It carries the decisions from a browser session so SP doesn't have to repeat them.

## What this is

Today in AI: SP's daily AI newsletter, served at https://sumiya.page/ainews.html. It was generated and hosted by Muse (an agent platform) from 2026-09-16 to 2026-10-21. Muse's public share link died on 2026-10-20 and SP switched off all Muse scheduled jobs on 2026-10-21. This repo rebuilds the newsletter to run on SP's own infrastructure.

`dist/ainews.html` (from `python -m newsletter.build`) is the full 36-edition archive, verified against the Muse export: same text per edition, same design, search, filters and Storylines working. It can be uploaded to S3 as-is.

## What's done (see README.md for layout and commands)

- `scripts/migrate_from_muse.py` split the Muse export into `data/editions/*.json`, `data/threads.json`, `data/state.json`. It dropped 19 reader-facing "sources were quiet" notes (Sep 29 to Oct 8), normalized colophons, dated threads from first appearance.
- `newsletter/build.py` renders data through `templates/` deterministically. The model never writes HTML.
- `newsletter/run.py` daily run: fetch, Claude call via a forced `submit_edition` tool bound to `newsletter/schema.py`, then checks (schema, known thread names, every link must be a URL fetched that run, leak-phrase lint in `newsletter/lint.py`), retry up to 3 with the exact problems, write data, build. Idempotent per date.
- `./tests/run_checks.sh` passes offline (archive builds strict; a bad edition is rejected for invented URL, gap phrase, unknown thread; a good one publishes).
- `.github/workflows/daily.yml` is manual-trigger only. The cron line is commented out on purpose.

## Not verified

- No live run yet: the browser sandbox had no internet and no ANTHROPIC_API_KEY. The model call and all feeds are untested.
- In `data/sources.yaml`, most feed URLs and the Two Minute Papers channel id are best-knowledge and marked `verified: false`. The bycloud blog URL was never pinned. bycloud and AI Jason channel ids are null; `python -m newsletter.check_sources` resolves them from their handles.
- Default model is `claude-sonnet-5-5` (env `NEWSLETTER_MODEL` overrides).

## Decision: merge into psumiya/brief

SP's older repo https://github.com/psumiya/brief (idle since 2026-08-18) is a profile-based brief generator. Recommendation SP received: fold Today in AI into `brief` as the `ai_news` profile's output instead of keeping two repos.

- Keep from brief: fetch layer (Gemini video transcription, weights, off-topic filter, cache, seen ledger), token tracker, pytest + evals CI, multi-brief site manifest (`briefs.json`), deploy code.
- Bring from here: edition schema, prompt, renderer and templates, lint with link provenance, thread registry with 10-day decay, the 36-edition data.
- Make output format selectable per profile in `profiles/<id>/profile.yaml`, so other profiles keep brief's current schema.
- Drop RAG (sqlite-vec) for this profile; the thread registry covers continuity.
- Union both source lists in one file with brief's weights.
- Deploy `ainews.html` at the site root so the current URL keeps working.

SP has not yet approved starting the merge. Confirm before doing it.

## Open question to resolve first

SP may have deleted the AWS infrastructure behind brief (SAM stack, S3 bucket, CloudFront). Check before planning any deploy, read-only:

```bash
aws sts get-caller-identity
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --query "StackSummaries[].StackName"
aws s3 ls
aws cloudfront list-distributions --query "DistributionList.Items[].{id:Id,aliases:Aliases.Items,origin:Origins.Items[0].DomainName}"
```

Also find what currently serves sumiya.page (`dig sumiya.page`, `curl -sI https://sumiya.page/ainews.html`). Report findings; don't create or delete anything without SP saying so.

## Rules SP set

- Nothing runs on a schedule until SP explicitly says to turn it on.
- Ask before any deploy, AWS change, or push.
- Newsletter rules: third-party sources only; reader-facing text never mentions how it was made, source gaps, or publishing; no numbered labels; summaries attribute claims to the source and analysis is clearly the newsletter's read.
- Talking to SP: direct and committed, recommend one path, prose over bullets, no em dashes, no "X, not Y" constructions, no filler or flattery.
