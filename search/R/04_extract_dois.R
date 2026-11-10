source(file.path(Sys.getenv("FLORA_PROJECT_ROOT", unset = getwd()), "R/00_config.R"))

DOI_RE <- regex("10\\.[0-9]{4,9}/[^\\s|}\\]<>\"'\\\\)]+", ignore_case = TRUE)

decode_doi <- function(x) {
  x <- str_replace_all(x, fixed("%2F"), "/")
  x <- str_replace_all(x, fixed("%2f"), "/")
  x <- str_replace_all(x, fixed("%3C"), "<")
  x <- str_replace_all(x, fixed("%3c"), "<")
  x <- str_replace_all(x, fixed("%3E"), ">")
  x <- str_replace_all(x, fixed("%3e"), ">")
  x <- str_replace_all(x, fixed("%3B"), ";")
  x <- str_replace_all(x, fixed("%3b"), ";")
  x <- str_replace_all(x, fixed("%28"), "(")
  x <- str_replace_all(x, fixed("%29"), ")")
  str_to_lower(x)
}

clean_doi <- function(x) {
  x <- decode_doi(x)
  x <- str_replace(x, "[\\.,;:\\)\\]\\}'\"\\?#]+$", "")
  x <- str_replace(x, "</?(ref|nowiki).*$", "")
  x
}

extract_dois_from_text <- function(text) {
  if (is.na(text) || !nzchar(text)) return(character())
  matches <- str_extract_all(text, DOI_RE)[[1]]
  matches |> clean_doi() |> unique()
}

extract_dois_for_page <- function(lang, pageid) {
  path <- file.path(WIKITEXT_DIR, lang, paste0(pageid, ".txt"))
  if (!file_exists(path)) return(character())
  text <- paste(readLines(path, warn = FALSE), collapse = "\n")
  extract_dois_from_text(text)
}

build_article_dois <- function(lang = LANG) {
  pages <- dir_ls(file.path(WIKITEXT_DIR, lang), recurse = TRUE, type = "file", glob = "*.txt")
  cli_alert_info("Extracting DOIs from {length(pages)} cached articles")

  rows <- map(pages, function(p) {
    parts <- str_split(p, "/", simplify = FALSE)[[1]]
    lang <- parts[length(parts) - 1]
    pageid <- as.integer(str_remove(parts[length(parts)], "\\.txt$"))
    text <- paste(readLines(p, warn = FALSE, encoding = "UTF-8"), collapse = "\n")
    dois <- extract_dois_from_text(text)
    if (length(dois) == 0) return(NULL)
    tibble(lang = lang, pageid = pageid, doi = dois)
  })

  if (!length(rows) || all(vapply(rows, is.null, logical(1))))
    return(tibble(lang = character(), pageid = integer(), doi = character()))
  bind_rows(rows)
}
