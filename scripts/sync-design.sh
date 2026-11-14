#!/usr/bin/env sh
# Copy the shared design system (frontend/design-system/) into both portals.
#   scripts/sync-design.sh          copy
#   scripts/sync-design.sh --check  fail if a portal's copy differs (CI)
set -eu
MODE=copy
[ "${1:-}" = "--check" ] && MODE=check
ROOT=$(cd "$(dirname "$0")/.." && pwd)
DS="$ROOT/frontend/design-system"
status=0
for app in fundi-pro jenga-pro; do
  A="$ROOT/frontend/$app/src"
  set -- \
    "$DS/styles.css:$A/styles.css" \
    "$DS/custom-theme.scss:$A/custom-theme.scss" \
    "$DS/theme.ts:$A/app/services/theme.ts" \
    "$DS/install.ts:$A/app/services/install.ts" \
    "$DS/i18n.ts:$A/app/services/i18n.ts" \
    "$DS/shell/types.ts:$A/app/shell/types.ts" \
    "$DS/shell/site-context.ts:$A/app/shell/site-context.ts" \
    "$DS/shell/ui.ts:$A/app/shell/ui.ts" \
    "$DS/shell/main.ts:$A/app/components/main/main.ts" \
    "$DS/shell/main.html:$A/app/components/main/main.html" \
    "$DS/shell/main.css:$A/app/components/main/main.css"
  for pair in "$@"; do
    src=${pair%%:*}; dst=${pair#*:}
    if [ "$MODE" = check ]; then
      cmp -s "$src" "$dst" || { echo "out of sync: ${dst#$ROOT/}"; status=1; }
    else
      mkdir -p "$(dirname "$dst")"; cp "$src" "$dst"
    fi
  done
done
[ "$MODE" = check ] && [ $status -eq 0 ] && echo "design system in sync"
exit $status
