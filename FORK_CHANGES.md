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
**What:** Pinned to `2.38.7` (latest stable on npm at time of writing) rather than tracking upstream's default or `latest`. Bumped from `2.38.6` on 2026-09-11.
**Why:** Deliberate version control — upgrades happen as a reviewed decision, not an automatic pull.

### 4. SearXNG service added, hardened for privacy, BM25 reranker layered in
**Commit:** `harden searxng: curated engines, autocomplete/tracker-url privacy fixes, POST method, image proxy; layer in BM25 reranker via custom Dockerfile.searxng`
**Files:** `Dockerfile.searxng` (new), `searxng-settings.yml`, `docker-compose.ai-sandbox.yml`
**What:**
- New `searxng` service in `docker-compose.ai-sandbox.yml`, built from a custom `Dockerfile.searxng` layered on `ghcr.io/searxng/searxng`, wired into `sandbox-network` and exposed to n8n's Instance AI feature via `N8N_INSTANCE_AI_SEARXNG_URL=http://searxng:8080`.
- `Dockerfile.searxng` bootstraps `pip` into the base image's venv (Void Linux base ships without it), installs [searxng-bm25-reranker](https://github.com/Oaklight/searxng-bm25-reranker), then strips `pip`/`setuptools`/`wheel` back out to keep the image lean.
- `searxng-settings.yml` rewritten for privacy: curated `keep_only` engine list (duckduckgo, brave, mojeek, startpage, wikipedia, github, stackexchange, wikidata), `method: POST` (keeps queries out of access logs / browser history-adjacent server logs), `image_proxy: true`, `public_instance: false`, `autocomplete: ""` (disables autocomplete-leak to third parties), `safe_search: 1` default.
- Two plugins enabled under `plugins:`, both addressed by full module path (this SearXNG version requires the new-style key — the older top-level `enabled_plugins: [...]` list is silently ignored):
  - `searx.plugins.tracker_url_remover.SXNGPlugin` (built-in — note the `searx.plugins.` prefix; external/pip-installed plugins like BM25 below do **not** take this prefix)
  - `searxng_bm25_reranker.SXNGPlugin` (external, installed via the Dockerfile step above)
- `searxng` container's port bound to the host's LAN IP only (`192.168.2.210:8080:8080`, not `0.0.0.0`) — reachable from the LAN/Traefik, not from outside the host's own interface.
**Why:** n8n's Instance AI search feature needed a search backend; self-hosting via SearXNG avoids sending every AI-assisted search query to a third party. The privacy settings and BM25 reranker close the gap between "self-hosted" and "actually private/effective" — default SearXNG settings leak autocomplete queries to the configured autocomplete backend and don't rerank results for relevance.
**Revisit if:** upstream SearXNG changes its plugin-loading schema again, or a future base image restores `pip` (the ensurepip-bootstrap-then-strip step becomes unnecessary).

