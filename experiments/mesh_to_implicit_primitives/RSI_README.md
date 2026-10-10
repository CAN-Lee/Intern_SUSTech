# 完整 RSIAgent Mesh 重建流程

入口为 `run_rsi.py`，配置为 `configs/rsi_standard.yaml`。原 `fit_cases.py` 和 `results/` 保留作为历史基线。

输入网格见 [data/README.md](data/README.md)。六页汇报位于 [experiments/presentations](../presentations/rsi_mesh2cad_20261010/RSI_Mesh2CAD_汇报.pptx)。

## 当前验证状态（2026-10-09）

- 几何、框架适配与相关上游回归测试：66 项通过。
- `rsi_runs/preflight_final/`：真实文本、视觉、Agent 执行、Embree 和只读记忆隔离预检通过。
- `rsi_runs/acceptance_verified/`：两个 BRS 练习、顺序记忆提交、DRS 目标验证及学习完成；
  冻结记忆后的新 Actor 已提交候选，最终 Verifier 的模型请求超时，记录为基础设施错误。
- `rsi_runs/acceptance_final/`：加入有界请求重试后重新执行；一个 BRS 分支通过，另一分支
  遇到提供方提示词策略拒绝（Gateway 包装为 HTTP 502），三次失败后停止，未提交该波记忆。

- 后续标准九例已经结束：7 例完成三阶段并通过最终验证，2 例错误中断。
  失败分别是 BRS 网格导出不闭合，以及最终重建阶段的模型服务 502/503。
  [九例指标与实体 mesh 对比图](results/rsi_standard_9_20261009/报告.md) 已归档，包含最终 CSG、STL 和验证指标。

上述合成验收失败记录仍保留，七个真实样例提供了完整端到端运行证据。
这些结果没有同预算消融对照，不能据此量化 RSI 本身带来的改进幅度。

第三方 RSIAgent 作为 Git submodule 固定版本，修改保存在用户仓库的
`thirdparty/rsiagent-mesh` 独立分支；没有向第三方上游推送修改。
新克隆后运行 `git submodule update --init --recursive` 获取依赖。
`rsi_runs/` 保留本地完整运行记录，Git 中的结果归档只包含最终产物和必要记录。

实体网格报告渲染命令：

```bash
.venv-rsi/bin/python render_rsi_results.py results/rsi_standard_9_20261009
```

渲染器使用完整三角面和一致的正交视角；运行中的快速预览仍使用表面采样点。

## 架构

此实现调用 RSIAgent 原仓库的 `core.loop.run_attempt`、
`explore.phase1_wave.evolve_parallel_phase1` 和
`core.self_evolving_loop.run_self_evolving_loop`。新增的几何适配器提供执行环境、
合成练习、独立几何验证及记忆传递；没有以硬编码贪心搜索替代 Agent。

1. BRS：Curriculum 观察目标，自主编写合成练习；并行 Actor 使用相同起始记忆。
   每个分支取得独立 Verifier 的有效结论后，上游调度器才按顺序恢复原 Actor 整理记忆。
2. DRS：实际目标尝试、独立验证、原 Actor 学习、Curriculum 决定下一项练习、
   新 Actor 再次尝试原目标。默认 `curriculum_review`，成功也经过学习和练习价值判断。
3. 冻结记忆：新环境、新上下文重建，记忆目录只读。最终评分在所有 Agent 调用结束后运行。

六类基元为盒体、有限圆柱、球、有限圆锥/圆台、圆环、胶囊；允许二叉并集、差集和交集。
Actor 自己选择树结构，数值优化只调整已给定结构的参数。默认 24 个叶节点、12 层。
布尔 SDF 的符号有几何含义，但组合场不保证是真实欧氏距离；评价表面距离不依赖这一假设。

## 安装和预检

当前专用管理环境为 `.venv-rsi`，复用原 `mesh_sdf_fit` 的科学计算依赖：

```bash
/data/lican/miniconda3/envs/mesh_sdf_fit/bin/python -m venv --system-site-packages .venv-rsi
.venv-rsi/bin/python -m pip install -r requirements-rsi-host.lock.txt
docker build -t mesh-rsi:verified -f docker/rsi.Dockerfile docker
.venv-rsi/bin/python run_rsi.py preflight
```

