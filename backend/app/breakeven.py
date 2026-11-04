"""Operational viability curves for fixed-geometry satellite subsets.

This module deliberately does not change the simulator.  It evaluates a frozen
state under survivor masks so peer connectivity and end-to-end task delivery
cannot be confused with a satellite-count claim.
"""
from __future__ import annotations

from copy import copy, deepcopy
from dataclasses import replace
from itertools import combinations
import math
import random
from dataclasses import dataclass

from .engine import Engine
from .models import Config, Task
from .network import build_links
from .orbits import visibility_windows
from .resources import can_host


@dataclass(frozen=True)
class BreakevenConfig:
    seed: int = 7
    exact_nodes: int = 12
    sampled_nodes: int = 40
    samples_per_count: int = 100
    task_window_end_s: float = 62.0
    task_deadline_s: float = 120.0


def _baseline(nodes: int, seed: int, deadline: float) -> tuple[Engine, Task]:
    if nodes % 2:
        raise ValueError("The integrated simulator needs an even node count")
    config = Config(
        swarm_count=2,
        satellites_per_swarm=nodes // 2,
        seed=seed,
        auto_tasks=False,
        random_failures=False,
        random_revival=False,
        space_effects=False,
    )
    engine = Engine(config, seed_tasks=False)
    task = Task(
        task_id="BREAKEVEN-001",
        event_id="BREAKEVEN",
        target={"lat": 18.52, "lon": 73.86},
        created_at=0.0,
        observation_window=[1.0, deadline - 58.0],
        delivery_deadline=deadline,
        priority=3,
        capture_duration_s=5.0,
        processing_cycles=8_000_000,
        raw_data_mb=40.0,
        output_data_mb=10.0,
    )
    task.visibility_windows = visibility_windows(
        engine.state, task.observation_window[0], task.observation_window[1]
    )
    return engine, task


def _evaluate(
    engine: Engine,
    task: Task,
    survivor_ids: tuple[str, ...],
    frozen_links: list,
) -> tuple[bool, bool]:
    """Return (peer_connected, complete_task_chain_feasible) for one mask."""
    state = copy(engine.state)
    state.satellites = {node: copy(sat) for node, sat in engine.state.satellites.items()}
    state.tasks = {}
    state.version += 1
    survivors = set(survivor_ids)
    for satellite in state.satellites.values():
        if satellite.id not in survivors:
            satellite.health = "isolated"
            satellite.faults["offline"] = True
    signature = (state.time_s, state.version, state.config.space_effects)
    filtered_links = [
        replace(
            link,
            available=(
                link.available
                and link.source in survivors
                and (link.target == "GND" or link.target in survivors)
            ),
        )
        for link in frozen_links
    ]
    state._link_cache = (signature, filtered_links)
    links = [link for link in filtered_links if link.target != "GND" and link.available]
    adjacency = {node: set() for node in survivors}
    for link in links:
        if link.source in survivors and link.target in survivors:
            adjacency[link.source].add(link.target)
            adjacency[link.target].add(link.source)
    connected = False
    if len(survivors) >= 2:
        reached = {next(iter(survivors))}
        pending = list(reached)
        while pending:
            pending.extend(adjacency[pending.pop()].difference(reached))
            reached.update(pending)
        connected = len(reached) == len(survivors)

    feasible = False
    state.tasks[task.task_id] = deepcopy(task)
    for node in sorted(survivors):
        candidate = state.satellites[node]
        ok, _, _ = can_host(state, candidate, state.tasks[task.task_id])
        if ok:
            feasible = True
            break
    return connected, feasible


