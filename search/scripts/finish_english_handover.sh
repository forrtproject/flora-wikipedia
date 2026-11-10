#!/usr/bin/env bash
# Run only after the live English writer has finished successfully.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
if systemctl --user is-active --quiet flora-english-full-gh.service; then
  echo 'Live writer is still active; refusing concurrent replay' >&2; exit 1
fi
python3 - <<'PY'
import json,pathlib
m=json.loads(pathlib.Path('runs/english-full-gh/en/output/manifest.json').read_text())
assert m['status']=='complete',m['status']
PY
sha256sum runs/english-full-gh/en/output/summary.json runs/english-full-gh/en/output/flora_wikipedia_audit.csv runs/english-full-gh/en/output/per_original_summary.csv runs/english-full-gh/en/output/citation_contexts.csv runs/english-full-gh/en/output/adjudication_pairs.csv > runs/english-full-gh/en/output/offline-before.sha256
Rscript R/run_audit.R --lang=en --run=english-full-gh --discovery=inventory --offline > runs/english-full-gh/en/output/offline-verification.log 2>&1
sha256sum -c runs/english-full-gh/en/output/offline-before.sha256 > runs/english-full-gh/en/output/offline-byte-check.log
Rscript -e 'Sys.setenv(FLORA_PROJECT_ROOT=getwd(), FLORA_RUN_DIR=file.path(getwd(),"runs/english-full-gh/en"), FLORA_LANG="en", FLORA_OFFLINE="1"); source("R/00_config.R"); print(sessionInfo())' > runs/english-full-gh/en/output/verification-session-info.txt
Rscript scripts/validate_full_run.R english-full-gh en > runs/english-full-gh/en/output/full-validation.log 2>&1
python3 scripts/prepare_adjudication.py --run-dir runs/english-full-gh/en --run-dir runs/spanish-full-latest/es --output runs/editathon-review
python3 scripts/select_calibration.py --packets runs/editathon-review/packets.json --output runs/editathon-review/calibration.json
python3 scripts/reconcile_wikidata.py --packets runs/editathon-review/packets.json --output runs/wikidata-sample --offline
python3 scripts/build_programme_review.py --output-dir ../flora-wikipedia-review-20261003
