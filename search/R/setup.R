# One-time setup; no paid services or credentials.
packages <- c("httr2", "dplyr", "readr", "tidyr", "stringr", "purrr", "jsonlite",
              "nanoparquet", "fs", "glue", "cli")
missing <- packages[!vapply(packages, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) install.packages(missing, repos = "https://cloud.r-project.org")
cat("Dependencies ready\n")
