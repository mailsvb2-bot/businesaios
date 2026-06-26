# Baseline contract matrix

This contour makes baseline requirements executable.

Each baseline item has:

- a stable requirement id;
- a domain;
- a concrete pytest scenario reference;
- required gates that must include the baseline-contract step.

The matrix is defined in `scripts/ci/baseline_contract.py` and enforced by `scripts/ci/step_baseline_contract.py`.

Required CI visibility:

- `fast`
- `full`
- `pre-release`
- `release`

The release gate sees the matrix before verify-release and build-artifact.
