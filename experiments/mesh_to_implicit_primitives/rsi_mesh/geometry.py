"""Versioned CSG trees and deterministic, independently callable geometry tools.

All lengths in programs are in normalized input coordinates. Boolean fields are
sign-correct implicit fields, not necessarily exact Euclidean distance fields.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path

import numpy as np
import trimesh
from scipy.optimize import least_squares
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
from skimage.measure import marching_cubes
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SIZES = {"box": 3, "sphere": 1, "cylinder": 2, "cone": 3, "torus": 2, "capsule": 2}


def load_mesh(path):
    mesh = trimesh.load(path, force="mesh", process=True)
    if not len(mesh.faces) or not mesh.is_watertight or not mesh.is_winding_consistent:
        raise ValueError("Input must be a nonempty watertight, consistently wound mesh")
    if not np.isfinite(mesh.vertices).all() or max(mesh.extents) <= 0:
        raise ValueError("Invalid input coordinates")
    return mesh


def normalize(mesh):
    center = mesh.bounds.mean(axis=0)
    scale = float(max(mesh.extents) / 2)
    out = mesh.copy()
    out.vertices = (out.vertices - center) / scale
    return out, {"center": center.tolist(), "scale": scale}


def validate(program, max_leaves=None, max_depth=None):
    max_leaves = int(os.environ.get("RSI_MAX_PRIMITIVES", "24")) if max_leaves is None else max_leaves
    max_depth = int(os.environ.get("RSI_MAX_DEPTH", "12")) if max_depth is None else max_depth
    if program.get("schema_version") != 1 or "root" not in program:
        raise ValueError("Expected schema_version=1 and root")
    leaves = []

    def visit(node, depth):
        if depth > max_depth:
            raise ValueError("CSG exceeds maximum tree depth")
        if "op" in node:
            if node["op"] not in {"union", "difference", "intersection"}:
                raise ValueError("Unknown boolean operator")
            children = node.get("children", [])
            if len(children) != 2:
                raise ValueError("Boolean nodes require exactly two children")
            for child in children:
                visit(child, depth + 1)
        else:
            kind = node.get("kind")
            if kind not in SIZES:
                raise ValueError(f"Unknown primitive: {kind}")
            center = np.asarray(node.get("center", [0, 0, 0]), dtype=float)
            rotation = np.asarray(node.get("rotation", [0, 0, 0]), dtype=float)
            size = np.asarray(node.get("size", []), dtype=float)
            if center.shape != (3,) or rotation.shape != (3,) or size.shape != (SIZES[kind],):
                raise ValueError("Invalid center, rotation or size shape")
            if not np.isfinite(np.r_[center, rotation, size]).all():
                raise ValueError("Nonfinite primitive parameters")
            if np.any(size <= 0) or np.any(size > 4) or np.any(np.abs(center) > 4):
                raise ValueError("Size must be in (0,4], center in [-4,4]")
            if kind == "torus" and size[0] <= size[1]:
                raise ValueError("Torus major radius must exceed minor radius")
            leaves.append(node)
    visit(program["root"], 1)
    if len(leaves) > max_leaves:
        raise ValueError("Too many primitive leaves")
    return leaves


def field(program, points):
    def evaluate(node):
        if "op" in node:
            a, b = map(evaluate, node["children"])
            return {"union": np.minimum, "intersection": np.maximum}.get(
                node["op"], lambda x, y: np.maximum(x, -y))(a, b)
        p = (points - node.get("center", [0, 0, 0])) @ Rotation.from_rotvec(
            node.get("rotation", [0, 0, 0])).as_matrix()
        s, kind = np.asarray(node["size"]), node["kind"]
        if kind == "sphere":
            return np.linalg.norm(p, axis=1) - s[0]
        if kind == "box":
            q = np.abs(p) - s
            return np.linalg.norm(np.maximum(q, 0), axis=1) + np.minimum(q.max(axis=1), 0)
        radial = np.linalg.norm(p[:, :2], axis=1)
        if kind == "cylinder":
            q = np.c_[radial - s[0], np.abs(p[:, 2]) - s[1]]
            return np.linalg.norm(np.maximum(q, 0), axis=1) + np.minimum(q.max(axis=1), 0)
        if kind == "torus":
            return np.linalg.norm(np.c_[radial - s[0], p[:, 2]], axis=1) - s[1]
        if kind == "capsule":
            return np.linalg.norm(np.c_[p[:, :2], p[:, 2] - np.clip(p[:, 2], -s[1], s[1])], axis=1) - s[0]
        # Finite cone/frustum: bottom radius, top radius, half-height.
        r0, r1, h = s
        q = np.c_[radial, p[:, 2]]
        k1, k2 = np.array([r1, h]), np.array([r1-r0, 2*h])
        ca = np.c_[radial - np.minimum(radial, np.where(p[:, 2] < 0, r0, r1)), np.abs(p[:, 2])-h]
        cb = q - k1 + np.clip(((k1-q) @ k2) / (k2 @ k2), 0, 1)[:, None] * k2
        sign = np.where((cb[:, 0] < 0) & (ca[:, 1] < 0), -1, 1)
        return sign * np.sqrt(np.minimum((ca*ca).sum(axis=1), (cb*cb).sum(axis=1)))
    return evaluate(program["root"])


def samples(mesh, count=1200, seed=42):
    rng = np.random.default_rng(seed)
    surface = mesh.sample(count, seed=seed)
    points = np.vstack([surface, surface + rng.normal(0, .025, surface.shape),
                        rng.uniform(mesh.bounds[0]-.15, mesh.bounds[1]+.15, (count, 3))])
    values = np.concatenate([-trimesh.proximity.signed_distance(mesh, p) for p in np.array_split(points, max(1, len(points)//500))])
    return points, np.clip(values, -.18, .18)


def optimize(program, mesh, seed=42, max_nfev=45):
    result = copy.deepcopy(program)
    leaves = validate(result)
    lengths = [6 + SIZES[n["kind"]] for n in leaves]
    offsets = np.cumsum([0] + lengths)
    x0 = np.concatenate([np.r_[n.get("center", [0, 0, 0]), n.get("rotation", [0, 0, 0]), n["size"]] for n in leaves])
    lo = np.concatenate([np.r_[[-4]*3, [-2*np.pi]*3, [.002]*SIZES[n["kind"]]] for n in leaves])
    hi = np.concatenate([np.r_[[4]*3, [2*np.pi]*3, [4]*SIZES[n["kind"]]] for n in leaves])
    points, target = samples(mesh, seed=seed)
    def assign(x):
        for i, node in enumerate(leaves):
            v = x[offsets[i]:offsets[i+1]]
            node.update(center=v[:3].tolist(), rotation=v[3:6].tolist(), size=v[6:].tolist())
    def residual(x):
        assign(x)
        return np.clip(field(result, points), -.18, .18)-target
    fitted = least_squares(residual, np.clip(x0, lo+1e-7, hi-1e-7), bounds=(lo, hi), max_nfev=max_nfev, ftol=1e-4, xtol=1e-4)
    assign(fitted.x)
    try:
        validate(result)
    except ValueError:
        return program  # An invalid optimized torus must never replace its seed.
    return result


def export_mesh(program, resolution=112):
    validate(program)
    def bounds(node):
        if "op" in node:
            a,b=map(bounds,node["children"])
            if node["op"]=="difference": return a
            if node["op"]=="intersection": return np.maximum(a[0],b[0]),np.minimum(a[1],b[1])
            return np.minimum(a[0],b[0]),np.maximum(a[1],b[1])
        s=node["size"]; kind=node["kind"]
        if kind=="box": ext=np.array(s)
        elif kind=="sphere": ext=np.full(3,s[0])
        elif kind=="cylinder": ext=np.array([s[0],s[0],s[1]])
        elif kind=="cone": ext=np.array([max(s[:2]),max(s[:2]),s[2]])
        elif kind=="torus": ext=np.array([sum(s),sum(s),s[1]])
        else: ext=np.array([s[0],s[0],sum(s)])
        ext=np.abs(Rotation.from_rotvec(node.get("rotation",[0,0,0])).as_matrix()) @ ext
        center=np.array(node.get("center",[0,0,0]))
        return center-ext,center+ext
    lo,hi=bounds(program["root"])
    if np.any(hi<=lo): raise ValueError("Empty CSG bounds")
    pad=np.maximum((hi-lo)/32,.002); lo,hi=lo-pad,hi+pad
    # Coarse occupancy locates actual surface, then remesh a tight padded domain.
    def grid_values(lower, upper, n):
        axes = [np.linspace(lower[i], upper[i], n) for i in range(3)]
        pts = np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, 3)
        values = np.concatenate([field(program, p) for p in np.array_split(pts, max(1, len(pts)//20000))])
        return pts, values.reshape((n,)*3)
    pts, coarse = grid_values(lo, hi, 64)
    inside = pts[coarse.ravel() < 0]
    if not len(inside):
        raise ValueError("Empty or sub-resolution CSG")
    padding = (hi-lo)/63*2
    lo, hi = inside.min(axis=0)-padding, inside.max(axis=0)+padding
    _, values = grid_values(lo, hi, resolution)
    if np.any(values[[0,-1],:,:] < 0) or np.any(values[:,[0,-1],:] < 0) or np.any(values[:,:,[0,-1]] < 0):
        raise ValueError("CSG touches meshing boundary")
    vertices, faces, _, _ = marching_cubes(values, 0, spacing=(hi-lo)/(resolution-1))
    mesh = trimesh.Trimesh(vertices+lo, faces, process=True)
    trimesh.repair.fix_normals(mesh)
    if not mesh.is_watertight:
        raise ValueError("Export is not watertight")
    return mesh


def metrics(program, target, reconstruction, grid=64, seed=2027, count=5000):
    lo = np.minimum(target.bounds[0], reconstruction.bounds[0])-.02
    hi = np.maximum(target.bounds[1], reconstruction.bounds[1])+.02
    axes = [lo[i]+(np.arange(grid)+.5)*(hi[i]-lo[i])/grid for i in range(3)]
    xyz = np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, 3)
    truth = np.concatenate([target.contains(x) for x in np.array_split(xyz, max(1, len(xyz)//2000))])
    pred = np.concatenate([field(program, x)<0 for x in np.array_split(xyz, max(1, len(xyz)//20000))])
    union = (truth | pred).sum()
    a = target.sample(count, seed=seed)
    b = reconstruction.sample(count, seed=seed+1)
    # Point-to-triangle distances avoid sampling-density bias in a 1% P95 gate.
    distances = np.r_[np.concatenate([trimesh.proximity.closest_point(reconstruction, x)[1] for x in np.array_split(a, 10)]),
                      np.concatenate([trimesh.proximity.closest_point(target, x)[1] for x in np.array_split(b, 10)])]
    return {f"voxel_iou_{grid}": float((truth & pred).sum()/union) if union else 0.,
            "surface_distance_mean": float(distances.mean()), "surface_distance_p95": float(np.quantile(distances, .95)),
            "surface_distance_p95_relative": float(np.quantile(distances, .95)/np.linalg.norm(target.extents)),
            "primitive_count": len(validate(program)), "reconstructed_watertight": bool(reconstruction.is_watertight),
            "surface_metric": "symmetric sampled point-to-triangle", "sample_count_per_mesh": count, "seed": seed}


def preview(target, reconstruction, path):
    fig = plt.figure(figsize=(10, 5))
    lo, hi = target.bounds
    center = (lo+hi)/2
    span = max(hi-lo)*.6
    for i, (m, title) in enumerate([(target, "Input"), (reconstruction, "RSI CSG")], 1):
        ax = fig.add_subplot(1, 2, i, projection="3d")
        # Dense marching-cubes meshes can make Matplotlib's vector triangulation
        # sorting dominate an entire run. Uniform surface samples are visualization
        # only; metrics and exported geometry always retain the complete surface.
        points=m.sample(8000,seed=123)
        ax.scatter(*points.T,s=.4,c=points[:,2],cmap="Blues",rasterized=True)
        ax.set(xlim=(center[0]-span, center[0]+span), ylim=(center[1]-span, center[1]+span), zlim=(center[2]-span, center[2]+span), title=title)
        ax.set_box_aspect((1,1,1)); ax.view_init(25, -55)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def inspect(mesh):
    points = mesh.sample(6000, seed=23)
    _, _, vh = np.linalg.svd(points-points.mean(axis=0), full_matrices=False)
    return {"bounds": mesh.bounds.tolist(), "extents": mesh.extents.tolist(),
            "volume": float(mesh.volume), "area": float(mesh.area), "components": len(mesh.split()),
            "principal_axes": vh.tolist(), "vertices": len(mesh.vertices), "faces": len(mesh.faces)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["inspect", "optimize", "evaluate", "export", "residual"])
    parser.add_argument("--mesh")
    parser.add_argument("--program")
    parser.add_argument("--out", required=True)
    parser.add_argument("--grid", type=int, default=64)
    parser.add_argument("--seed", type=int, default=2027)
    parser.add_argument("--max-nfev", type=int, default=45)
    args = parser.parse_args()
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    mesh = load_mesh(args.mesh) if args.mesh else None
    program = json.loads(Path(args.program).read_text()) if args.program else None
    if program: validate(program)
    if args.action == "inspect":
        data = inspect(mesh)
    elif args.action == "optimize":
        data = optimize(program, mesh, args.seed, args.max_nfev)
    elif args.action == "residual":
        pts, truth = samples(mesh, count=1500, seed=args.seed)
        pred = field(program, pts)
        missing = pts[(truth < -.01) & (pred > .01)]
        excess = pts[(truth > .01) & (pred < -.01)]
        data = {"missing_points": missing[:600].tolist(), "excess_points": excess[:600].tolist(),
                "missing_count": len(missing), "excess_count": len(excess)}
    elif args.action == "export":
        export_mesh(program).export(out); print(out); return
    else:
        reconstruction = export_mesh(program)
        data = metrics(program, mesh, reconstruction, args.grid, args.seed)
        reconstruction.export(out.with_suffix(".stl"))
        preview(mesh, reconstruction, out.with_suffix(".png"))
    out.write_text(json.dumps(data, indent=2)); print(json.dumps(data))


if __name__ == "__main__":
    main()
