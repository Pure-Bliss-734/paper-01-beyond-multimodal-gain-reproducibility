# Beyond Multimodal Gain

Jiangwei Xue, Zhida Qin and Yuda Bi. [Manuscript and version history](https://zenodo.org/records/22704444).

| Paper result | Inputs and calculation | Reference |
|---|---|---|
| Tables 1–3, Figures 1–3 | Definitions, latent extensions and analytical constructions in the manuscript | Sections 2–7 and proofs |
| Table 4, Figures 4–5 | Simulation design, identified-set endpoints and finite-sample coverage | canonical_results/simulation |
| Tables 5 and 7 | Survey-weighted NHANES mortality witness, resampling and boundary diagnostics | canonical_results/empirical/nhanes and canonical_results/floor_diagnostics |
| Table 8 | CrossCheck cluster resampling and within-stratum permutation | canonical_results/empirical/crosscheck |
| Tables 6 and 9–12, Figure 6 | Frozen MELD pairs, nested dialogue-grouped prediction, subgroup and representation comparisons | canonical_results/meld |

## Verify the download

From the extracted package, supply the path to its ZIP.

<!-- RELEASE_COMMAND:verify -->
```sh
python3 tools/verify_release.py --archive <ARCHIVE_PATH>
```
<!-- END_RELEASE_COMMAND:verify -->

## Recompute the study

Install the two frozen Python environments and base R with its recommended packages. The upstream NHANES reconstruction also uses an R-compatible C compiler.

```sh
python3.11 -m venv .venv-sim
.venv-sim/bin/python -m pip install -r requirements-simulation-lock.txt
python3.14 -m venv .venv-meld
.venv-meld/bin/python -m pip install -r requirements-lock.txt
make reproduce
```

The four jobs generate new results in rerun_results and compare them with frozen references. The MELD check uses 111 numerical comparisons, the simulation compares tables and plotted pixels, and the R comparisons use exact output bytes. The primary MELD cluster intervals and the CrossCheck participant-bootstrap interval include zero. The NHANES witness measures observable dependence. Results do not establish a causal effect or calibrate positive channel floors.

## Input reconstruction

The five compact tables support offline replay. CrossCheck cells retain only the within-cluster grouping needed for the bootstrap and the weighted tables for the fixed permutation draws. MELD retains transformed features, adjacent-pair keys, labels and dialogue grouping. NHANES retains the outcome, discretized variables and sampling design needed for the weighted comparisons. The grouped records should be handled under the source data terms.

For optional upstream reconstruction, run the following from the extracted package. It downloads the specific external sources in upstream/sources.json and can require about 20 GiB of scratch space.

```sh
.venv-meld/bin/python upstream/rebuild_inputs.py
```

This workflow starts from the public cleaned CrossCheck daily series, MELD dialogue labels and MM-Align sequence features, and official NHANES survey, mortality and accelerometer records. It compares the reconstructed scientific fields against the five compact inputs. Raw phone-sensor cleaning and neural feature extraction from audio or video are outside the reported calculation.

Author-owned analysis code uses the MIT license. Author-created documentation and reference results use CC BY 4.0. Third-party data and derivatives retain their upstream terms. See [license terms](LICENSE).
