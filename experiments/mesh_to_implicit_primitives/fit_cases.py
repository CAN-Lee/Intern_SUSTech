"""Greedy CPU fit of a small implicit CSG program to one watertight OBJ."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
import trimesh
import sdfcad as sdf


KINDS = ("box", "cylinder", "sphere")
TAU = 0.18


def field(kind: str, x: np.ndarray, points: np.ndarray) -> np.ndarray:
    center = x[:3]
    local = points - center
    if kind == "sphere":
        return np.linalg.norm(local, axis=1) - x[3]
    if kind == "box":
        rotated = local @ Rotation.from_rotvec(x[6:9]).as_matrix()
        q = np.abs(rotated) - x[3:6]
        return np.linalg.norm(np.maximum(q, 0), axis=1) + np.minimum(np.max(q, axis=1), 0)
    axis = x[5:8] / max(np.linalg.norm(x[5:8]), 1e-8)
    axial = local @ axis
    radial = np.sqrt(np.maximum(np.sum(local * local, axis=1) - axial * axial, 0))
    q = np.stack((radial - x[3], np.abs(axial) - x[4]), axis=1)
    return np.linalg.norm(np.maximum(q, 0), axis=1) + np.minimum(np.max(q, axis=1), 0)


def program_field(program: list[dict], points: np.ndarray) -> np.ndarray:
    value = field(program[0]["kind"], np.asarray(program[0]["params"]), points)
    for node in program[1:]:
        other = field(node["kind"], np.asarray(node["params"]), points)
        value = np.minimum(value, other) if node["op"] == "union" else np.maximum(value, -other)
    return value


def bounds(kind: str) -> tuple[np.ndarray, np.ndarray]:
    center_lo = np.full(3, -1.5)
    center_hi = np.full(3, 1.5)
    if kind == "sphere":
        return np.r_[center_lo, 0.025], np.r_[center_hi, 2.5]
    if kind == "box":
        return np.r_[center_lo, np.full(3, 0.025), np.full(3, -np.pi)], np.r_[center_hi, np.full(3, 2.5), np.full(3, np.pi)]
    return np.r_[center_lo, 0.025, 0.025, np.full(3, -1.0)], np.r_[center_hi, 2.5, 2.5, np.full(3, 1.0)]


def seed_params(kind: str, center: np.ndarray, dims: np.ndarray, axis: np.ndarray | None = None) -> np.ndarray:
    if kind == "sphere":
        return np.r_[center, max(0.05, np.median(dims) * 0.42)]
    if kind == "box":
        return np.r_[center, np.maximum(dims * 0.42, 0.05), np.zeros(3)]
    if axis is None:
        axis = np.array([0.0, 0.0, 1.0])
    direction = int(np.argmax(np.abs(axis)))
    cross = [i for i in range(3) if i != direction]
    radius = max(0.05, min(dims[cross]) * 0.48)
    half_height = max(0.05, dims[direction] * 0.48)
    return np.r_[center, radius, half_height, axis]


def target_samples(mesh: trimesh.Trimesh, rng: np.random.Generator, count: int) -> tuple[np.ndarray, np.ndarray]:
    surface = mesh.sample(count, seed=int(rng.integers(2**31)))
    extent = mesh.extents
    uniform = rng.uniform(mesh.bounds[0] - extent * 0.15, mesh.bounds[1] + extent * 0.15, size=(count, 3))
    jitter = surface + rng.normal(0, 0.05, size=surface.shape)
    points = np.vstack((surface, jitter, uniform))
    # trimesh uses positive-inside, while sdfCAD and this fitter use negative-inside.
    signed = -trimesh.proximity.signed_distance(mesh, points)
    if not np.all(np.isfinite(signed)):
        raise ValueError("Non-finite signed distances in input mesh")
    return points, np.clip(signed, -TAU, TAU)


def mse(program: list[dict], points: np.ndarray, target: np.ndarray) -> float:
    delta = np.clip(program_field(program, points), -TAU, TAU) - target
    return float(np.mean(delta * delta))


def fit_node(kind: str, op: str, prior: list[dict], starts: list[np.ndarray], points: np.ndarray, target: np.ndarray, max_nfev: int) -> dict:
    lo, hi = bounds(kind)
    prior_value = program_field(prior, points) if prior else None

    def residual(x: np.ndarray) -> np.ndarray:
        value = field(kind, x, points)
        if prior_value is not None:
            value = np.minimum(prior_value, value) if op == "union" else np.maximum(prior_value, -value)
        return np.clip(value, -TAU, TAU) - target

    best = None
    for start in starts:
        result = least_squares(residual, np.clip(start, lo + 1e-5, hi - 1e-5), bounds=(lo, hi), max_nfev=max_nfev, ftol=2e-3, xtol=2e-3)
        score = float(np.mean(result.fun**2))
        if best is None or score < best["train_mse"]:
            best = {"kind": kind, "op": op, "params": result.x.tolist(), "train_mse": score, "nfev": result.nfev}
    assert best is not None
    return best


def initial_starts(kind: str, mesh: trimesh.Trimesh) -> list[np.ndarray]:
    center = mesh.bounds.mean(axis=0)
    dims = mesh.extents
    starts = [seed_params(kind, center, dims)]
    if kind == "box":
        cloud = mesh.vertices - mesh.vertices.mean(axis=0)
        _, _, vh = np.linalg.svd(cloud, full_matrices=False)
        matrix = vh.T
        if np.linalg.det(matrix) < 0:
            matrix[:, 2] *= -1
        local = cloud @ matrix
        half = np.maximum((local.max(axis=0) - local.min(axis=0)) / 2, 0.025)
        starts.append(np.r_[mesh.vertices.mean(axis=0), half, Rotation.from_matrix(matrix).as_rotvec()])
    if kind == "cylinder":
        starts = [seed_params(kind, center, dims, np.eye(3)[i]) for i in range(3)]
    return starts


def addition_starts(kind: str, op: str, prior: list[dict], points: np.ndarray, target: np.ndarray, dims: np.ndarray) -> list[np.ndarray]:
    pred = program_field(prior, points)
    mask = (target < -0.02) & (pred > 0.02) if op == "union" else (target > 0.02) & (pred < -0.02)
    region = points[mask]
    if len(region) < 10:
        region = points[np.argsort(np.abs(target - np.clip(pred, -TAU, TAU)))[-100:]]
    centers = [np.median(region, axis=0), region.mean(axis=0)]
    size = np.maximum(np.minimum(np.ptp(region, axis=0), dims), 0.08)
    starts = []
    for center in centers:
        if kind == "cylinder":
            starts.extend(seed_params(kind, center, size, np.eye(3)[i]) for i in range(3))
        else:
            starts.append(seed_params(kind, center, size))
    return starts


def refine(program: list[dict], points: np.ndarray, target: np.ndarray) -> list[dict]:
    lengths = [len(node["params"]) for node in program]
    offsets = np.cumsum([0, *lengths])
    x0 = np.concatenate([node["params"] for node in program])
    lo = np.concatenate([bounds(node["kind"])[0] for node in program])
    hi = np.concatenate([bounds(node["kind"])[1] for node in program])

    def residual(x: np.ndarray) -> np.ndarray:
        local = [{**node, "params": x[offsets[i]:offsets[i+1]]} for i, node in enumerate(program)]
        return np.clip(program_field(local, points), -TAU, TAU) - target

    result = least_squares(residual, x0, bounds=(lo, hi), max_nfev=28, ftol=2e-3, xtol=2e-3)
    return [{**node, "params": result.x[offsets[i]:offsets[i+1]].tolist()} for i, node in enumerate(program)]


def to_sdf(program: list[dict]):
    objects = []
    for node in program:
        kind, x = node["kind"], np.asarray(node["params"])
        if kind == "sphere":
            obj = sdf.sphere(radius=float(x[3]), center=x[:3])
        elif kind == "box":
            angle = np.linalg.norm(x[6:9])
            obj = sdf.box(size=2 * x[3:6])
            if angle > 1e-8:
                obj = obj.rotate(angle, x[6:9] / angle)
            obj = obj.translate(x[:3])
        else:
            axis = x[5:8] / max(np.linalg.norm(x[5:8]), 1e-8)
            obj = sdf.capped_cylinder(x[:3] - axis * x[4], x[:3] + axis * x[4], radius=float(x[3]))
        objects.append(obj)
    assembled = objects[0]
    for node, obj in zip(program[1:], objects[1:]):
        assembled = assembled | obj if node["op"] == "union" else assembled - obj
    return assembled


def evaluation_grid(mesh: trimesh.Trimesh, grid: int = 48) -> tuple[np.ndarray, np.ndarray]:
    low, high = mesh.bounds[0] - 0.12, mesh.bounds[1] + 0.12
    axes = [np.linspace(low[i], high[i], grid) for i in range(3)]
    xyz = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3)
    actual = mesh.contains(xyz)
    return xyz, actual


def evaluate(program: list[dict], xyz: np.ndarray, actual: np.ndarray) -> dict:
    predicted = program_field(program, xyz) <= 0
    intersection = np.count_nonzero(predicted & actual)
    union = np.count_nonzero(predicted | actual)
    return {"voxel_iou_48": float(intersection / union) if union else None, "target_occupied": int(actual.sum()), "predicted_occupied": int(predicted.sum())}


def surface_distance(mesh: trimesh.Trimesh, reconstruction: trimesh.Trimesh, seed: int, count: int = 1500) -> dict:
    rng = np.random.default_rng(seed)
    source = mesh.sample(count, seed=int(rng.integers(2**31)))
    fitted = reconstruction.sample(count, seed=int(rng.integers(2**31)))
    a = trimesh.proximity.closest_point(reconstruction, source)[1]
    b = trimesh.proximity.closest_point(mesh, fitted)[1]
    both = np.r_[a, b]
    return {"surface_distance_mean": float(np.mean(both)), "surface_distance_p95": float(np.percentile(both, 95))}


def meshing_bounds(implicit, mesh: trimesh.Trimesh) -> tuple[np.ndarray, np.ndarray]:
    margin = 0.2
    for _ in range(6):
        low, high = mesh.bounds[0] - margin, mesh.bounds[1] + margin
        samples = []
        for axis in range(3):
            other = [i for i in range(3) if i != axis]
            uv = np.stack(np.meshgrid(*[np.linspace(low[i], high[i], 15) for i in other], indexing="ij"), axis=-1).reshape(-1, 2)
            for edge in (low[axis], high[axis]):
                points = np.zeros((len(uv), 3))
                points[:, axis] = edge
                points[:, other] = uv
                samples.append(points)
        if np.min(implicit(np.vstack(samples))) > 0.02:
            return low, high
        margin *= 2
    raise ValueError("Could not enclose the fitted implicit solid for meshing")


def preview(mesh: trimesh.Trimesh, reconstruction: trimesh.Trimesh, path: Path) -> None:
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    fig = plt.figure(figsize=(10, 5))
    for i, (shape, title) in enumerate(((mesh, "Input"), (reconstruction, "Fitted implicit CSG"))):
        ax = fig.add_subplot(1, 2, i + 1, projection="3d")
        collection = Poly3DCollection(shape.vertices[shape.faces], linewidth=0)
        collection.set_facecolor("#79a9c9")
        ax.add_collection3d(collection)
        ax.set_xlim(-1.25, 1.25); ax.set_ylim(-1.25, 1.25); ax.set_zlim(-1.25, 1.25)
        ax.view_init(elev=28, azim=35)
        ax.set_title(title)
        ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def run(case: Path, output: Path, max_primitives: int, seed: int, time_limit: int) -> None:
    start = time.monotonic()
    output.mkdir(parents=True, exist_ok=True)
    mesh = trimesh.load(case, force="mesh", process=False)
    if not mesh.is_watertight or not mesh.is_winding_consistent:
        raise ValueError("Input mesh must be watertight with consistent winding")
    rng = np.random.default_rng(seed)
    train_points, train_target = target_samples(mesh, rng, 1100)
    valid_points, valid_target = target_samples(mesh, rng, 700)
    trace = []
    candidates = []
    for kind in KINDS:
        candidate = fit_node(kind, "root", [], initial_starts(kind, mesh), train_points, train_target, 45)
        candidate["validation_mse"] = mse([candidate], valid_points, valid_target)
        candidates.append(candidate)
    best = min(candidates, key=lambda node: node["validation_mse"])
    program = [best]
    trace.append({"stage": 1, "candidates": [{"kind": c["kind"], "validation_mse": c["validation_mse"]} for c in candidates], "selected": best["kind"]})
    print(f"stage 1: {best['kind']} validation MSE {best['validation_mse']:.6f}", flush=True)

    for stage in range(2, max_primitives + 1):
        if time.monotonic() - start > time_limit - 90:
            trace.append({"stage": stage, "status": "time_budget_reached"})
            break
        choices = []
        for op in ("union", "difference"):
            for kind in KINDS:
                starts = addition_starts(kind, op, program, train_points, train_target, mesh.extents)
                node = fit_node(kind, op, program, starts, train_points, train_target, 35)
                candidate = program + [node]
                node["validation_mse"] = mse(candidate, valid_points, valid_target)
                choices.append((node["validation_mse"], node))
        score, node = min(choices, key=lambda pair: pair[0])
        prior_score = mse(program, valid_points, valid_target)
        record = {"stage": stage, "best_kind": node["kind"], "best_op": node["op"], "prior_validation_mse": prior_score, "new_validation_mse": score}
        if score >= prior_score * 0.97:
            record["status"] = "stopped_no_meaningful_improvement"
            trace.append(record)
            break
        proposed = refine(program + [node], train_points, train_target)
        refined_score = mse(proposed, valid_points, valid_target)
        if refined_score <= score:
            program = proposed
            record["new_validation_mse"] = refined_score
        else:
            program.append(node)
        record["status"] = "accepted"
        trace.append(record)
        print(f"stage {stage}: {node['op']} {node['kind']} validation MSE {record['new_validation_mse']:.6f}", flush=True)

    baseline = [{"kind": "box", "op": "root", "params": np.r_[mesh.bounds.mean(axis=0), mesh.extents / 2, np.zeros(3)].tolist()}]
    optimization_seconds = time.monotonic() - start
    xyz, actual = evaluation_grid(mesh)
    metrics = {"case": str(case), "sha256": hashlib.sha256(case.read_bytes()).hexdigest(), "seed": seed,
               "optimization_seconds": optimization_seconds, "primitive_count": len(program),
               "validation_mse": mse(program, valid_points, valid_target),
               "bbox_baseline": evaluate(baseline, xyz, actual), "fit": evaluate(program, xyz, actual)}
    implicit = to_sdf(program)
    probe = rng.uniform(mesh.bounds[0], mesh.bounds[1], size=(128, 3))
    max_delta = np.max(np.abs(implicit(probe).ravel() - program_field(program, probe)))
    if max_delta > 1e-5:
        raise ValueError(f"sdfCAD and optimizer fields disagree by {max_delta:g}")
    bounds_ = meshing_bounds(implicit, mesh)
    implicit.save(str(output / "reconstruction.stl"), bounds=bounds_, step=float(max(mesh.extents) / 90), workers=1, verbose=False, sparse=False)
    reconstructed = trimesh.load(output / "reconstruction.stl", force="mesh", process=True)
    metrics["reconstructed_watertight"] = bool(reconstructed.is_watertight)
    if not reconstructed.is_watertight:
        raise ValueError("Exported reconstruction is not watertight")
    metrics.update(surface_distance(mesh, reconstructed, seed))
    preview(mesh, reconstructed, output / "comparison.png")
    metrics["total_seconds"] = time.monotonic() - start
    (output / "program.json").write_text(json.dumps({"case": str(case), "program": program, "convention": "negative inside; operations applied in list order"}, indent=2))
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2))
    (output / "trace.json").write_text(json.dumps(trace, indent=2))
    print(json.dumps(metrics, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-primitives", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--time-limit", type=int, default=600)
    args = parser.parse_args()
    run(args.case, args.output, args.max_primitives, args.seed, args.time_limit)
