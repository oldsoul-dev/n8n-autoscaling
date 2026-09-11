# PLAN.md

### What we're doing

Bump VM106's n8n stack from 2.36.8 to the current stable release (2.38.6), fixing the upstream `Dockerfile.runner` bug that blocked this last time — its Corepack step assumes a Node version that no longer bundles Corepack. Along the way, turn `/root/n8n-autoscaling` from a bare clone into a real fork: an upstream remote, our local patches committed and documented, so future n8n releases can be reviewed and merged deliberately instead of blind-pulled.

### Steps

1. **Make it a real fork.** Add `upstream` remote pointing at `conor-is-my-name/n8n-autoscaling`, create a local branch (e.g. `homelab-main`), and commit the current working tree as a baseline — including the insecure-mode flags already flipped off, so that patch is in history instead of silently sitting uncommitted.
2. **Patch the Corepack step.** In `Dockerfile.runner`, add an explicit `npm install -g corepack@latest` before the `corepack prepare pnpm@10 --activate` line, so it works against Node 26 base images. Commit this as its own change with a message explaining the upstream bug it works around.
3. **Build in isolation first.** Bump `N8N_VERSION=2.38.6` in `.env`, then `docker compose build n8n n8n-worker-runner` (build only, no `up`) — confirms the image compiles clean before touching anything running.
4. **Snapshot before cutover.** Tag the current working images (`docker tag` current `n8n-autoscaling-n8n` / `-n8n-worker-runner` images as `:pre-2.38.6-rollback`), copy `.env` aside, and `pg_dump` the live database to a timestamped file — the images can be reverted with a tag, but a bad migration needs the DB itself restorable, not just the old code pointed back at it.
5. **Cut over and verify.** `docker compose up -d --build`, confirm every container reaches healthy, confirm the n8n UI loads, confirm the 5 migrated workflows and 14 credentials still decrypt, confirm Instance AI (Ollama-backed) still responds.
6. **Commit and tag the working state.** Once verified, commit the version bump to the fork's git history and tag it (`v2.38.6-homelab`) so this known-good point is easy to find later.
7. **Write `FORK_CHANGES.md`.** One file listing every place this fork diverges from upstream (runner security flags, the Corepack patch, the version pin) and a short process note: before merging a future upstream release, diff it against this file's list first.

### What we're NOT doing

- Not bumping to 2.39.0 — that's unreleased master, not a tagged stable version
- Not setting up automated upstream-tracking (bot/CI diffing) — manual review per release, by design
- Not touching LXC 108 or re-running any part of the earlier migration — that's already done
- Not standing up a separate staging instance — the tag-and-rollback snapshot in step 4 is the safety net instead
- Not revisiting the docker-socket-proxy or other hardening decisions already made in earlier sessions

### How we'll know it works

1. `docker exec n8n-autoscaling-n8n-1 n8n --version` reports `2.38.6`, and the container stays `healthy` (no crash-loop) for several minutes.
2. Logging into `https://n8n.myhomelab.space` shows all 5 migrated workflows and their 14 credentials loading and testing successfully — nothing lost in the version jump.
3. Running the Instance AI tool once more in the n8n UI completes without the earlier Corepack-related runner crash.
