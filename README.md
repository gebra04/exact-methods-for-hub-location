# Exact methods for hub location

English | [Português (Brasil)](README.pt-BR.md)

Authors: [@ValimD](https://github.com/ValimD), [@HenriUz](https://github.com/HenriUz), [@gebra04](https://github.com/gebra04)

Implementation of the **Capacitated r-Allocation p-Hub Median Problem (CrApHMP)** for the Métodos Exatos (XMAC02) course. The formulation and experimental objectives follow the [assignment](trabalho2.pdf).

## Problem

Given a set of nodes representing origins, destinations, and candidate hub locations, the problem selects exactly **p hubs** and routes demand through them to minimize total transportation cost. Each node can be allocated to at most **r hubs**, and the total flow handled by each hub must respect its capacity.

| Parameter     | Meaning                                                             |
| ------------- | ------------------------------------------------------------------- |
| n             | Number of nodes                                                     |
| w[i,j]        | Flow demand from node `i` to node `j`                               |
| d[i,j]        | Distance or unit transportation cost from `i` to `j`                |
| p             | Number of hubs to open                                              |
| r             | Maximum number of hub allocations per node, with `1 <= r <= p <= n` |
| B[k]          | Capacity of candidate hub `k`                                       |
| alpha         | Inter-hub transportation discount, with `0 < alpha <= 1`            |
| lambda, delta | Collection and distribution cost coefficients                       |

A route follows `i -> k -> l -> j`, where `k` and `l` are hubs. Its unit transportation cost is:

$$
C_{ijkl} = \lambda d_{ik} + \alpha d_{kl} + \delta d_{lj}.
$$

When `k = l`, the route uses a single hub. Setting `r = 1` gives single allocation; setting `r = p` allows multiple allocation to any selected hub. Intermediate values restrict the number of connections while allowing more routing flexibility.

### Datasets

The input files available in this repository are:

| Dataset | Files                                        | Description                                                                                                       |
| ------- | -------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| CAB     | `datasets/CAB25.txt`                         | Passenger flows and distances between 25 US cities; attributed in the assignment to O'Kelly (1987)                |
| AP      | `datasets/AP40.txt`, `datasets/AP80.txt`     | Instances with 40 and 80 nodes derived from Australian postal data; attributed to Ernst and Krishnamoorthy (1996) |
| Dummy   | `datasets/dummy/toy1.txt` through `toy8.txt` | Small instances for checking the model and inspecting solution structures                                         |

Each text file contains, in order:

1. The number of nodes `n` on the first line.
2. The `n x n` demand matrix `w`.
3. The `n x n` distance matrix `d`.
4. An optional row with `n` hub capacities.

Values are separated by whitespace. Lines beginning with `#` are comments.

AP demands may be asymmetric (`w[i,j] != w[j,i]`) and may have positive diagonal entries (`w[i,i] > 0`). The implementation preserves these values.

CAB and AP files do not include capacities. Supply a single value with `--capacity`; it is expanded to a vector of length `n`, assigning the same capacity to every candidate hub. **If the file includes a capacity row, that row takes precedence over `--capacity`.**

## Method

The project implements the assignment's mixed-integer linear programming (MILP) formulation in **PuLP** and solves it with **CBC**.

The decision variables are:

- `z[i,k]`: binary variable indicating whether node `i` is allocated to hub `k`. A diagonal value `z[k,k] = 1` means that hub `k` is open.
- `x[i,j,k,l]`: continuous variable in `[0,1]` representing the fraction of demand from `i` to `j` routed through hubs `k` and `l`.

The objective minimizes total demand-weighted transportation cost:

$$
\min \sum_{i,j,k,l \in N} w_{ij} C_{ijkl} x_{ijkl}.
$$

The constraints enforce exactly `p` open hubs, allocation only to open hubs, at most `r` allocations per node, complete routing of each origin-destination flow, and consistency between routes and allocations. Hub capacities account for flow handled as either the first or second hub; a route with `k = l` consumes that hub's capacity only once.

The implementation creates `n²` binary allocation variables and `n⁴` continuous routing variables. Consequently, model construction and memory consumption can become substantial for larger instances.

The experimental interface uses `lambda = delta = 1`. Statuses are displayed directly from `pulp.LpStatus[prob.status]`.

## Architecture

The project separates model construction, solving, experiment orchestration, and visualization.

| File               | Responsibility                                                     |
| ------------------ | ------------------------------------------------------------------ |
| `src/build.py`     | Read the instance and construct the MILP                           |
| `src/main.py`      | Build and solve a case; extract allocations and routes; export DOT |
| `experiments.sh`   | Iterate over datasets and parameter combinations sequentially      |
| `src/visualize.py` | Build an HTML report from experiment JSON files                    |

For each parameter combination, `experiments.sh` launches `src/main.py --experiment`. The case execution and output persistence are implemented in `main.py` itself. Its `solve_problem` function constructs the model through `src/build.py` and invokes CBC using `COIN_CMD`. The CBC executable must be installed on the system and available as `cbc` on PATH. After the experiments, `src/visualize.py` reads the saved JSON files to generate the HTML report.

## Installation

Use **Python 3.12 or newer** and **Bash 4 or newer**. Run the following commands from the repository root. The shell examples target Linux or a compatible environment such as WSL.

**Recommended: uv**

With `uv` installed, synchronize the environment using the committed lockfile:

```bash
uv sync --locked
```

This creates `.venv` and installs the project's dependencies. Python commands can then be executed with `uv run`.

**Alternative: pip**

Create and activate a virtual environment, then install the dependency ranges declared in `pyproject.toml`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install 'numpy>=2.5.4' 'pulp[cbc]>=3.3,<4'
```

The pip alternative follows the declared ranges but does not reproduce the exact versions in `uv.lock`. Keep the PuLP upper bound: the current code uses the PuLP 3.x solver API.

## Usage

Run commands from the repository root. `experiments.sh` selects the project's `.venv/bin/python` automatically, falling back to `python3`. You can override the interpreter with the `PYTHON` environment variable.

**Run a small parameter sweep**

```bash
bash experiments.sh datasets/dummy/toy1.txt \
  --p 1 2 \
  --alpha 0.25 0.5 1.0
```

Without `--r`, the script tries every integer from `1` through the current `p`. To select particular allocation limits, pass a list such as `--r 1 2`.

| Option               | Meaning                                   | Default                           |
| -------------------- | ----------------------------------------- | --------------------------------- |
| `--p INTEGER...`     | Hub counts                                | `1 2`                             |
| `--r INTEGER...`     | Allocation limits                         | All integers from `1` to each `p` |
| `--alpha NUMBER...`  | Inter-hub discount factors                | `0.25 0.5 1.0`                    |
| `--capacity NUMBER`  | Uniform capacity if absent from the input | Use the file's capacity row       |
| `--output DIRECTORY` | Parent directory for experiment sessions  | `results`                         |

Place dataset paths before the options. The script starts a separate Python process for each dataset and valid `(p, r, alpha)` combination, waiting for it to finish before starting the next. Combinations with `p > n` or `r > p` are skipped.

**Run CAB and AP with uniform capacities**

For example, the following commands assign capacity `1000000` to each candidate hub. This is an illustrative value, not a calibrated experimental setting; choose capacities according to each dataset's demand scale and the desired capacity tightness.

```bash
bash experiments.sh datasets/CAB25.txt \
  --p 2 --r 1 2 --alpha 0.5 \
  --capacity 1000000

bash experiments.sh datasets/AP40.txt datasets/AP80.txt \
  --p 2 --r 1 2 --alpha 0.5 \
  --capacity 1000000
```

To study capacity tightness, invoke the script again with different `--capacity` values. For files containing a capacity row, modify that row or use a separate copy of the instance, since the command-line fallback does not override it.

**Output files**

Each dataset receives a session directory named after the dataset and supplied parameters. For the small sweep above:

```text
results/toy1_p-1-2_r-auto_alpha-0.25-0.5-1.0_capacity-file/
```

Repeated sessions receive suffixes such as `__run2`, preserving previous outputs. Each session contains:

- `summary.csv`: one row per case, with parameters, effective capacities, status, objective, and execution times.
- One `.json` per case: metadata, hubs, allocations, routing fractions, and hub loads.
- One `.cbc.log` per solver execution: CBC's log.
- One `.cbc.dot` per run: allocations and aggregated flows between hubs.

DOT represents the network graph, while JSON retains the detailed routing fractions used by the interactive report. Values and graphs are exported regardless of status; consult the status when interpreting each run.

**Generate the HTML report**

With uv:

```bash
uv run python src/visualize.py results --output results/report.html
```

With the pip environment activated:

```bash
python src/visualize.py results --output results/report.html
```

Open `results/report.html` in a browser. The report includes a table of all loaded cases and interactive solution graphs for instances stored in a `dummy` directory. These graphs let you inspect allocations and routes for a selected origin-destination pair. You can also pass a single JSON file or a specific session directory instead of `results`.

**Run one case directly**

To generate the same experiment outputs without a parameter sweep:

```bash
uv run python src/main.py --experiment datasets/dummy/toy1.txt \
  --p 2 --r 1 --alpha 0.5 --session results/single-case
```

With pip, replace `uv run python` with `python` after activating `.venv`.

## Results
