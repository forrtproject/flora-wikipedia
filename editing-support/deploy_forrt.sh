#!/usr/bin/env bash
# Rebuild the review cards and publish them to https://forrt.org/flora-wikipedia/ (GitHub Pages, gh-pages).
# gh-pages is replaced by one commit holding the staged site (WIP banner, "private" wording rewritten) plus
# card-layouts/index.html, which forwards old mock-up links (?layout=…#card) to the main cards.
#   editing-support/deploy_forrt.sh          # from the repository root, on an up-to-date, pushed main
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/.." && pwd)"
built="$repo/../flora-wikipedia-edit-prototype-20261006"
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
[[ -z "$(git -C "$repo" status --porcelain -- editing-support)" ]] || { echo "editing-support has uncommitted changes" >&2; exit 1; }
rev="$(git -C "$repo" rev-parse --short HEAD)"
(cd "$here" && python3 build_site.py --output-dir "$built" >/dev/null)
rmdir "$stage" && python3 "$here/stage_public.py" "$built" "$stage" --wip >/dev/null
touch "$stage/.nojekyll"
mkdir "$stage/card-layouts"
cat > "$stage/card-layouts/index.html" <<'EOF'
<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="robots" content="noindex, nofollow">
<title>Review cards moved</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='90'%3E🔁%3C/text%3E%3C/svg%3E">
<script>location.replace('../' + location.search + location.hash);</script></head>
<body><p>The card layouts are now part of the main review cards: <a href="../">forrt.org/flora-wikipedia</a>.</p></body></html>
EOF
git -C "$stage" init -q -b gh-pages
git -C "$stage" add -A
git -C "$stage" -c user.name="$(git -C "$repo" config user.name)" -c user.email="$(git -C "$repo" config user.email)" \
  commit -q -m "Publish review cards ($rev); card-layouts/ redirects to the main cards"
git -C "$stage" push -q -f "$(git -C "$repo" remote get-url origin)" gh-pages
for _ in $(seq 1 30); do
  [[ "$(gh api repos/forrtproject/flora-wikipedia/pages/builds/latest --jq .status)" == built ]] && break
  sleep 8
done
echo "Published $rev: https://forrt.org/flora-wikipedia/ (Pages: $(gh api repos/forrtproject/flora-wikipedia/pages/builds/latest --jq .status))"
