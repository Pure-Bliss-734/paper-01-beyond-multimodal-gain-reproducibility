"""Verify the distributed input contracts and frozen result-file identities."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    root = parser.parse_args().root
    manifest = json.loads((root/'checksums.json').read_text())
    for name, expected in manifest.items():
        path = root/name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Content mismatch for ' + name)
    files = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if files != set(manifest) | {'checksums.json'}:
        raise ValueError('File list mismatch')
    def read_table(name):
        with (root/'input_data'/name).open(newline='') as stream:
            return list(csv.DictReader(stream))
    nhanes = read_table('nhanes_analysis_public.csv')
    meld = read_table('meld_reanalysis_pairs.csv')
    crosscheck = read_table('crosscheck_cluster_cells.csv')
    if (len(nhanes), sum(row['Y_primary']=='1' for row in nhanes)) != (6565,903):
        raise ValueError('NHANES population mismatch')
    if (len(meld),len({r['dialogue_id'] for r in meld})) != (2330,268):
        raise ValueError('MELD grouping mismatch')
    if len({r['cluster'] for r in crosscheck}) != 60:
        raise ValueError('CrossCheck grouping mismatch')
    print(json.dumps({'PACKAGE_VALIDATION':'PASS','verified_files':len(files),'NHANES_rows':len(nhanes),'MELD_pairs':len(meld),'CrossCheck_clusters':60}))

if __name__ == '__main__':
    main()
