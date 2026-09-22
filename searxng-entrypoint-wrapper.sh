#!/bin/sh
# Renders /etc/searxng/settings.yml.template (bind-mounted from the tracked
# searxng-settings.yml, which holds only placeholder tokens - no real
# secrets ever land in git) into /etc/searxng/settings.yml (container-local,
# not bind-mounted) by substituting env vars, then hands off to the base
# image's real entrypoint.
#
# sed, not envsubst: this Void Linux runtime image ships neither envsubst
# nor a package manager to install it with (confirmed - same reason
# Dockerfile.searxng bootstraps/strips pip via ensurepip instead of xbps).
set -e

TEMPLATE=/etc/searxng/settings.yml.template
RENDERED=/etc/searxng/settings.yml

if [ -f "$TEMPLATE" ]; then
  sed \
    -e "s|__GITEA_API_KEY__|${GITEA_API_KEY:-}|g" \
    -e "s|__SHLINK_API_KEY__|${SHLINK_API_KEY:-}|g" \
    "$TEMPLATE" > "$RENDERED"
fi

exec /usr/local/searxng/entrypoint.sh "$@"
