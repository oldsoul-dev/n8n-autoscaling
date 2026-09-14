#!/usr/bin/env bash
# Generates the three secrets docker-compose.yml requires (N8N_ENCRYPTION_KEY,
# POSTGRES_PASSWORD/POSTGRES_APP_PASSWORD, N8N_USER_MANAGEMENT_JWT_SECRET) and
# writes them into .env in place. Run from the repo root:
#   ./generate-secrets.sh
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "No .env found - copying .env.example to .env first."
  cp .env.example .env
fi

# BSD sed (macOS) needs -i '' ; GNU sed needs -i with no arg. Detect once.
if sed --version >/dev/null 2>&1; then
  SED_INPLACE=(-i)
else
  SED_INPLACE=(-i '')
fi

ENC_KEY=$(openssl rand -hex 32)
PG_PASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
JWT_SECRET=$(openssl rand -base64 32 | tr -d '/+=')

sed "${SED_INPLACE[@]}" "s|^N8N_ENCRYPTION_KEY=.*|N8N_ENCRYPTION_KEY=${ENC_KEY}|" .env
sed "${SED_INPLACE[@]}" "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PG_PASS}|" .env
sed "${SED_INPLACE[@]}" "s|^POSTGRES_APP_PASSWORD=.*|POSTGRES_APP_PASSWORD=${PG_PASS}|" .env
sed "${SED_INPLACE[@]}" "s|^N8N_USER_MANAGEMENT_JWT_SECRET=.*|N8N_USER_MANAGEMENT_JWT_SECRET=${JWT_SECRET}|" .env

echo "Wrote fresh N8N_ENCRYPTION_KEY, POSTGRES_PASSWORD/POSTGRES_APP_PASSWORD, and N8N_USER_MANAGEMENT_JWT_SECRET into .env"
echo "Keep .env out of git - it already is (.gitignore covers .env / .env.*)"
