import argparse
import csv
import os
import re
import shutil
import subprocess
from time import perf_counter

import pulp

from build import build_problem


def read_args():
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


def save_csv(prob, dataset, time, p, r, B, alpha, lamb, delta, path):
    columns = ["dataset", "objective", "time", "p", "r", "B", "alpha", "lamb", "delta"]
    new = not os.path.exists(path)

    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(columns)

        w.writerow(
            [
                dataset,
                pulp.value(prob.objective),
                round(time, 4),
                p,
                r,
                " ".join(map(str, B)),
                alpha,
                lamb,
                delta,
            ]
        )


def variable(prob, prefix):
    values = {}
    for v in prob.variables():
        if v.name.startswith(prefix + "_"):
            idx = tuple(int(s) for s in re.findall(r"\d+", v.name[len(prefix) + 1 :]))
            values[idx] = v.varValue if v.varValue is not None else 0.0
    return values


def generate_dot(z, x, dot_path="results/graph.dot", eps=1e-6):
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

    # Allocation edges i -> k (dashed).
    for (i, k), val in sorted(z.items()):
        if val > 0.5 and i != k:
            lines.append(f"  {i} -> {k} [style=dashed, color=gray];")

    # Routing edges between hubs k -> l.
    labels = {}

    for (i, j, k, l), val in x.items():
        if val > eps and k != l:
            labels.setdefault((k, l), []).append(f"{i}-{j}:{val:.2f}")

    for (k, l), lis in sorted(labels.items()):
        rotulo = "\\n".join(sorted(lis))
        lines.append(f'  {k} -> {l} [color=red, penwidth=2, label="{rotulo}"];')

    lines.append("}")

    with open(dot_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


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
    prob = build_problem(dataset, p, r, B, alpha, lamb, delta)

    start = perf_counter()
    prob.solve(pulp.COIN_CMD(msg=False))
    end = perf_counter()

    print("Status:", pulp.LpStatus[prob.status])
    print("Objective:", pulp.value(prob.objective))

    # Saving results in the CSV file.
    dirs = dataset.split("/")
    name = dirs[len(dirs) - 1][:-4]

    save_csv(prob, name, end - start, p, r, B, alpha, lamb, delta, results)

    # Printing variables.
    z = variable(prob, "z")
    x = variable(prob, "x")

    n = max(i for i, _ in z) + 1

    print("\nAllocation matrix z (line i -> column hub k):")
    print("     " + " ".join(f"{k:>3}" for k in range(n)))
    for i in range(n):
        print(f"{i:>3}: " + " ".join(f"{round(z.get((i, k), 0)):>3}" for k in range(n)))

    print("\nFraction flow x[i,j,k,l] > 0 (path i -> k -> l -> j):")
    for (i, j, k, l), val in sorted(x.items()):
        if val > 1e-6:
            print(f"  x[{i},{j},{k},{l}] = {val:.4f}   ({i} -> {k} -> {l} -> {j})")

    # Generating dot.
    generate_dot(z, x)


if __name__ == "__main__":
    dataset, results, p, r, B, alpha, lamb, delta = read_args()
    main(dataset, results, p, r, B, alpha, lamb, delta)
