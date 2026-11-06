#!/usr/bin/env bash
# One-command rebuild of the English edit-suggestion prototype.
# Offline by default: selection, evidence packets and the site are rebuilt from
# cached audit products, cached sources and existing drafts. Drafting itself is
# a separate, restartable step (see prototype/README.md).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
out="${PROTOTYPE_OUTPUT_DIR:-$here/../../flora-wikipedia-edit-prototype-20261006}"
refresh=""
[[ "${1:-}" == "--refresh-live" ]] && refresh="--refresh-live"
cd "$here"
env -u OPENROUTER_API_KEY -u OPENAI_API_KEY -u ANTHROPIC_API_KEY python3 select_pages.py
env -u OPENROUTER_API_KEY -u OPENAI_API_KEY -u ANTHROPIC_API_KEY python3 evidence.py $refresh
python3 validate_all.py
python3 build_site.py --output-dir "$out" ${refresh:+--fetch-labels}
