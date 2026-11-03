"""Solve one experiment; experiments.sh owns the parameter sweep."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
from time import perf_counter

import numpy as np
import pulp

if __package__:
    from .main import solve_problem, variable, hubs_flow, generate_dot
else:
    from main import solve_problem, variable, hubs_flow, generate_dot

SUMMARY_FIELDS = [
    "schema_version", "instance", "n", "p", "r", "alpha", "lamb", "delta",
    "effective_capacity", "status", "solution_status", "has_solution",
    "objective", "build_seconds", "solve_seconds", "total_seconds",
    "solver_log_path", "error",
]


def _positive_finite(value: float, name: str) -> float:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return value


def _read_metadata(path: Path, capacity: float | None) -> tuple[int, list[float]]:
    """Read dimensions and capacities, preferring the input capacity row."""
    with path.open(encoding="utf-8") as handle:
        n = int(handle.readline())
        if n <= 0:
            raise ValueError("n must be positive")
        data = np.loadtxt(handle, ndmin=2)
    if data.shape not in ((2*n, n), (2*n+1, n)):
        raise ValueError("Expected two n-by-n matrices and an optional capacity row")
    if not np.isfinite(data).all() or (data < 0).any():
        raise ValueError("Instance values must be finite and nonnegative")
    if len(data) == 2*n+1:
        capacities = data[2*n].tolist()
    elif capacity is not None:
        capacities = [_positive_finite(capacity, "capacity")] * n
    else:
        raise ValueError("Instance has no capacity row; pass --capacity")
    for value in capacities:
        _positive_finite(value, "effective capacity")
    return n, capacities


def _solution_state(prob: pulp.LpProblem) -> tuple[bool, str]:
    if prob.sol_status not in (pulp.LpSolutionOptimal, pulp.LpSolutionIntegerFeasible):
        return False, "none"
    if not prob.valid(1e-5):
        return False, "none"
    if prob.sol_status == pulp.LpSolutionOptimal and prob.status == pulp.LpStatusOptimal:
        return True, "optimal"
    return True, "feasible_incumbent"


def _save_result(path: Path, result: dict) -> None:
    temporary = path.with_suffix(".json.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def main() -> int:
    """Run a single case and persist JSON, summary CSV, CBC log and DOT.

    Return 1 on execution errors; infeasibility is a recorded solver outcome.
    Node indices in JSON and DOT are zero-based.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance", type=Path)
    parser.add_argument("--p", type=int, required=True)
    parser.add_argument("--r", type=int, required=True)
    parser.add_argument("--alpha", type=float, required=True)
    parser.add_argument("--capacity", type=float)
    parser.add_argument("--time-limit", type=float, default=60)
    parser.add_argument("--session", type=Path, required=True)
    args = parser.parse_args()
    try:
        _positive_finite(args.time_limit, "time-limit")
        if args.capacity is not None:
            _positive_finite(args.capacity, "capacity")
        if not math.isfinite(args.alpha) or not 0 < args.alpha <= 1:
            raise ValueError("alpha must be finite and in (0, 1]")
        instance = args.instance.expanduser().resolve()
        n, capacities = _read_metadata(instance, args.capacity)
        if not 1 <= args.r <= args.p <= n:
            raise ValueError("Require 1 <= r <= p <= n")
    except (ValueError, OSError) as exc:
        parser.error(str(exc))

    args.session.mkdir(parents=True, exist_ok=True)
    tag = hashlib.sha1(str(instance).encode("utf-8")).hexdigest()[:10]
    stem = f"{instance.stem}-{tag}-p{args.p}-r{args.r}-a{args.alpha!r}"
    log_path = args.session / f"{stem}.cbc.log"
    dot_path = args.session / f"{stem}.cbc.dot"
    result = dict(
        schema_version=1, instance=str(instance), n=n, p=args.p, r=args.r,
        alpha=args.alpha, lamb=1.0, delta=1.0, effective_capacity=capacities,
        status="not_run", solution_status="none", has_solution=False,
        objective=None, build_seconds=None, solve_seconds=None, total_seconds=None,
        hubs=[], allocations=[], routes=[], hub_flows={}, dot_path=None,
        solver_log_path=str(log_path.resolve()), error=None,
    )
    started = perf_counter()
    try:
        prob, w, build_seconds, solve_seconds = solve_problem(
            str(instance), args.p, args.r, capacities, args.alpha,
            time_limit=args.time_limit, log_path=str(log_path),
        )
        result.update(build_seconds=build_seconds, solve_seconds=solve_seconds,
                      status=pulp.LpStatus.get(prob.status, str(prob.status)))
        valid, state = _solution_state(prob)
        result.update(has_solution=valid, solution_status=state)
        if state == "feasible_incumbent":
            result["status"] = "Feasible (not proven optimal)"
        elif not valid and result["status"] == "Optimal":
            result["status"] = "No validated solution"
        if valid:
            z, x = variable(prob, "z"), variable(prob, "x")
            result.update(
                objective=float(pulp.value(prob.objective) or 0.0),
                hubs=sorted(k for (i, k), value in z.items() if i == k and value > .5),
                allocations=[[i, k] for (i, k), value in sorted(z.items()) if value > .5],
                routes=[[i, j, k, l, float(value)] for (i, j, k, l), value in sorted(x.items()) if value > 1e-7],
                hub_flows=hubs_flow(z, x, w),
            )
            generate_dot(z, x, w, str(dot_path))
            result["dot_path"] = str(dot_path.resolve())
    except (Exception, SystemExit) as exc:
        result.update(status="error", error=f"{type(exc).__name__}: {exc}")
    result["total_seconds"] = perf_counter() - started
    json_path = args.session / f"{stem}.json"
    _save_result(json_path, result)
    summary_path = args.session / "summary.csv"
    new = not summary_path.exists() or summary_path.stat().st_size == 0
    summary = {key: result[key] for key in SUMMARY_FIELDS}
    summary["effective_capacity"] = json.dumps(capacities)
    # Shell executes cases sequentially, so each process appends one row.
    with summary_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        if new:
            writer.writeheader()
        writer.writerow(summary)
        handle.flush()
        os.fsync(handle.fileno())
    print(f"[{result['status']}] objective={result['objective']} — {json_path}", flush=True)
    return 1 if result["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
