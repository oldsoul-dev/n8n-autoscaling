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

### 7. Known issue, not fixed here: stale `N8N_VERSION` fallback defaults
**Status:** Documented only — deliberately **not** patched on this branch, since VM106's actual builds always pass the real value from `.env` and never hit it.
**Files:** `Dockerfile` (`ARG N8N_VERSION=2.36.8`), `Dockerfile.runner` (same), `docker-compose.yml` (two `build.args` fallbacks, same default)
**The issue:** all four fallback defaults still say `2.36.8`, but `Dockerfile.runner` hardcodes `corepack prepare pnpm@11.22.0` — correct for the *actual* pinned version (`2.38.7`; confirmed `n8nio/runners:2.38.7` links `pnpm@11.22.0`), but wrong for the stale `2.36.8` default (confirmed `n8nio/runners:2.36.8` links `pnpm@10.32.1`). Any build that falls through to the default instead of reading `.env` hits `ERR_PNPM_UNEXPECTED_STORE`.
**When this actually bites:** anything that builds these Dockerfiles standalone without passing `--build-arg N8N_VERSION=...` — e.g. Docker Build Cloud's auto-build-every-Dockerfile-it-finds feature (hit this exact error on the `worklaptop-minimal` branch, which is why that branch has the defaults bumped to `2.38.7` — see that branch's FORK_CHANGES.md #8). `docker compose build`/`up -d` here on VM106 is unaffected — `.env` always supplies `N8N_VERSION` and overrides the fallback.
**Revisit if:** a standalone/CI build of either Dockerfile starts failing with `ERR_PNPM_UNEXPECTED_STORE` on this branch too, or the next `N8N_VERSION` bump changes the runner's linked pnpm version again (re-check with the command already documented above, in divergence #2's neighbor comment in `Dockerfile.runner`).

### 8. Custom SearXNG engines: private Gitea repo search, Shlink go-links
**Files:** `searxng-engines/gitea_private.py` (new), `searxng-engines/shlink.py` (new), `Dockerfile.searxng`, `searxng-settings.yml`, `docker-compose.ai-sandbox.yml`, `searxng-entrypoint-wrapper.sh` (new)
**What:**
- `gitea_private.py` — forked from SearXNG's built-in `gitea.py` engine, with one addition: an `Authorization: token <key>` header, so repos private to that token's owner are included (the stock engine sends no credential at all, so private repos never surface there). `inactive: true` in settings until a real `GITEA_API_KEY` is set (see below) — its `setup()` hard-fails on an empty key, which would otherwise silently drop just that one engine at load (confirmed: a `setup()` exception is caught per-engine, not fatal to the whole instance — checked `searx/engines/__init__.py:call_engine_setup`), but `inactive` avoids even that.
- `shlink.py` — new engine for a self-hosted [Shlink](https://shlink.io) instance's go-links (`GET /rest/v3/short-urls?searchTerm=`, `X-Api-Key` header auth, Shlink API v3).
- Both point at plain-`http://` LAN addresses (Gitea `192.168.1.134:3000`, Shlink `192.168.1.6:8207` — same backends Traefik itself uses) and both need `enable_http: true` in their settings.yml entries: SearXNG rejects plain-`http://` per engine by default (`ENGINE_DEFAULT_ARGS["enable_http"] = False`) and raises `InvalidSchema` rather than silently going cleartext — took real debugging to trace (see "Found by" below), not an obvious error message.
- **API keys never land in git.** `searxng-settings.yml`'s `engines:` entries hold placeholder tokens (`__GITEA_API_KEY__`, `__SHLINK_API_KEY__`), not real secrets. `docker-compose.ai-sandbox.yml` mounts the tracked file to `/etc/searxng/settings.yml.template` (not `settings.yml` directly) and passes `GITEA_API_KEY`/`SHLINK_API_KEY` as container env vars (from `.env`, gitignored as usual). `searxng-entrypoint-wrapper.sh` — the image's new `ENTRYPOINT` — `sed`-substitutes the placeholders into the real `/etc/searxng/settings.yml` at container start, then execs the stock entrypoint unchanged. `sed`, not `envsubst`: this Void Linux runtime image has neither `envsubst` nor a package manager to install it with (same reason the BM25 install bootstraps/strips `pip` via `ensurepip` instead of `xbps`).
- Engine source files live in a new top-level `searxng-engines/` directory, not under `examples/` — `.dockerignore` explicitly excludes `examples/` from the build context (`COPY` failed with "not found" until moved).
**Why:** Requested: search across private Gitea repos and Shlink go-links from the same SearXNG instance already indexing web results. True per-request OIDC identity forwarding isn't something SearXNG's engine model supports (one static credential per engine, not a per-browser-session relay) — flagged this explicitly before building, and a single scoped Gitea PAT is an accepted tradeoff since SearXNG here is already internal-LAN-only, reachable by one person.
**Found by:** first real search crashed silently (`unresponsive_engines: [['shlink', 'unexpected crash']]`, zero results) despite connectivity/auth both verified correct (direct `wget` from inside the container against Shlink's API succeeded, 29 short URLs returned). Root cause needed reproducing the exact request path inside the running container (`docker exec` + a Python script replicating `OnlineProcessor._search_basic`'s exact `request_args` construction) to get past a misleadingly generic `curl_cffi.requests.exceptions.InvalidSchema` down to `searx/network/client.py:36` — `enable_http` gating, not a URL-formatting bug.
**Revisit if:** `GITEA_API_KEY` gets set in `.env` — remove or flip `inactive: true` to `false`/absent on the `gitea (private)` engine entry in `searxng-settings.yml` to activate it. Scope that PAT to `read:repository` only (add `read:user` if org/team-only repos should also be searchable).

## Review process for future upstream releases

1. `git fetch upstream`
2. `git log homelab-main..upstream/main --oneline` — see what changed
3. Check whether any upstream commit touches `Dockerfile.runner`'s Corepack step, or the runner security flags in `docker-compose.yml` — if so, divergence #1 or #2 above may need to be re-evaluated or dropped
4. `git merge upstream/main` (or cherry-pick specific commits) into a throwaway branch, resolve conflicts, rebuild in isolation (`docker compose build`, no `up`) before cutting over
5. Follow the same backup-before-cutover pattern as any version bump: tag current images, dump the DB, copy `.env`, then `up -d --build`
6. For SearXNG specifically: check the [searxng-bm25-reranker](https://github.com/Oaklight/searxng-bm25-reranker) repo for compatibility before bumping `SEARXNG_VERSION` past a major schema change — the plugin-loading key format (`plugins:` with full module paths) has already changed once upstream.
