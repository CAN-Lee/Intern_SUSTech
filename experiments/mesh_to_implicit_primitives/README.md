# 从 Mesh 拟合隐式 CAD 基元

本目录用于把输入 Mesh 近似为少量基元构成的隐式 CSG 组合。

- `fusion360_gallery/`：从 Autodesk Fusion 360 Gallery Dataset 提取的 9 个 OBJ 案例，按简单、中等、困难分组；来源和许可证见[案例说明](fusion360_gallery/README.md)。
- `../../submodule/sdfcad/`：第三方 Git submodule，负责表示 SDF 并导出 Mesh；它本身不提供 Mesh 逆向拟合功能。
- `results/`：重建结果与中文[结果汇总](results/结果汇总.md)。

## 环境

本轮使用独立 Conda 环境 `/data/lican/miniconda3/envs/mesh_sdf_fit`，Python 3.10.20，CPU 运行。从本目录重建环境：

```bash
conda env create -f environment.yml
conda activate mesh_sdf_fit
python -m pip install -r requirements.txt
```

`sdfcad` 从本地第三方 submodule 以 editable 模式安装。数据集坐标已接近 `[-1, 1]`，本轮保留原坐标，没有额外归一化。

## 运行

从本目录运行全部 9 个案例：

```bash
python run_all.py
```

脚本复用已完成的结果，未完成的案例才重新计算；`--force` 可强制重跑。每例默认最多 3 个基元，随机种子 42，拟合时间参数为 600 秒。单例运行示例：

```bash
python fit_cases.py --case fusion360_gallery/easy/129012_576921da_0.obj --output results/easy_129012 --max-primitives 3 --seed 42 --time-limit 600
```

拟合器在可旋转盒体、有限圆柱体和球体之间选择，并以并集或差集逐步添加基元。新增基元须使独立采样点上的截断 SDF MSE 至少改善 3%。同名 `timeline_info` JSON 仅供结果分析，不作为拟合输入或真实基元标签。

每例目录包含中文 `结果说明.md`，以及 `program.json`、`reconstruction.stl`、`comparison.png`、`metrics.json` 和 `trace.json`。JSON 保留英文键名供程序读取；`run.log` 是原始执行日志。`program.json` 中负 SDF 表示实体内部，布尔运算按列表顺序执行。总表另存为中文表头的 [summary.csv](results/summary.csv)；`summary.json` 保留机器可读结构。

## 本轮结果

| 难度 | 案例 ID | 基元数 | 48³ 体素 IoU | 包围盒基线 IoU | 平均对称表面距离 |
|---|---|---:|---:|---:|---:|
| 简单 | `110956_df981ed9_0` | 2 | 1.000 | 0.957 | 0.00034 |
| 简单 | `129012_576921da_0` | 3 | 0.966 | 0.751 | 0.00938 |
| 简单 | `23853_4f653200_4` | 3 | 0.821 | 0.286 | 0.02342 |
| 中等 | `132948_7b65c184_2` | 3 | 0.982 | 0.919 | 0.00444 |
| 中等 | `140224_6952f93f_3` | 1 | 0.958 | 0.117 | 0.00178 |
| 中等 | `62111_9ba5436e_2` | 3 | 0.951 | 0.400 | 0.00790 |
| 困难 | `109857_1d24326e_6` | 3 | 0.614 | 0.698 | 0.01088 |
| 困难 | `138244_f79136e9_0` | 3 | 0.812 | 0.225 | 0.00886 |
| 困难 | `96174_fea894a7_0` | 3 | 0.979 | 0.611 | 0.00531 |

体素 IoU 在固定的 48³ 网格上评价隐式场，越高越好；表面距离从原 Mesh 和导出的 STL 各采样 1,500 点后双向计算，越低越好，单位为数据集坐标单位。9 份导出 STL 经顶点合并后均为闭合网格。

`109857` 的 IoU 低于包围盒基线，是本轮明显失败的拟合。它有 20 个源 CAD 操作；3 个基元可能不足，优化也可能未找到更好的组合。结果只说明几何近似程度，不证明恢复了原始 CAD 建模历史。前两例的较早初始化结果保存在 `results/iterations/` 供对比。