### 5. SearXNG version pin
**File:** `.env` (`SEARXNG_VERSION`), `docker-compose.ai-sandbox.yml` (fallback default)
**What:** Pinned to `2026.9.12-d4f00d15d`. Bumped from the original `2026.8.28-a30b2d474` on 2026-09-13 (SearXNG cuts new tags nearly daily; left unpinned this would drift constantly, left stale it falls behind on engine fixes — checked and bumped as a deliberate step instead).
**Why:** Same reasoning as the n8n version pin (#3) — reviewed upgrades, not automatic tracking.

### 6. Network exposure: SearXNG is internal-only, not on the Cloudflare Tunnel
**Scope:** Outside this repo — Traefik dynamic config (`private.yml`) and DNS (Technitium), not tracked in this git history.
**What:** `search.myhomelab.space` resolves and routes LAN/Traefik-internal only (`middlewares: ["internal"]`). It was briefly on the Cloudflare Tunnel alongside `n8n.` and torn back off.
**Why:** An unauthenticated SearXNG instance has no reason to be reachable from the public internet; away-from-home access is intended to go through Tailscale instead (not yet configured as of this writing).
**Revisit if:** away-from-home search access is needed before Tailscale is set up on this VM.

### 7. `worklaptop-minimal` branch: pared down for local dev
**Branch:** `worklaptop-minimal` (this section describes that branch, not `homelab-main`)
**Files removed:** `docker-compose.instance-ai.yml`, `docker-compose.ai-sandbox.yml`, `docker-compose.ai-sandbox.privileged.yml`, `docker-compose.ai-sandbox.sysbox.yml`, `docker-compose.ai-daytona.yml`, `docker-compose.cloudflare.yml`, `Dockerfile.searxng`, `searxng-settings.yml`
**Files added:** `docker-compose.override.yml` (gates the core `cloudflared` service behind a `cloudflare-tunnel` profile, so it's skipped by default — Compose auto-loads this filename, no `-f` flags needed)
**File trimmed:** `.env.example` — dropped the Instance AI / sandbox / SearXNG / Daytona variable block (all dead weight with the compose files gone); `CLOUDFLARE_TUNNEL_TOKEN` annotated as opt-in via the new profile
**What:** Core stack only — `n8n`, `n8n-webhook`, `n8n-worker`, `n8n-worker-runner`, `n8n-autoscaler`, `postgres`, `redis`, `redis-monitor`, `n8n-backup`. No Sysbox dependency (Docker Desktop on macOS can't provide it anyway), no public tunnel, no AI search backend.
**Why:** Built for a work MacBook running Docker Desktop — no need for Instance AI or its dependency chain there, and Sysbox isn't available in a Docker-Desktop VM regardless. Started from `homelab-main` at commit `77b5bff` and subtracted, rather than building up from scratch, so the core n8n/queue/worker/db setup stays byte-identical to the production branch.
**Revisit if:** Instance AI or the sandbox becomes wanted on this machine too — re-add the removed compose files and `.env.example` block from `homelab-main`, they weren't rewritten, just deleted here.

### 8. Removed VM106's hardcoded LAN IP from the core n8n port bind
**File:** `docker-compose.yml`
**What:** The `n8n` service published two ports — `127.0.0.1:5678:5678` and `192.168.2.210:5678:5678` (VM106's own LAN address, added when n8n was exposed to the LAN there). The second line was missed when this branch was first cut from `homelab-main`, since it lives in the shared core file, not one of the files removed in #7.
**Why:** `192.168.2.210` doesn't exist as a local address anywhere but VM106 — `docker compose up -d` fails outright elsewhere with `bind: can't assign requested address`. Removed for this branch; `homelab-main` keeps it, since VM106 genuinely needs that LAN-reachable bind.
**Found by:** first real `docker compose up -d` run on an actual work MacBook (this branch's intended target) — the failure mode this branch exists to avoid.

### 9. `.env.example`'s `COMPOSE_FILE` silently disabled the cloudflared profile gate
**File:** `.env.example`
**What:** `COMPOSE_FILE=docker-compose.yml` (inherited from `homelab-main`, where the wizard keeps this list in sync with every optional override it manages). Compose treats a set `COMPOSE_FILE` as the *complete* file list — it stops auto-discovering `docker-compose.override.yml` entirely once this variable exists. So on this branch, `cloudflared`'s profile gate (added in #7) never applied: the override file just wasn't part of the build.
**Fix:** `COMPOSE_FILE=docker-compose.yml:docker-compose.override.yml` — explicit, so the override loads every time.
**Why this branch hit it and `homelab-main` doesn't:** `homelab-main`'s wizard-managed `COMPOSE_FILE` already lists every file it needs (including `docker-compose.override.yml` when present, per `n8n-setup.sh`'s `compose_file_list()`). This branch inherited a stale `.env.example` snapshot from before the override file existed, and nothing regenerates it automatically since the wizard itself was never meant to run here.
**Found by:** `cloudflared` crash-looping on a real `docker compose up -d` — no Cloudflare token set (correctly, this branch doesn't need one), so the container kept restarting instead of being skipped.
**Revisit if:** another override file gets added to this branch later — it needs adding to this same `COMPOSE_FILE` line, or it'll have the identical silent-skip problem.

## Review process for future upstream releases

1. `git fetch upstream`
2. `git log homelab-main..upstream/main --oneline` — see what changed
3. Check whether any upstream commit touches `Dockerfile.runner`'s Corepack step, or the runner security flags in `docker-compose.yml` — if so, divergence #1 or #2 above may need to be re-evaluated or dropped
4. `git merge upstream/main` (or cherry-pick specific commits) into a throwaway branch, resolve conflicts, rebuild in isolation (`docker compose build`, no `up`) before cutting over
5. Follow the same backup-before-cutover pattern as any version bump: tag current images, dump the DB, copy `.env`, then `up -d --build`
6. For SearXNG specifically: check the [searxng-bm25-reranker](https://github.com/Oaklight/searxng-bm25-reranker) repo for compatibility before bumping `SEARXNG_VERSION` past a major schema change — the plugin-loading key format (`plugins:` with full module paths) has already changed once upstream.
