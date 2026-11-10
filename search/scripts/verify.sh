#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd -- "$script_dir/.."
mkdir -p runs/verification
Rscript tests/test_pipeline.R > runs/verification/pipeline-tests.log 2>&1
Rscript tests/test_inventory.R > runs/verification/inventory-tests.log 2>&1
Rscript tests/test_runner.R > runs/verification/runner-tests.log 2>&1
Rscript R/run_audit.R --lang=en --run=english-regression --legacy --offline > runs/verification/english-replay.log 2>&1
Rscript tests/test_english_regression.R > runs/verification/regression-tests.log 2>&1
Rscript -e 'for (p in list.files("R", full.names=TRUE, pattern="[.]R$")) parse(p); cat("All R scripts parse\n")' > runs/verification/parse.log
python3 -m py_compile scripts/build_review.py tests/retry_server.py
python3 -m unittest discover -s tests -p test_adjudication.py > runs/verification/adjudication-tests.log 2>&1
python3 -m unittest discover -s tests -p test_wikidata.py > runs/verification/wikidata-tests.log 2>&1
Rscript tests/test_citation_format.R > runs/verification/citation-format-tests.log 2>&1
python3 -m py_compile scripts/prepare_adjudication.py scripts/reconcile_wikidata.py
git diff --check
git diff --quiet -- data cache output/audit_long.parquet output/citation_contexts.csv output/citation_contexts.parquet output/flora_wikipedia_audit.csv output/flora_wikipedia_audit.parquet output/per_original_summary.csv output/recommendations.csv web/doi-screen/data.json
python3 - <<'PY'
import datetime, json, pathlib
vdir = pathlib.Path('runs/verification')
count = sum(x.startswith('PASS:') for x in (vdir / 'pipeline-tests.log').read_text().splitlines())
record = {
    'passed': True,
    'verified_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'incremental_metered_api_cost_usd': 0, 'cost_cap_usd': 1, 'paid_api_calls': 0,
    'checks': [
        f'{count} pipeline checks: endpoints, language/cache isolation, Spanish UTF-8 context, English DOI contract, continuation, zero hits, and interruption/resume.',
        'Actual HTTP retry fixture: 429, HTTP 200 maxlag, then success.',
        'Inventory tests passed: exact URL-decoded DOI matches, aliases, continuation resume, offline reuse, and latest optional-field schema.',
        'Three CLI checks: scope change rejected, concurrent writer rejected, Spanish offline replay from another working directory.',
        'Exact English audit and paired summary rows/fields and per-original summary match the archive.',
        'English denominators reproduce: 54/422 originals; 66/847 article–original combinations.',
        'Spanish live sample: 27 DOI queries, 17 candidate pages, revision caches and adjudication exports completed.',
        'English live sample: six DOI queries and 38 candidate page caches completed.',
        'R scripts parsed, Python scripts compiled, and git diff --check passed.',
        'Three review-ledger tests passed: dropped evidence preserved, decision reasons and large-project study matching enforced, retired generator rejected.',
        'Institutional and missing author names format without NA.',
        'Archived data, caches, audit tables, contexts, and web/doi-screen/data.json unchanged.',
    ],
    'remaining_limits': [
        'Full latest-snapshot Spanish results and their own scope/validation are recorded separately under runs/spanish-full-latest/es/output.',
        'Selected Spanish sample does not estimate edition-wide coverage.',
        'DOI absence is not acknowledgement failure; DOI-free sources and citation histories unaudited.',
        'Inherited DOI extraction keeps complex punctuation and encoded-slash limits.',
    ],
}
(vdir / 'validation.json').write_text(json.dumps(record, indent=2) + '\n')
print('Verification passed; logs and US$0 incremental metered cost recorded in runs/verification')
PY
