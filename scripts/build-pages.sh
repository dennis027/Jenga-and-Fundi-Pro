#!/usr/bin/env sh
# Build both Angular portals as one static GitHub Pages site.
#
#   BASE_PATH=/<repo-name> [API_URL=https://api.example.com/] scripts/build-pages.sh
#
# Output (default ./_site):
#   _site/index.html        landing page linking to both portals
#   _site/fundi-pro/        worker portal    (base href BASE_PATH/fundi-pro/)
#   _site/jenga-pro/        contractor portal (base href BASE_PATH/jenga-pro/)
#   _site/404.html          sends unknown paths back to the right portal
# API_URL (optional) overrides src/environments/environment.prod.ts for this
# build only; the file is restored afterwards.
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
BASE_PATH=${BASE_PATH:-}
BASE_PATH=${BASE_PATH%/}
OUT=${OUT_DIR:-$ROOT/_site}

rm -rf "$OUT"
mkdir -p "$OUT"

build() {
  dir=$1 project=$2
  app="$ROOT/frontend/$dir"
  env_file="$app/src/environments/environment.prod.ts"
  echo "==> Building $dir (base href $BASE_PATH/$dir/)"
  cp "$env_file" "$env_file.bak"
  trap 'mv -f "$env_file.bak" "$env_file"' EXIT INT TERM
  if [ -n "${API_URL:-}" ]; then
    case "$API_URL" in */) ;; *) API_URL="$API_URL/" ;; esac
    printf "export const environment = {\n  production: true,\n  apiUrl: '%s'\n};\n" "$API_URL" > "$env_file"
  fi
  (cd "$app" && npm ci --no-audit --no-fund && \
    npx ng build --configuration production --base-href "$BASE_PATH/$dir/")
  mv -f "$env_file.bak" "$env_file"
  trap - EXIT INT TERM
  cp -R "$app/dist/$project/browser" "$OUT/$dir"
  # SPA entry for client-side routes that were not prerendered
  [ -f "$OUT/$dir/index.html" ] || cp "$OUT/$dir/index.csr.html" "$OUT/$dir/index.html"
}

build fundi-pro fundi-pro
build jenga-pro jenga-fundi-pro

touch "$OUT/.nojekyll"

cat > "$OUT/index.html" <<HTML
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Fundi / Jenga Pro</title>
  <style>
    body { margin: 0; min-height: 100vh; display: grid; place-items: center;
           font-family: system-ui, sans-serif; background: #f4f6f8; color: #1d2733; }
    main { padding: 2rem 1rem; text-align: center; }
    .apps { display: flex; gap: 1rem; flex-wrap: wrap; justify-content: center; margin-top: 1.5rem; }
    a { display: block; width: 15rem; padding: 1.25rem; border-radius: 12px; background: #fff;
        color: inherit; text-decoration: none; box-shadow: 0 1px 4px rgba(0,0,0,.12); }
    a:hover { box-shadow: 0 3px 12px rgba(0,0,0,.18); }
    strong { display: block; font-size: 1.2rem; margin-bottom: .35rem; }
    @media (prefers-color-scheme: dark) {
      body { background: #12171d; color: #e6ebf0; } a { background: #1c242d; }
    }
  </style>
</head>
<body>
  <main>
    <h1>Fundi / Jenga Pro</h1>
    <div class="apps">
      <a href="$BASE_PATH/fundi-pro/"><strong>Fundi Pro</strong>Worker portal</a>
      <a href="$BASE_PATH/jenga-pro/"><strong>Jenga Pro</strong>Contractor portal</a>
    </div>
  </main>
</body>
</html>
HTML

cat > "$OUT/404.html" <<HTML
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Redirecting…</title>
  <script>
    (function () {
      var base = "$BASE_PATH", p = location.pathname;
      ["fundi-pro", "jenga-pro"].forEach(function (app) {
        if (p.indexOf(base + "/" + app + "/") === 0) location.replace(base + "/" + app + "/");
      });
      if (p.indexOf(base + "/fundi-pro/") !== 0 && p.indexOf(base + "/jenga-pro/") !== 0) location.replace(base + "/");
    })();
  </script>
</head>
<body></body>
</html>
HTML

echo "==> Site ready in $OUT"
