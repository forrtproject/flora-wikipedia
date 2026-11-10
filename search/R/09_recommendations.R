# Retired prototype: preserve historical output, never regenerate insertion advice.
stop(paste(
  "Outcome-ranked insertion recommendations are retired.",
  "Use R/run_audit.R and scripts/prepare_adjudication.py for source-led human review.",
  "Historical code is retained as non-executable text in docs/archive/09_recommendations.R.txt."
))
