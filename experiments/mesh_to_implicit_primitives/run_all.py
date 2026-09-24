"""运行全部 Fusion 360 Gallery 案例并生成中文结果记录。"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CASES = ROOT / "fusion360_gallery"
RESULTS = ROOT / "results"
REQUIRED = ("program.json", "metrics.json", "reconstruction.stl", "comparison.png", "trace.json")
LEVELS = {"easy": "简单", "medium": "中等", "hard": "困难"}
KINDS = {"box": "盒体", "cylinder": "圆柱体", "sphere": "球体"}
STATUSES = {"completed": "已完成", "reused": "已完成", "timeout": "超时"}


def completed(folder: Path) -> bool:
    if not all((folder / name).is_file() and (folder / name).stat().st_size > 0 for name in REQUIRED):
        return False
    try:
        metrics = json.loads((folder / "metrics.json").read_text())
        return bool(metrics["reconstructed_watertight"] and metrics["fit"]["voxel_iou_48"] is not None)
    except (OSError, ValueError, KeyError):
        return False


def output_name(case: Path) -> str:
    # Preserve the names already used for the first two results.
    if case.stem == "129012_576921da_0":
        return "easy_129012"
    if case.stem == "62111_9ba5436e_2":
        return "medium_62111"
    return f"{case.parent.name}_{case.stem}"


def program_description(nodes: list[dict]) -> str:
    expression = KINDS.get(nodes[0]["kind"], nodes[0]["kind"])
    for node in nodes[1:]:
        operator = "∪" if node["op"] == "union" else "−"
        expression = f"({expression} {operator} {KINDS.get(node['kind'], node['kind'])})"
    return expression


def write_case_report(case: Path, folder: Path) -> None:
    metrics = json.loads((folder / "metrics.json").read_text())
    nodes = json.loads((folder / "program.json").read_text())["program"]
    actual_iou = metrics["fit"]["voxel_iou_48"]
    baseline_iou = metrics["bbox_baseline"]["voxel_iou_48"]
    delta = actual_iou - baseline_iou
    input_link = os.path.relpath(case, folder)
    note = "拟合 IoU 低于包围盒基线，需视为本轮拟合失败。" if delta < 0 else "拟合 IoU 高于包围盒基线。"
    lines = [
        f"# 案例 {case.stem}：{LEVELS[case.parent.name]}", "",
        f"输入：[原始 OBJ]({input_link})。仅以 Mesh 为拟合输入，未读取同名时间线 JSON 作为标签。", "",
        "| 指标 | 结果 |", "|---|---:|",
        f"| 基元数 | {metrics['primitive_count']} |",
        f"| 48³ 体素 IoU | {actual_iou:.6f} |",
        f"| 包围盒基线 IoU | {baseline_iou:.6f} |",
        f"| IoU 相对基线差值 | {delta:+.6f} |",
        f"| 验证集截断 SDF MSE | {metrics['validation_mse']:.8f} |",
        f"| 平均对称表面距离 | {metrics['surface_distance_mean']:.6f} |",
        f"| 对称表面距离第 95 百分位 | {metrics['surface_distance_p95']:.6f} |",
        f"| 重建 STL 是否闭合 | {'是' if metrics['reconstructed_watertight'] else '否'} |",
        f"| 总耗时 | {metrics.get('total_seconds', float('nan')):.1f} 秒 |", "",
        f"**隐式组合：** {program_description(nodes)}。布尔运算按括号顺序执行；负 SDF 表示实体内部。", "",
        f"**判断：** {note}这些数值衡量几何近似，不证明恢复了原始 CAD 建模历史。", "",
        "文件：[重建 STL](reconstruction.stl) · [形状对比图](comparison.png) · [基元参数 JSON](program.json) · [原始指标 JSON](metrics.json) · [拟合过程 JSON](trace.json)", "",
        "体素 IoU 在固定的 48³ 网格上评估隐式场；表面距离从原 Mesh 与导出的 STL 各采样 1,500 个点后双向计算，单位为数据集坐标单位。", "",
    ]
    (folder / "结果说明.md").write_text("\n".join(lines), encoding="utf-8")


def write_summary(records: list[dict]) -> None:
    csv_fields = ("案例", "难度", "结果目录", "结果状态", "基元数", "体素IoU(48³)", "包围盒基线IoU(48³)", "平均对称表面距离", "总耗时(秒)")
    with (RESULTS / "summary.csv").open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=csv_fields)
        writer.writeheader()
        for record in records:
            case = Path(record["case"])
            writer.writerow({"案例": case.stem, "难度": LEVELS[case.parent.name], "结果目录": record["result_dir"],
                             "结果状态": STATUSES.get(record["status"], record["status"]),
                             "基元数": record.get("primitive_count", ""),
                             "体素IoU(48³)": record.get("voxel_iou_48", ""),
                             "包围盒基线IoU(48³)": record.get("bbox_iou_48", ""),
                             "平均对称表面距离": record.get("surface_distance_mean", ""),
                             "总耗时(秒)": record.get("total_seconds", "")})
    lines = ["# 九个 Mesh 案例的隐式基元拟合结果", "",
             "本轮所有案例使用相同设置：随机种子 42、最多 3 个基元；输入只有 OBJ Mesh。以下为几何拟合结果，不代表恢复了原始 CAD 操作。", "",
             "对比图中，**左侧为输入 Mesh（Input），右侧为拟合结果（Fitted implicit CSG）**。点击图片可查看原尺寸；点击案例名称可查看详细指标与重建文件。", "",
             "| 难度 | 案例 | 可视化对比（左：输入；右：拟合） | 基元数 | 48³ 体素 IoU | 包围盒基线 IoU | 平均对称表面距离 |", "|---|---|---|---:|---:|---:|---:|"]
    for record in records:
        case = Path(record["case"])
        report = f"{Path(record['result_dir']).name}/结果说明.md"
        comparison = f"{Path(record['result_dir']).name}/comparison.png"
        preview = (f'<a href="{comparison}"><img src="{comparison}" width="360" alt="{case.stem}：输入 Mesh 与拟合结果"></a>'
                   if (RESULTS / comparison).is_file() else "暂无对比图")
        if "voxel_iou_48" in record:
            lines.append(f"| {LEVELS[case.parent.name]} | [{case.stem}]({report}) | {preview} | {record['primitive_count']} | {record['voxel_iou_48']:.3f} | {record['bbox_iou_48']:.3f} | {record['surface_distance_mean']:.5f} |")
        else:
            lines.append(f"| {LEVELS[case.parent.name]} | {case.stem} | {preview} | — | {STATUSES.get(record['status'], record['status'])} | — | — |")
    lines.extend(["", "`109857_1d24326e_6` 的体素 IoU 为 0.614，低于包围盒基线 0.698，是本轮明显失败的案例。三个基元可能不足，优化过程也可能未找到更好的组合。", "",
                  "体素 IoU 越大越好；平均对称表面距离越小越好，单位是数据集坐标单位。每个案例目录均保留参数、重建 STL、对比图、原始指标和拟合过程。", ""])
    (RESULTS / "结果汇总.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="rerun cases with complete results")
    parser.add_argument("--time-limit", type=int, default=600)
    parser.add_argument("--max-primitives", type=int, default=3)
    args = parser.parse_args()
    RESULTS.mkdir(exist_ok=True)
    cases = [p for level in ("easy", "medium", "hard") for p in sorted((CASES / level).glob("*.obj"))]
    if len(cases) != 9:
        raise RuntimeError(f"Expected 9 OBJ cases; found {len(cases)}")
    records = []
    for case in cases:
        folder = RESULTS / output_name(case)
        relative_case = case.relative_to(ROOT)
        if completed(folder) and not args.force:
            status = "reused"
        else:
            folder.mkdir(exist_ok=True)
            command = [sys.executable, str(ROOT / "fit_cases.py"), "--case", str(relative_case),
                       "--output", str(folder.relative_to(ROOT)), "--max-primitives", str(args.max_primitives),
                       "--seed", "42", "--time-limit", str(args.time_limit)]
            environment = os.environ.copy()
            environment.setdefault("MPLCONFIGDIR", "/tmp/mpl-mesh-sdf")
            environment["OPENBLAS_NUM_THREADS"] = "1"
            with (folder / "run.log").open("w") as log:
                log.write("Command: " + " ".join(command) + "\n")
                log.flush()
                try:
                    result = subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT,
                                            timeout=args.time_limit + 120, check=False)
                    status = "completed" if result.returncode == 0 and completed(folder) else f"failed_exit_{result.returncode}"
                except subprocess.TimeoutExpired:
                    log.write("\nHard timeout exceeded.\n")
                    status = "timeout"
        record = {"case": str(relative_case), "result_dir": str(folder.relative_to(ROOT)), "status": status}
        if completed(folder):
            metrics = json.loads((folder / "metrics.json").read_text())
            record.update({"primitive_count": metrics["primitive_count"],
                           "voxel_iou_48": metrics["fit"]["voxel_iou_48"],
                           "bbox_iou_48": metrics["bbox_baseline"]["voxel_iou_48"],
                           "surface_distance_mean": metrics["surface_distance_mean"],
                           "total_seconds": metrics.get("total_seconds")})
            write_case_report(case, folder)
        records.append(record)
        print(f"{relative_case}: {status}" + (f", IoU={record['voxel_iou_48']:.3f}" if "voxel_iou_48" in record else ""), flush=True)
        (RESULTS / "summary.json").write_text(json.dumps(records, indent=2))
        write_summary(records)


if __name__ == "__main__":
    main()
