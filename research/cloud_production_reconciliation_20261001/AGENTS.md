# Cloud lineage diagnostics

- Audit saved artifacts and cached inputs without calling the daily CLI, fitting models, sending notifications, deploying, or writing production state. Verify input hashes before and after each diagnostic and pin the snapshot expectations explicitly.
- Distinguish selector replay from model replay. Equal source syntax or cached feature probes do not prove a fresh raw-data-to-model replay, and a diagnostic PASS does not certify production profitability.
- Candidate condition changes must demonstrate performance at least equal to the current Cloud on comparable inputs and explicitly address the published reference. Beating a corrected research baseline alone does not meet this requirement. Report win rate, mean, median, major losses, concentration, count and capital; label maxima by their metric and search scope and do not adopt a post-hoc maximum automatically.
- Match input coverage before attributing identity differences. Count price/volume gate failures separately from eligible-but-unselected rows; overlapping exclusion reasons must not be summed as separate trades.
- Compare old teacher labels only within the named subset; never report Tail-subset label changes as full-training-corpus changes. Preserve the corrected actual-session units rather than retuning to reproduce a legacy headline.
