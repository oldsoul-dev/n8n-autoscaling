# FORK_CHANGES.md

This is a maintained fork of [conor-is-my-name/n8n-autoscaling](https://github.com/conor-is-my-name/n8n-autoscaling), tracked as the `upstream` remote on the `homelab-main` branch. Every change made on top of upstream is listed here, in commit order, so a future `git fetch upstream && git log upstream/main..homelab-main` diff can be checked against this list before merging anything new.

## Divergences from upstream

### 1. Runner security hardening
**Commit:** `Baseline: hardened runner flags (insecure-mode/prototype-mutation off)...`
**File:** `docker-compose.yml`
**What:** `N8N_RUNNERS_INSECURE_MODE` and `N8N_RUNNERS_ALLOW_PROTOTYPE_MUTATION` flipped from `true` to `false` across all three task-runner service blocks (main, worker-runner sidecar).
**Why:** Upstream ships both `true` by default, which lifts n8n's own JS sandboxing on Code nodes. Not needed for this instance's workflows — kept off unless a specific workflow requires raw `require()` or prototype mutation.
**Revisit if:** a workflow starts failing with a sandboxing-related error in the Code node.

### 2. Dockerfile.runner Corepack fix
**Commit:** `Patch Dockerfile.runner: install Corepack explicitly...`
**File:** `Dockerfile.runner`
**What:** Added `RUN npm install -g corepack@latest` immediately before the existing `RUN node .../corepack/dist/corepack.js prepare pnpm@10 --activate` line.
**Why:** Upstream's Dockerfile calls the bundled Corepack binary directly at a fixed path (`/usr/local/lib/node_modules/corepack/dist/corepack.js`), assuming the Node base image always ships it. Node 25+ dropped bundled Corepack (made it opt-in), so that path stopped existing and the build failed outright on any n8n release using a Node 25+ base image (confirmed against n8n 2.38.5 and 2.38.6). `npm install -g corepack` recreates that exact path, so the existing upstream commands work unmodified — this is an additive one-line fix, not a rewrite of their build logic.
**Revisit if:** upstream ever patches this themselves (check their Dockerfile.runner on each version bump) — if so, this patch becomes redundant and can be dropped.

### 3. Version pin
**File:** `.env` (`N8N_VERSION`)
**What:** Pinned to `2.38.6` (latest stable on npm at time of writing) rather than tracking upstream's default or `latest`.
**Why:** Deliberate version control — upgrades happen as a reviewed decision, not an automatic pull.

## Review process for future upstream releases

1. `git fetch upstream`
2. `git log homelab-main..upstream/main --oneline` — see what changed
3. Check whether any upstream commit touches `Dockerfile.runner`'s Corepack step, or the runner security flags in `docker-compose.yml` — if so, divergence #1 or #2 above may need to be re-evaluated or dropped
4. `git merge upstream/main` (or cherry-pick specific commits) into a throwaway branch, resolve conflicts, rebuild in isolation (`docker compose build`, no `up`) before cutting over
5. Follow the same backup-before-cutover pattern as any version bump: tag current images, dump the DB, copy `.env`, then `up -d --build`
