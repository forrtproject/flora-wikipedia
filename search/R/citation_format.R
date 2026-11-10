# Formatting aid only; source relevance and article wording require human review.
# Institutional authors use |authorN=; absent names are omitted, never rendered NA.
build_cite_template <- function(row) {
  present <- function(x) length(x) == 1L && !is.na(x) && nzchar(as.character(x))
  raw <- row$author_r
  authors <- if (present(raw)) tryCatch(jsonlite::fromJSON(raw), error=function(e) NULL) else NULL
  parts <- character()
  if (is.data.frame(authors)) {
    for (i in seq_len(min(nrow(authors), 9L))) {
      literal <- if ("literal" %in% names(authors)) authors$literal[i] else NA_character_
      family <- if ("family" %in% names(authors)) authors$family[i] else NA_character_
      given <- if ("given" %in% names(authors)) authors$given[i] else NA_character_
      if (present(literal)) parts <- c(parts, paste0("|author",i,"=",literal))
      else {
        if (present(family)) parts <- c(parts,paste0("|last",i,"=",family))
        if (present(given)) parts <- c(parts,paste0("|first",i,"=",given))
      }
    }
    if (nrow(authors)>9L) parts <- c(parts,"|display-authors=etal")
  } else if (present(raw)) parts <- c(parts,paste0("|author1=",raw))
  for (key in c("year","title","journal","volume","issue","pages","doi")) {
    value <- row[[paste0(key,"_r")]]
    if (present(value)) parts <- c(parts,paste0("|",key,"=",value))
  }
  paste0("<ref>{{cite journal ",paste(parts,collapse=" "),"}}</ref>")
}
