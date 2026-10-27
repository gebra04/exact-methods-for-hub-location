import sys
from itertools import product

import numpy as np
import pulp


def build_problem(
    instance_path: str,
    p: int,
    r: int,
    B: list[float] | None,
    alpha: float,
    lamb: float = 1.0,
    delta: float = 1.0,
) -> pulp.LpProblem:
    """
    Build a PuLP solver for the Capacitated r-Allocation p-Hub Median Problem using a MILP formulation.

    The parameter `B` will be overridden if the instance contains a capacity vector in the last row. For this reason, it may have the value `None`.

    # Parameters:
    - instance_path (str): Instance path.
    - p (int): number of hubs to locate.
    - r (int): maximum number of hubs each node may be allocated to (`1 <= r <= p`).
    - B (list[float] | None): capacity of hub k (maximum total flow that can enter the hub).
    - alpha (float): inter-hub transfer discount factor (economies of scale).
    - lamb (float): collection cost coefficient.
    - delta (float): distribution cost coefficient.

    # Returns:
    Instance of the modeled problem.
    """

    # Checking parameters.
    if r < 1 or r > p:
        print("Incorrect value of r. It must be 1 <= r <= p.")
        sys.exit(1)

    if alpha <= 0 or alpha > 1:
        print("Incorret value of alpha. It must be in (0, 1] interval.")
        sys.exit(1)

    # Reading instance.
    try:
        with open(instance_path, "r") as file:
            n = int(file.readline())

            data = np.loadtxt(file)

            w = data[:n, :]
            d = data[n : 2 * n, :]

            if data.shape[0] > 2 * n:
                Bk = data[2 * n, :]
            else:
                if B is not None:
                    if len(B) != n:
                        raise ValueError(
                            f"B must contain values for the {n} nodes. It contains {len(B)} values."
                        )

                    Bk = np.array(B, dtype=np.float64)
                else:
                    raise ValueError(
                        "Vector B is not specified in the parameters or in the instance."
                    )
    except OSError as e:
        print(e)
        sys.exit(1)
    except ValueError as e:
        print(e)
        sys.exit(1)

    # Building cost of routing.
    i, j, k, l = np.ogrid[0:n, 0:n, 0:n, 0:n]
    C = lamb * d[i, k] + alpha * d[k, l] + delta * d[l, j]

    # Building problem.
    prob = pulp.LpProblem("Hub_Location", pulp.LpMinimize)

    # Creating variables and adding objective function to problem.
    nodes = range(n)

    pairs = list(product(nodes, repeat=2))
    triples = list(product(nodes, repeat=3))
    quads = list(product(nodes, repeat=4))

    z = prob.add_variable_dicts("z", pairs, cat="Binary")
    x = prob.add_variable_dicts(
        "x",
        quads,
        lowBound=0,
        upBound=1,
        cat="Continuous",
    )

    prob += (
        pulp.lpSum(w[i, j] * C[i, j, k, l] * x[i, j, k, l] for i, j, k, l in quads),
        "Objective_Function",
    )

    # Adding constraints.
    prob += pulp.lpSum(z[k, k] for k in range(n)) == p, "Constraint_4"

    for i, k in pairs:
        if i != k:
            prob += z[i, k] <= z[k, k], f"Constraint_5_{i},{k}"

    for i in nodes:
        prob += pulp.lpSum(z[i, k] for k in nodes) <= r, f"Constraint_6_{i}"

    for i, j in pairs:
        prob += (
            pulp.lpSum(x[i, j, k, l] for k, l in pairs) == 1,
            f"Constraint_7_{i},{j}",
        )

    for i, j, k in triples:
        prob += (
            pulp.lpSum(x[i, j, k, l] for l in nodes) <= z[i, k],
            f"Constraint_8_{i},{j},{k}",
        )

    for i, j, l in triples:
        prob += (
            pulp.lpSum(x[i, j, k, l] for k in nodes) <= z[j, l],
            f"Constraint_9_{i},{j},{l}",
        )

    for k in nodes:
        prob += (
            pulp.lpSum(
                w[i, j]
                * (
                    pulp.lpSum(x[i, j, k, l] for l in nodes)
                    + pulp.lpSum(x[i, j, l, k] for l in nodes if l != k)
                )
                for i, j in pairs
            )
            <= Bk[k] * z[k, k],
            f"Constraint_10_{k}",
        )

    return prob