当前旧会话需要通过 `sg docker -c '完整命令'` 获得已授予的 Docker 组权限。
不要在执行容器内启动 Gateway。模型调用来自管理进程，默认使用已存在的
`http://127.0.0.1:9000/v1`，模型 `azure/gpt-5.6-sol`，占位 key `local-gateway`。
如需覆盖 key，设置 `RSI_GATEWAY_API_KEY`。该通道依赖已有 Gateway 和 SSH 隧道。
临时网络或服务错误最多请求 3 次，每次超时 120 秒，保持请求参数不变；
参数错误立即结束，连续请求失败记为基础设施错误，不生成虚假的 Agent 动作或评分。

预检包含真实文本调用、图片调用、Agent 程序动作以及容器依赖和隔离检查。
不会将读取不到图片的模型静默替换成另一个模型。

## 运行

```bash
sg docker -c '.venv-rsi/bin/python run_rsi.py run --synthetic --run-dir rsi_runs/acceptance'
sg docker -c '.venv-rsi/bin/python run_rsi.py run --all --run-dir rsi_runs/standard_9'
sg docker -c '.venv-rsi/bin/python run_rsi.py run --case fusion360_gallery/easy/129012_576921da_0.obj'
.venv-rsi/bin/python run_rsi.py report --run-dir rsi_runs/standard_9
```

也可使用 `bash run_rsi.sh run --all --run-dir rsi_runs/standard_9`；该启动器会自动通过
`sg docker` 获取已授予的组权限。合成验收可选 `--config configs/rsi_acceptance.yaml`，
同样执行全部三阶段，但 BRS 预算为 2 个练习；正式九例仍采用标准配置的 8 个。

九例串行运行，每例 BRS 最多 8 个练习、同时执行最多 2 个；DRS 最多 4 个目标周期、
8 个练习。学习总预算 2 小时，最终重建 30 分钟。预算耗尽不是收敛。
失败案例与基础设施错误保留在总表中，不用旧基线分数替代。
`completed` 仅表示流程与最终评分完成，不代表达到了几何 PASS 门槛；以最终
`metrics.json` 的 `verifier_verdict` 和实际数值为准。

仅恢复完成且哈希验证通过的学习边界：

```bash
sg docker -c '.venv-rsi/bin/python run_rsi.py resume --run-dir rsi_runs/standard_9'
```

源代码、模型配置、输入内容、镜像改变会拒绝续跑。学习中途尚未形成支持的完整边界时，
命令明确拒绝恢复，不伪造旧 Actor 上下文或重用未提交记忆。最终阶段的中断产物会归档。

## 输出和评价口径

每轮保存源文件哈希、上游 revision 与补丁、Docker 镜像 ID、只读工具快照、配置及输入 SHA256。
每例保留 `events.jsonl`、各角色真实动作/工具输出/对话、生成练习、Verifier 证据、
记忆前后快照、`learning_boundary.json`、冻结记忆及 `result.json`。

最终文件位于 `cases/<case>/final/`：`program.json`、`reconstruction.stl`、
`comparison.png`、`metrics.json`。CSG 参数处于最长边为 2 的规范坐标；
`normalization` 保存恢复变换，STL 已回到输入坐标。

局部 PASS 条件为有效非空 CSG、闭合网格、64³ IoU ≥ 0.95、对称点到三角面距离
P95 ≤ 包围盒对角线的 1%。Verifier 独立查阅几何证据，管理端复核数值门槛。
最终采用另外的采样种子和 96³ 体素网格，另提供旧拟合器同网格定义的 48³ IoU。
历史表面距离采用采样点到采样点，本实现采用采样点到三角面，二者不可直接相减。

合成练习的生成树只留在管理端，学习 Actor 只能接触其 Mesh。原始 CAD 时间线、
历史结果、最终评分器不挂载到学习环境。Verifier 使用候选副本，不接触 Actor 记忆；
同一模型的独立上下文不等于跨模型独立性。

记忆为 Actor 自主维护的文本与脚本目录，禁止输入 Mesh、STL 和完整目标答案作为记忆。
文件边界、大小和类型由程序检查；自然语言中经验的正确性仍依赖模型判断，不能据此宣称无错误。

```bash
MPLCONFIGDIR=/tmp/mesh-rsi-mpl OPENBLAS_NUM_THREADS=1 .venv-rsi/bin/python -m pytest tests -q
```
