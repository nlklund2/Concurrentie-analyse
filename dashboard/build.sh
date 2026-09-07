#!/bin/bash
# Netlify-buildstap: schrijft dashboard/config.js uit omgevingsvariabelen.
# Stel SUPABASE_URL en SUPABASE_ANON_KEY in via Netlify > Site settings >
# Environment variables. De anon-key is een publieke client-sleutel; de
# toegang tot data wordt afgedwongen door Row Level Security + login.
#
# Preview naast productie (docs/foldermonitor-plan.md §9.5): buiten de
# productiecontext (deploy previews van PR's en branch deploys) leest het
# dashboard het PREVIEW-project zodra PREVIEW_SUPABASE_URL en
# PREVIEW_SUPABASE_ANON_KEY gezet zijn. Netlify zet CONTEXT zelf
# (production | deploy-preview | branch-deploy). De productiewaarden
# blijven onaangeraakt; zonder PREVIEW_-variabelen gedraagt de build zich
# als voorheen.
set -euo pipefail
: "${SUPABASE_URL:?Zet SUPABASE_URL als omgevingsvariabele in Netlify}"
: "${SUPABASE_ANON_KEY:?Zet SUPABASE_ANON_KEY als omgevingsvariabele in Netlify}"

URL="$SUPABASE_URL"
KEY="$SUPABASE_ANON_KEY"
OMGEVING="productie"
if [ "${CONTEXT:-production}" != "production" ] \
   && [ -n "${PREVIEW_SUPABASE_URL:-}" ] && [ -n "${PREVIEW_SUPABASE_ANON_KEY:-}" ]; then
  URL="$PREVIEW_SUPABASE_URL"
  KEY="$PREVIEW_SUPABASE_ANON_KEY"
  OMGEVING="preview"
fi

cat > "$(dirname "$0")/config.js" <<EOT
window.MONITOR_CONFIG = {
  url: "${URL}",
  anonKey: "${KEY}",
  omgeving: "${OMGEVING}",
};
EOT
echo "dashboard/config.js aangemaakt (context ${CONTEXT:-production} → ${OMGEVING})."
