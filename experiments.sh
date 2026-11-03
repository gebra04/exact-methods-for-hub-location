#!/usr/bin/env bash
# Shell owns the parameter sweep; Python builds and solves one MILP per process.
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
usage() {
    cat <<'HELP'
Usage: bash experiments.sh INSTANCE... [options]
  --p INTEGER...       Hub counts (default: 1 2)
  --r INTEGER...       Allocation limits (default: 1 through p)
  --alpha NUMBER...    Discounts (default: 0.25 0.5 1.0)
  --capacity NUMBER    Uniform capacity when absent from the instance
  --time-limit NUMBER  CBC time limit in seconds (default: 60)
  --output DIRECTORY   Session parent directory (default: results)
  -h, --help           Show this help
Paths are relative to the caller's directory. PYTHON selects the interpreter;
otherwise the project .venv is preferred, falling back to python3.
HELP
}
fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }
instances=() p_values=(1 2) r_values=() alpha_values=(0.25 0.5 1.0)
capacity=() time_limit=60 output=results
while (($#)); do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --p|--r|--alpha)
            option="$1"; shift; values=()
            while (($#)) && [[ "$1" != --* ]]; do values+=("$1"); shift; done
            ((${#values[@]})) || fail "$option requires values"
            case "$option" in
                --p) p_values=("${values[@]}") ;;
                --r) r_values=("${values[@]}") ;;
                --alpha) alpha_values=("${values[@]}") ;;
            esac ;;
        --capacity|--time-limit|--output)
            option="$1"
            (($# >= 2)) && [[ "$2" != --* ]] || fail "$option requires a value"
            case "$option" in
                --capacity) capacity=(--capacity "$2") ;;
                --time-limit) time_limit="$2" ;;
                --output) output="$2" ;;
            esac
            shift 2 ;;
        --*) fail "Unknown option: $1" ;;
        *) instances+=("$1"); shift ;;
    esac
done
((${#instances[@]})) || { usage >&2; exit 1; }
for value in "${p_values[@]}" "${r_values[@]}"; do
    [[ "$value" =~ ^[1-9][0-9]*$ && ${#value} -le 8 ]] || fail "p and r must be positive integers (at most 8 digits)"
done
check_number() {
    local value="$1" upper="$2"
    [[ "$value" =~ ^[+]?[0-9]*\.?[0-9]+([eE][+-]?[0-9]+)?$ ]] || fail "Invalid number: $value"
    LC_ALL=C awk -v v="$value" -v upper="$upper" 'BEGIN {exit !(v+0>0 && v+0<1e308 && (!upper || v+0<=upper))}' || fail "Number out of range: $value"
}
for value in "${alpha_values[@]}"; do check_number "$value" 1; done
check_number "$time_limit" 0
if ((${#capacity[@]})); then check_number "${capacity[1]}" 0; fi
for instance in "${instances[@]}"; do
    [[ -f "$instance" && -r "$instance" ]] || fail "Cannot read instance: $instance"
done
if [[ -n "${PYTHON:-}" ]]; then python_bin="$PYTHON"
elif [[ -x "$project_dir/.venv/bin/python" ]]; then python_bin="$project_dir/.venv/bin/python"
else python_bin=python3
fi
command -v "$python_bin" >/dev/null || fail "Python interpreter not found: $python_bin"
mkdir -p -- "$output"
join_values() { local IFS=-; printf '%s' "$*"; }
p_tag="$(join_values "${p_values[@]}")"
r_tag="$(join_values "${r_values[@]}")"
r_tag="${r_tag:-auto}"
alpha_tag="$(join_values "${alpha_values[@]}")"
capacity_tag="${capacity[1]:-file}"
# mkdir reserves names atomically; repeated runs never overwrite prior results.
create_session() {
    local base="$1" candidate="$1" suffix=2
    while ! mkdir -- "$candidate" 2>/dev/null; do
        [[ -e "$candidate" ]] || fail "Cannot create directory: $candidate"
        candidate="${base}__run${suffix}"
        suffix=$((suffix + 1))
    done
    printf '%s' "$candidate"
}
declare -A completed=()
runs=0
for instance in "${instances[@]}"; do
    dataset="$(basename -- "$instance")"
    dataset="${dataset%.*}"
    dataset="$(printf '%s' "$dataset" | LC_ALL=C tr -c '[:alnum:]_.-' '_')"
    session="$(create_session "$output/${dataset}_p-${p_tag}_r-${r_tag}_alpha-${alpha_tag}_capacity-${capacity_tag}_time-${time_limit}")"
    printf 'Session: %s\n' "$session"
    n="$(head -n 1 -- "$instance" | tr -d '[:space:]')"
    [[ "$n" =~ ^[1-9][0-9]*$ && ${#n} -le 8 ]] || fail "Invalid node count in $instance"
    for p in "${p_values[@]}"; do
        if ((p > n)); then printf '[skip] %s p=%s exceeds n=%s\n' "$instance" "$p" "$n"; continue; fi
        current_r=("${r_values[@]}")
        if ((${#current_r[@]} == 0)); then
            for ((r=1; r<=p; r++)); do current_r+=("$r"); done
        fi
        for r in "${current_r[@]}"; do
            if ((r > p)); then printf '[skip] p=%s r=%s\n' "$p" "$r"; continue; fi
            for alpha in "${alpha_values[@]}"; do
                key="$instance|$p|$r|$alpha"
                [[ -z "${completed[$key]:-}" ]] || continue
                completed[$key]=1
                printf '[run] %s p=%s r=%s alpha=%s\n' "$instance" "$p" "$r" "$alpha"
                "$python_bin" "$project_dir/src/main.py" --experiment "$instance" \
                    --p "$p" --r "$r" --alpha "$alpha" "${capacity[@]}" \
                    --time-limit "$time_limit" --session "$session"
                runs=$((runs + 1))
            done
        done
    done
    printf 'Summary: %s/summary.csv\n' "$session"
done
((runs > 0)) || fail 'No valid parameter combinations were selected'
printf 'Completed %s runs. Results: %s\n' "$runs" "$output"
