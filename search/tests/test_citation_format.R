script <- sub('^--file=', '', grep('^--file=',commandArgs(),value=TRUE)[1])
source(file.path(dirname(script),'../R/citation_format.R'))
row <- list(author_r='Open Science Collaboration', title_r='Estimating reproducibility', doi_r='10.1126/science.aac4716')
x <- build_cite_template(row)
stopifnot(grepl('|author1=Open Science Collaboration',x,fixed=TRUE),!grepl('=NA',x,fixed=TRUE))
row$author_r <- '[{"family":"García","given":null}]'
x <- build_cite_template(row)
stopifnot(grepl('|last1=García',x,fixed=TRUE),!grepl('|first1=',x,fixed=TRUE),!grepl('=NA',x,fixed=TRUE))
cat('PASS: institutional and absent author names are formatted without NA\n')
