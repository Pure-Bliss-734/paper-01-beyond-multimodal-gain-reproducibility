# Derive the inputs used for participant resampling and conditional permutation replay.
write_crosscheck_tables <- function(pairs, out_dir, config) {
  cluster <- match(pairs$participant_id, unique(pairs$participant_id))
  cluster_size <- tabulate(cluster)
  if (max(abs(pairs$analysis_weight - 1 / cluster_size[cluster])) > 1e-12) {
    stop("Pair weights differ from the participant-equal weighting rule")
  }
  cells <- aggregate(
    list(count = rep(1L, nrow(pairs))),
    list(cluster = cluster, C = pairs$C, T = pairs$T, Y = pairs$Y, M = pairs$M),
    sum
  )
  cells <- cells[order(cells$cluster, cells$C, cells$T, cells$Y, cells$M), ]
  write.csv(cells, file.path(out_dir, "crosscheck_cluster_cells.csv"), row.names = FALSE)

  strata <- sort(unique(pairs$C))
  grid <- expand.grid(Y = 1:3, M = 1:3, T = 1:3, C = strata, stringsAsFactors = FALSE)
  # The same sampling order and RNG calls as the original conditional permutation.
  groups <- interaction(pairs[c("T", "C")], drop = TRUE, lex.order = TRUE)
  proxy_by_group <- split(pairs$M, groups)
  cell_base <- pairs$Y + 9L * (pairs$T - 1L) + 27L * (match(pairs$C, strata) - 1L)
  set.seed(config$seed + 20000L)
  draws <- lapply(seq_len(config$permutation_replicates), function(replicate) {
    permuted <- lapply(proxy_by_group, function(x) {
      if (length(x) > 1L) sample(x, length(x), replace = FALSE) else x
    })
    proxy <- unsplit(permuted, groups)
    cell <- cell_base + 3L * (proxy - 1L)
    mass <- rowsum(cbind(count = rep(1L, nrow(pairs)), weight = pairs$analysis_weight), cell)
    used <- as.integer(rownames(mass))
    data.frame(replicate = replicate, grid[used, ], count = as.integer(mass[, "count"]),
               weight = as.numeric(mass[, "weight"]), row.names = NULL)
  })
  write.csv(do.call(rbind, draws), file.path(out_dir, "crosscheck_permutation_cells.csv"),
            row.names = FALSE)
}
