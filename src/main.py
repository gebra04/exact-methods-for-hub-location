import argparse
import csv
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from time import perf_counter

import numpy as np
import numpy.typing as npt
import pulp

from build import build_problem


def read_args() -> tuple[str, str, int, int, list[float], float, float, float]:
    parser = argparse.ArgumentParser(description="Parameters for hub-location problem.")

    parser.add_argument(
        "dataset", type=str, help="path to the hub-location problem instance."
    )
    parser.add_argument("results", type=str, help="path to the results CSV file.")
    parser.add_argument("p", type=int, help="number of hubs to locate.")
    parser.add_argument(
        "r", type=int, help="maximum number of hubs each node may be allocated to."
    )
    parser.add_argument(
        "B",
        type=float,
        nargs="+",
        help="capacity of hub k (maximum total flow that can enter the hub).",
    )
    parser.add_argument(
        "alpha",
        type=float,
        help="inter-hub transfer discount factor (economies of scale).",
    )

    parser.add_argument(
        "--lamb", type=float, default=1.0, help="collection cost coefficient."
    )
    parser.add_argument(
        "--delta", type=float, default=1.0, help="distribution cost coefficient."
    )

    args = parser.parse_args()
    return (
        args.dataset,
        args.results,
        args.p,
        args.r,
        args.B,
        args.alpha,
        args.lamb,
        args.delta,
    )


def save_csv(
    prob: pulp.LpProblem,
    time: float,
    p: int,
    r: int,
    B: list[float],
    alpha: float,
    lamb: float,
    delta: float,
    hubs: list[int],
    flow: dict[int, float],
    path: str,
) -> None:
    """
    Saves the parameters used and additional information about the solution to the problem in the CSV file specified by the `path` parameter.

    To avoid cluttering the CSV file, only the first element of parameter `B` is saved.

    # Parameters:
    - prob (LpProblem): instance of the problem that has already been solved.
    - time (float): time spent resolving the problem.
    - p (int): number of hubs to locate.
    - r (int): maximum number of hubs each node may be allocated to.
    - B (list[float]): capacity of hub k.
    - alpha (float): inter-hub transfer discount factor (economies of scale).
    - lamb (float): collection cost coefficient.
    - delta (float): distribution cost coefficient.
    - hubs (list[int]): solution hubs.
    - flow (dict[int, float]): total flow passing through the hubs.
    - path (str): path to the CSV file.
    """

    columns = [
        "status",
        "objective",
        "time",
        "p",
        "r",
        "B",
        "alpha",
        "lamb",
        "delta",
        "hubs",
        "flow",
    ]
    status = pulp.LpStatus[prob.status]
    new = not os.path.exists(path)

    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(columns)

        w.writerow(
            [
                status,
                pulp.value(prob.objective),
                round(time, 4),
                p,
                r,
                B[0],
                alpha,
                lamb,
                delta,
                " ".join(map(str, hubs)),
                " ".join(f"{h}:{flow[h]:.4f}" for h in hubs),
            ]
        )


def variable(prob: pulp.LpProblem, prefix: str) -> dict[tuple[int, ...], float]:
    """
    Identifies the variables in the problem that begin with `prefix` and end with '_'. The returned value is a dictionary whose keys correspond to the indices of the variables.
    """

    values = {}
    for v in prob.variables():
        if v.name.startswith(prefix + "_"):
            idx = tuple(int(s) for s in re.findall(r"\d+", v.name[len(prefix) + 1 :]))
            values[idx] = v.varValue if v.varValue is not None else 0.0
    return values


def identify_hubs(z: dict[tuple[int, ...], float]) -> list[int]:
    """
    Identifies which variables are hubs and returns a list of their indices.
    """

    n = max(i for i, _ in z) + 1
    return [k for k in range(n) if z.get((k, k), 0) > 0.5]


def hubs_flow(
    z: dict[tuple[int, ...], float],
    x: dict[tuple[int, ...], float],
    w: npt.NDArray[np.float64],
    eps: float = 1e-9,
) -> dict[int, float]:
    """
    Returns a dictionary containing the total flow weighted by the weights `w` of each hub.
    """

    hubs = identify_hubs(z)
    flow = {h: 0.0 for h in hubs}

    for (i, j, k, l), val in x.items():
        if val <= eps:
            continue

        c = val * w[i][j]

        for h in {k, l}:
            if h in flow:
                flow[h] += c

    return flow


