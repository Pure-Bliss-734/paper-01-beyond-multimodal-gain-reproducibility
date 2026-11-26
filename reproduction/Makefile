PYTHON_SIM ?= .venv-sim/bin/python
PYTHON_MELD ?= .venv-meld/bin/python
export TZ := UTC
export PYTHONDONTWRITEBYTECODE := 1
export OMP_NUM_THREADS := 1
export OPENBLAS_NUM_THREADS := 1
export VECLIB_MAXIMUM_THREADS := 1
.PHONY: reproduce simulation empirical floor meld
reproduce: simulation empirical floor meld
simulation:
	$(PYTHON_SIM) analysis/run_simulation.py --config config/simulation.json --output-dir rerun_results/simulation
	$(PYTHON_SIM) analysis/verify_simulation_rerun.py --reference canonical_results/simulation --candidate rerun_results/simulation
empirical:
	Rscript analysis/run_empirical_reproduction.R . rerun_results/empirical
	Rscript analysis/verify_empirical_rerun.R canonical_results/empirical rerun_results/empirical
floor:
	Rscript analysis/run_nhanes_floor_diagnostics.R . rerun_results/floor
	Rscript analysis/verify_empirical_rerun.R canonical_results/floor_diagnostics rerun_results/floor
meld:
	$(PYTHON_MELD) analysis/run_meld_reproduction.py --config config/meld_reproduction.json --data-dir input_data --output-dir rerun_results/meld
	$(PYTHON_MELD) analysis/verify_meld_rerun.py --reference canonical_results/meld --candidate rerun_results/meld
	$(PYTHON_MELD) analysis/verify_folds.py
