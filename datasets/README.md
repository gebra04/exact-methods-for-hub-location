# Input format

These files were copied without alteration from `../Trabalho 2/` (relative to
the project root); `dummy/` was extracted from `dummy_instances.zip`.

Whitespace-separated numeric format:

1. Positive integer n.
2. n rows of n directed flow values w[i,j].
3. n rows of n nonnegative distance/cost values d[i,j].
4. Optional n nonnegative capacities B[k].

Blank lines are ignored. `#` starts a comment up to the end of the line. The
reader rejects extra/missing values, nonfinite numbers, negative values and
nonzero distance diagonals. Flow diagonals may be positive. Ordering is preserved;
no symmetry, rounding, demand normalization or unit conversion is imposed.
Capacities are in the same flow units as the first matrix. Costs retain the
second matrix's units; the supplied format note does not specify physical units.

CAB25 has 25 nodes, AP40 40 and AP80 80; none includes capacities. The dummy
instances toy1–toy8 include capacity rows except toy7, whose final row begins
with `#40` and is therefore a comment. Supply capacities explicitly for that file.
The CLI never silently treats commented values as data.