def _wilson(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    if not trials:
        return 0.0, 0.0
    p = successes / trials
    denominator = 1.0 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denominator
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def _curve_from_masks(
    engine: Engine,
    task: Task,
    masks_by_count: dict[int, list[tuple[str, ...]]],
    exact: bool,
    frozen_links: list,
) -> dict:
    nodes = tuple(engine.state.satellites)
    result = []
    for survivor_count in range(len(nodes) + 1):
        masks = masks_by_count.get(survivor_count, [])
        outcomes = [_evaluate(engine, task, mask, frozen_links) for mask in masks]
        peer = [int(item[0]) for item in outcomes]
        delivery = [int(item[1]) for item in outcomes]
        row = {
            "survivor_count": survivor_count,
            "trials": len(outcomes),
            "peer_best_case": max(peer, default=0),
            "peer_probability": sum(peer) / len(peer) if peer else 0.0,
            "peer_worst_case": min(peer, default=0) if exact else None,
            "delivery_best_case": max(delivery, default=0),
            "delivery_probability": sum(delivery) / len(delivery) if delivery else 0.0,
            "delivery_worst_case": min(delivery, default=0) if exact else None,
        }
        row["peer_ci95"] = _wilson(sum(peer), len(peer))
        row["delivery_ci95"] = _wilson(sum(delivery), len(delivery))
        result.append(row)
    return {"nodes": len(nodes), "exact": exact, "counts": result}


def analyze(config: BreakevenConfig = BreakevenConfig()) -> dict:
    """Generate exact 12-node and sampled 40-node operational viability data."""
    exact_engine, exact_task = _baseline(config.exact_nodes, config.seed, config.task_deadline_s)
    exact_nodes = tuple(exact_engine.state.satellites)
    exact_links = build_links(exact_engine.state)
    exact_masks = {
        count: list(combinations(exact_nodes, count))
        for count in range(config.exact_nodes + 1)
    }

    sampled_engine, sampled_task = _baseline(
        config.sampled_nodes, config.seed, config.task_deadline_s
    )
    sampled_nodes = tuple(sampled_engine.state.satellites)
    rng = random.Random(config.seed)
    sampled_links = build_links(sampled_engine.state)
    sampled_masks = {}
    for count in range(config.sampled_nodes + 1):
        if count in (0, config.sampled_nodes):
            sampled_masks[count] = [tuple(sampled_nodes[:count])]
        else:
            sampled_masks[count] = [
                tuple(sorted(rng.sample(sampled_nodes, count)))
                for _ in range(config.samples_per_count)
            ]
    return {
        "definition": {
            "peer_communication": "The induced active radio graph is connected.",
            "complete_task_delivery": (
                "At least one survivor passes the current host, resource, visibility, "
                "thermal, energy, and predicted ground-route checks."
            ),
            "geometry": "Frozen at simulator time zero; no recovery, motion, or rescheduling is simulated.",
            "exact": "All survivor subsets are evaluated for the 12-node case.",
            "sampled": "The 40-node case uses seeded uniform survivor masks per count.",
        },
        "seed": config.seed,
        "task": {
            "observation_window_s": [1.0, config.task_window_end_s],
            "delivery_deadline_s": config.task_deadline_s,
            "output_data_mb": 10.0,
        },
        "cases": {
            str(config.exact_nodes): _curve_from_masks(
                exact_engine, exact_task, exact_masks, exact=True, frozen_links=exact_links
            ),
            str(config.sampled_nodes): _curve_from_masks(
                sampled_engine, sampled_task, sampled_masks, exact=False, frozen_links=sampled_links
            ),
        },
    }


def plot(result: dict, output_path: str) -> None:
    """Render the paper-ready two-panel breakeven figure."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.6), sharey=True, constrained_layout=True)
    colours = {"12": "#1f77b4", "40": "#d95f02"}
    exact_key, sampled_key = tuple(result["cases"])
    sampled_trials = result["cases"][sampled_key]["counts"][1]["trials"]
    labels = {
        exact_key: f"{exact_key} nodes (exact)",
        sampled_key: f"{sampled_key} nodes ({sampled_trials} masks/count)",
    }
    metrics = [
        ("peer", "Peer communication", "Connected active peer graph"),
        ("delivery", "Complete task delivery", "A feasible host + delivery chain"),
    ]
    for axis, (prefix, title, subtitle) in zip(axes, metrics):
        for key in (exact_key, sampled_key):
            rows = result["cases"][key]["counts"]
            x = [row["survivor_count"] for row in rows]
            probability = [row[f"{prefix}_probability"] for row in rows]
            best = [row[f"{prefix}_best_case"] for row in rows]
            axis.plot(x, probability, color=colours[key], linewidth=2.4, label=labels[key])
            axis.scatter(x, best, color=colours[key], s=13, alpha=.75)
            if key == exact_key:
                worst = [row[f"{prefix}_worst_case"] for row in rows]
                axis.step(x, worst, where="mid", color=colours[key], linestyle="--", alpha=.7)
            else:
                lower = [row[f"{prefix}_ci95"][0] for row in rows]
                upper = [row[f"{prefix}_ci95"][1] for row in rows]
                axis.fill_between(x, lower, upper, color=colours[key], alpha=.12)
        axis.set_title(title, loc="left", fontweight="bold")
        axis.text(.01, .93, subtitle, transform=axis.transAxes, fontsize=9, color="#555")
        axis.set_xlabel("Surviving satellites")
        axis.set_xlim(left=0)
        axis.set_ylim(-.03, 1.03)
        axis.grid(alpha=.22)
    axes[0].set_ylabel("Fraction of survivor masks passing")
    axes[0].legend(frameon=False, loc="lower right")
    fig.suptitle(
        "Operational viability threshold under fixed geometry and request",
        fontsize=14,
        fontweight="bold",
    )
    fig.text(
        .5,
        -.01,
        "Solid = random-mask success probability; dots = best-case existence; "
        "12-node dashed = worst-case guarantee; 40-node bands = 95% Wilson intervals",
        ha="center",
        fontsize=9,
    )
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
