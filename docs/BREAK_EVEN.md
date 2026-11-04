# Operational viability figure

## What this figure measures

The figure is an **operational viability** study, not an economic breakeven
calculation. It keeps the initial orbit, antenna state, resource margins, task
request, observation window, and delivery deadline fixed. Only the set of
surviving satellites changes.

It reports two different questions:

1. **Peer communication:** do at least two surviving satellites form one
   connected active radio graph? A single satellite is not a communication pair.
2. **Complete task delivery:** does at least one survivor pass the complete
   admission check, including target access, CPU, storage, energy, thermal
   margin, and a predicted ground route before the deadline?

A connected graph does not guarantee delivery. Conversely, one satellite may
complete a single-spacecraft task without providing a peer-connected swarm.

## Curves and guarantees

- **Solid line:** fraction of tested survivor masks that pass. This is the
  random-failure success probability under uniform masks at each survivor count.
- **Dots:** best-case existence. One dot at 1 means that at least one tested
  mask works; it is not a guarantee for every mask.
- **Dashed line (12 nodes):** worst-case guarantee, obtained from every possible
  survivor subset. A value of 1 means every mask at that count works.
- **Shaded band (40 nodes):** 95% Wilson confidence interval for the sampled
  success probability. The 40-node result is not an exhaustive worst-case
  proof.

The resource and route checks are intentionally visible in the task-delivery
panel. Satellite count alone cannot identify whether the limiting condition is
connectivity, observation access, CPU, storage, energy, thermal headroom, or
ground contact.

## Reproduce the figure

Install the normal requirements, then run from the repository root:

```bash
python generate_breakeven_figure.py
```

This writes:

- `docs/figures/breakeven_feasibility.png` — the figure;
- `docs/figures/breakeven_feasibility.json` — the exact values used to draw it.

The 12-node case evaluates all survivor subsets. The default 40-node case
evaluates 100 seeded uniformly sampled masks for each survivor count. Use
`--samples 500` or a larger value when a narrower Monte Carlo interval is
needed:

```bash
python generate_breakeven_figure.py --samples 500
```

The simulator itself is unchanged by this analysis. No task is executed, no
failure is repaired, and no future orbital motion is assumed; each mask is
evaluated against the same frozen time-zero state.