def generate_dot(
    z: dict[tuple[int, ...], float],
    x: dict[tuple[int, ...], float],
    w: npt.NDArray[np.float64],
    dot_path: str = "results/graph.dot",
    eps: float = 1e-6,
) -> None:
    """
    Generate a DOT description of the problem: dashed edges from non-hub nodes to their hubs, and solid edges between hubs labeled with the total flow.
    """

    n = max(i for i, _ in z) + 1
    hubs = {k for k in range(n) if z.get((k, k), 0) > 0.5}

    lines = ["digraph G {", "  rankdir=LR;", "  node [shape=circle];"]

    # Nodes and hubs.
    for i in range(n):
        if i in hubs:
            lines.append(
                f"  {i} [style=filled, fillcolor=lightblue, shape=doublecircle];"
            )
        else:
            lines.append(f"  {i};")

    # Allocation edges i -> k (dashed), only for non-hub nodes.
    for (i, k), val in sorted(z.items()):
        if val > 0.5 and i not in hubs:
            lines.append(f"  {i} -> {k} [style=dashed, color=gray];")

    # Total flow on each hub-to-hub edge k -> l.
    flows: dict[tuple[int, int], float] = {}
    for (i, j, k, l), val in x.items():
        if val > eps and k != l:
            demand = w[i][j] if w is not None else 1.0
            flows[(k, l)] = flows.get((k, l), 0.0) + val * demand

    max_flow = max(flows.values(), default=1.0)

    for (k, l), flow in sorted(flows.items()):
        # Edge thickness proportional to flow (between 1 and 5).
        width = 1 + 4 * flow / max_flow
        lines.append(
            f'  {k} -> {l} [color=red, penwidth={width:.2f}, label="{flow:.2f}"];'
        )

    lines.append("}")

    with open(dot_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def solve_problem(dataset, p, r, B, alpha, lamb=1.0, delta=1.0,
                  log_path=None):
    """Build and solve one case, returning model, demands and separate timings.

    Expand a uniform fallback capacity; capacities in the input take precedence.
    """
    with open(dataset, encoding="utf-8") as handle:
        n = int(handle.readline())
    if B is not None and len(B) == 1:
        B = B * n
    start = perf_counter()
    prob, w = build_problem(dataset, p, r, B, alpha, lamb, delta)
    build_seconds = perf_counter() - start
    start = perf_counter()
    prob.solve(pulp.COIN_CMD(msg=False, logPath=log_path))
    return prob, w, build_seconds, perf_counter() - start


def main(
    dataset: str,
    results: str,
    p: int,
    r: int,
    B: list[float],
    alpha: float,
    lamb: float,
    delta: float,
):
    prob, w, _, solve_seconds = solve_problem(
        dataset, p, r, B, alpha, lamb, delta
    )
    Path(results).parent.mkdir(parents=True, exist_ok=True)
    print("Status:", pulp.LpStatus[prob.status])
    print("Objective:", pulp.value(prob.objective))

    # Extracting the variables and hubs from the solution.
    z = variable(prob, "z")
    x = variable(prob, "x")

    hubs = identify_hubs(z)
    flow = hubs_flow(z, x, w)
    print("Hubs:", hubs)
    for h in hubs:
        print(f"  fluxo no hub {h}: {flow[h]:.4f}")

    # Printing the solution variables.
    n = max(i for i, _ in z) + 1

    print("\nAllocation matrix z (line i -> column hub k):")
    print("     " + " ".join(f"{k:>3}" for k in range(n)))
    for i in range(n):
        print(f"{i:>3}: " + " ".join(f"{round(z.get((i, k), 0)):>3}" for k in range(n)))

    print("\nFraction flow x[i,j,k,l] > 0 (path i -> k -> l -> j):")
    for (i, j, k, l), val in sorted(x.items()):
        if val > 1e-6:
            print(f"  x[{i},{j},{k},{l}] = {val:.4f}   ({i} -> {k} -> {l} -> {j})")

    # Saving the results to a CSV file.
    save_csv(prob, solve_seconds, p, r, B, alpha, lamb, delta, hubs, flow, results)

    # Generating dot.
    generate_dot(z, x, w, str(Path(results).with_suffix(".dot")))


SUMMARY_FIELDS = [
    "schema_version", "instance", "n", "p", "r", "alpha", "lamb", "delta",
    "effective_capacity", "status", "solution_status", "has_solution",
    "objective", "build_seconds", "solve_seconds", "total_seconds",
    "solver_log_path", "error",
]


def _read_metadata(path: Path, capacity: float | None) -> tuple[int, list[float] | None]:
    """Read dimensions and capacities, preferring the input capacity row."""
    with path.open(encoding="utf-8") as handle:
        n = int(handle.readline())
        data = np.loadtxt(handle, ndmin=2)
    if len(data) > 2*n:
        capacities = data[2*n].tolist()
    else:
        capacities = [capacity] * n if capacity is not None else None
    return n, capacities


def _save_result(path: Path, result: dict) -> None:
    temporary = path.with_suffix(".json.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def run_experiment(argv=None) -> int:
    """Run a single case and persist JSON, summary CSV, CBC log and DOT.

    Return 1 on execution errors; infeasibility is a recorded solver outcome.
    Node indices in JSON and DOT are zero-based.
    """
    parser = argparse.ArgumentParser(description="Solve one experiment and save CSV, JSON, CBC log and DOT.")
    parser.add_argument("instance", type=Path)
    parser.add_argument("--p", type=int, required=True)
    parser.add_argument("--r", type=int, required=True)
    parser.add_argument("--alpha", type=float, required=True)
    parser.add_argument("--capacity", type=float)
    parser.add_argument("--session", type=Path, required=True)
    args = parser.parse_args(argv)
    instance = args.instance.expanduser().resolve()
    n, capacities = _read_metadata(instance, args.capacity)

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
            log_path=str(log_path),
        )
        result.update(build_seconds=build_seconds, solve_seconds=solve_seconds,
                      status=pulp.LpStatus[prob.status],
                      solver_status=pulp.LpStatus.get(prob.status, str(prob.status)))
        result.update(
            has_solution=prob.status == pulp.LpStatusOptimal,
            solution_status=pulp.LpSolution[prob.sol_status],
        )
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
    if len(sys.argv) > 1 and sys.argv[1] == "--experiment":
        raise SystemExit(run_experiment(sys.argv[2:]))
    main(*read_args())
