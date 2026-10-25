"""Thin wrapper so `python -m evals.run_evals` also works from the repo root."""
import sys

from prime.evals import main

if __name__ == "__main__":
    sys.exit(main(live="--live" in sys.argv))
