"""Compare the two frozen tuning records with the cross-fitted replay."""
import json
from pathlib import Path

for name in ('model_based_tuning_manifest.json', 'primary_fold_and_tuning_manifest.json'):
    reference = Path('canonical_results/meld/folds', name)
    result = Path('rerun_results/meld/folds', name)
    if json.loads(reference.read_text()) != json.loads(result.read_text()):
        raise SystemExit('Tuning or fold mismatch: ' + name)
print('Fold assignments and tuning records match.')
