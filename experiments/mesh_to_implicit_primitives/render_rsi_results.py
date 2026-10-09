#!/usr/bin/env python3
"""Render saved RSI triangle meshes with orthographic Embree ray casting."""
import argparse
import base64
import json
import os
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR', '/tmp/mesh-rsi-mpl')
import numpy as np
import trimesh
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def render(mesh, center, span, elevation, azimuth, pixels=512):
    elev, az = np.deg2rad([elevation, azimuth])
    eye = np.array([np.cos(elev)*np.cos(az), np.cos(elev)*np.sin(az), np.sin(elev)])
    right = np.array([-np.sin(az), np.cos(az), 0.])
    up = np.cross(eye, right)
    x, y = np.meshgrid(np.linspace(-span, span, pixels), np.linspace(span, -span, pixels))
    origins = center + eye*span*4 + x.reshape(-1, 1)*right + y.reshape(-1, 1)*up
    directions = np.broadcast_to(-eye, origins.shape).copy()
    intersector = trimesh.ray.ray_pyembree.RayMeshIntersector(mesh)
    triangle = intersector.intersects_first(origins, directions)
    valid = triangle >= 0
    normals = mesh.face_normals[triangle[valid]]
    light = eye + .5*up - .4*right
    light /= np.linalg.norm(light)
    shade = .32 + .68*np.clip(normals @ light, 0, 1)
    rgb = np.ones((pixels*pixels, 3))
    rgb[valid] = np.array([.28, .58, .83])*shade[:, None]
    return rgb.reshape(pixels, pixels, 3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir', type=Path)
    args = parser.parse_args()
    root = args.run_dir
    assert trimesh.ray.has_embree, 'Embree is required for solid mesh rendering'
    report_path = root/'报告.md'
    report = report_path.read_text() if report_path.exists() else None
    html_path = root/'visualization.html'
    html = html_path.read_text() if html_path.exists() else None
    for case in json.loads((root/'cohort.json').read_text()):
        folder = root/'cases'/case['name']
        final = folder/'final'
        if not (final/'reconstruction.stl').exists():
            continue
        target = trimesh.load(case['path'], force='mesh', process=True)
        result = trimesh.load(final/'reconstruction.stl', force='mesh', process=True)
        # The exported STL and source share the original coordinate system.
        bounds = np.stack([target.bounds, result.bounds])
        lo, hi = bounds[:, 0].min(axis=0), bounds[:, 1].max(axis=0)
        center = (lo+hi)/2
        span = np.linalg.norm(hi-lo)*.55
        fig, axes = plt.subplots(3, 2, figsize=(10, 13.8), facecolor='white')
        for row, (elev, az, label) in enumerate([(25, -55, 'Oblique'), (25, 125, 'Reverse'), (90, -90, 'Top')]):
            for col, (mesh, name) in enumerate([(target, 'Input mesh'), (result, 'RSI CSG mesh')]):
                axes[row, col].imshow(render(mesh, center, span, elev, az))
                axes[row, col].set_title(f'{name} | {label}', fontsize=13)
                axes[row, col].axis('off')
        fig.suptitle(case['name'], fontsize=16)
        fig.tight_layout(rect=(0, 0, 1, .98))
        out = final/'comparison_mesh.png'
        fig.savefig(out, dpi=150, facecolor='white')
        plt.close(fig)
        if report is not None:
            report = report.replace(f'cases/{case["name"]}/final/comparison.png', f'cases/{case["name"]}/final/comparison_mesh.png')
        if html is not None and (final/'comparison.png').exists():
            old = base64.b64encode((final/'comparison.png').read_bytes()).decode()
            new = base64.b64encode(out.read_bytes()).decode()
            html = html.replace(old, new)
        print(out, flush=True)
    if report is not None:
        report = report.replace('每张图左侧为输入网格，右侧为 RSI CSG 重建。图片展示表面采样点，颜色不表示重建误差；当前单一视角不能展示所有遮挡面或内部细节。',
            '每组左侧为输入三角网格，右侧为最终 STL 三角网格；依次展示斜视、反向斜视和俯视。使用完整三角面进行正交射线渲染，保留遮挡关系，不使用点云或网格简化。两侧视角、尺度和光照一致；蓝色明暗表示表面法向光照，不表示重建误差。内部封闭结构未通过剖面展示。')
        report_path.write_text(report)
    if html is not None:
        html = html.replace('采用表面采样点展示，颜色不表示误差。', '使用完整三角面渲染斜视、反向斜视和俯视，颜色明暗表示光照，不表示误差。')
        html_path.write_text(html)


if __name__ == '__main__':
    main()
