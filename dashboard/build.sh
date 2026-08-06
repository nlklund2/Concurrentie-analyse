#!/bin/bash
# Netlify-buildstap: schrijft dashboard/config.js uit omgevingsvariabelen.
# Stel SUPABASE_URL en SUPABASE_ANON_KEY in via Netlify > Site settings >
# Environment variables. De anon-key is een publieke client-sleutel; de
# toegang tot data wordt afgedwongen door Row Level Security + login.
set -euo pipefail
: "${SUPABASE_URL:?Zet SUPABASE_URL als omgevingsvariabele in Netlify}"
: "${SUPABASE_ANON_KEY:?Zet SUPABASE_ANON_KEY als omgevingsvariabele in Netlify}"

cat > "$(dirname "$0")/config.js" <<EOF
window.MONITOR_CONFIG = {
  url: "${SUPABASE_URL}",
  anonKey: "${SUPABASE_ANON_KEY}",
};
EOF
echo "dashboard/config.js aangemaakt."
