# 07 · 近期文献地图与研究比较（2024–2026）

[总目录](README.md) · [上一章](06_zero_to_cad.md)

## 学习目标

按输出表示和研究问题选择后续论文；把 Autodesk 近期工作放到主线中；能提出可检验的比较，而不是只说“用更大的模型”。

## 1. 补充阅读只选近期、直接相关的工作

按用户偏好，额外推荐均在 **2024–2026 年**。较早工作只保留截图指定的 UCSG-Net、D²CSG，以及原始 nTop 入门文章。DeepCAD、Fusion360、ABC 等名称在前文作为论文实际使用的数据集出现，不另布置一组旧论文。

以下七篇是**定向扩展阅读**：根据一手论文摘要、项目和机构页面核对问题、表示及发表状态；不把它们写成与核心五篇同等深度的全文精读，也不引入未经核对的实验排名。完整来源见 [参考资料](references.md)。

| 补充论文 | 年份 / 状态 | 补哪一块 | 建议接在哪章后 |
|---|---|---|---|
| [PrimitiveAnything](https://primitiveanything.github.io/) | SIGGRAPH 2025 | 学习人类基元装配先验；腾讯 / 清华 | 03 |
| [BrepGen](https://www.research.autodesk.com/publications/brepgen/) | ACM TOG / SIGGRAPH 2024 | 层次潜几何与扩散生成 B-rep；Autodesk / SFU | 01 后预览，07 精读 |
| [AutoBrep](https://github.com/AutodeskAILab/AutoBrep) | SIGGRAPH Asia 2025 | 统一几何与拓扑 token；Autodesk 主线 | 07 |
| [BrepARG](https://arxiv.org/abs/2601.16771) | CVPR 2026 | 整体 B-rep token 序列的另一种设计 | AutoBrep 后 |
| [CAD-Recode](https://github.com/filaPro/cad-recode) | ICCV 2025；预印本 2024 | 点云到 Python CAD 程序；卢森堡大学团队 | 05 |
| [cadrille](https://arxiv.org/abs/2505.22914v3) | ICLR 2026；预印本 2025 | 多模态 CAD 与执行反馈强化学习 | 06 |
| [FlexCAD](https://github.com/microsoft/FlexCAD) | ICLR 2025 | 分层可控生成与编辑；微软研究相关工作 | 06–07 |

## 2. 先对比 PrimitiveAnything 与 SuperFit

PrimitiveAnything 将基元抽象组织成条件自回归生成，利用人类制作的基元装配监督，预测类型、位姿、尺度等属性。它补的是“人类如何分解形状”的数据先验，而 SuperFit 更依赖目标几何与逐形状优化。[作者项目页](https://primitiveanything.github.io/)

**阅读问题：** 当输入在训练分布外，预测式方法与优化式方法谁更稳定？如果预测结果再做 test-time optimization，几何质量、语义一致性、运行时间各如何变化？SuperFit 的主表已经区分 PA 和 PA(TTO)，说明比较时不能忽略后处理。

## 3. Autodesk 近期路线：直接生成 B-rep

### 3.1 BrepGen：生成层次结构，再恢复共享关系

BrepGen 将实体—面—边—顶点组织成层次树，节点包含空间范围和局部几何潜表示，使用扩散模型逐层生成。共享边等拓扑关系通过重复节点表示，后续识别并合并以恢复连接。[Autodesk 论文页面](https://www.research.autodesk.com/publications/brepgen/)

这正好回答第 01 章的问题：只生成看起来相接的面还不够，还得知道哪些边被两个面共享。生成树结构也不等于生成建模历史树。

### 3.2 AutoBrep：把几何与拓扑放进同一序列

AutoBrep 的 token 同时描述局部几何和拓扑引用，按 B-rep 面邻接图的广度优先次序生成。其输出是几何与连接关系，而非 Extrude/Fillet 的设计历史。[Autodesk 官方代码与表示说明](https://github.com/AutodeskAILab/AutoBrep)

**讲义分析：** 面图遍历顺序是一种序列化策略，不是人类建模顺序。两个方法都使用 next-token prediction，也可能学习完全不同的随机变量：AutoBrep 预测边界结构，Zero-to-CAD 下游模型预测可执行源代码。

### 3.3 BrepARG：另一种近期整体序列表示

BrepARG 将几何、位置和面索引组织为整体 token 序列，配合自回归模型生成。它适合与 AutoBrep 比较“拓扑引用怎样编码”，并提醒我们前沿中的主要差异可能在表示，而不仅是 Transformer 大小。[论文入口](https://arxiv.org/abs/2601.16771) · [CVPR 2026 正式论文](https://openaccess.thecvf.com/content/CVPR2026/papers/Li_AutoRegressive_Generation_with_B-rep_Holistic_Token_Sequence_Representation_CVPR_2026_paper.pdf)

不要直接复述各论文“首次”的说法来判定优先权；发布日期、版本和具体定义可能不同。

## 4. 程序路线：快速重建、反馈学习与局部控制

**CAD-Recode：** 将点云映射到可执行的 Python/CadQuery 草图拉伸程序，利用预训练代码模型和合成序列。它是理解 CADFit 基线与 Zero-to-CAD 数据动机的直接桥梁。读取时重点核对操作词表，不把任意 Python 的语言能力当成训练数据覆盖了任意 CAD 操作。[官方论文与代码](https://github.com/filaPro/cad-recode)

**cadrille：** 在多模态程序重建中先做监督微调，再利用程序化反馈做在线强化学习。其 v3 标注 ICLR 2026；早期题名带 Online，最新版题名为 *Multi-modal CAD Reconstruction with Reinforcement Learning*。这条路线把执行结果变成参数更新信号，区别于仅在生成时重试代码。[arXiv v3](https://arxiv.org/abs/2505.22914v3)

**FlexCAD：** 将 CAD 层次结构转为文本，训练时遮盖不同层级的片段，再生成被遮盖部分。它补充“保留既有结构、只改局部”的控制问题，而不只是从零生成整个对象。[微软研究页面](https://www.microsoft.com/en-us/research/publication/flexcad-unified-and-versatile-controllable-cad-generation-with-fine-tuned-large-language-models/)

## 5. 五篇核心论文放在同一张问题表里

| 方法 | 输入与输出 | 优化 / 监督 | 保留的结构 | 不能由该输出直接保证的内容 |
|---|---|---|---|---|
| SuperFit | 形状 → 解析基元软并装配 | 单形状几何优化 | 基元形状参数、装配 | 原始 CAD 操作与约束 |
| UCSG-Net | 形状 → CSG | 无真实树标签的 encoder 与可微重建 | 基元与布尔组合 | 任意复杂度、原始历史 |
| D²CSG | 形状 → 双分支 CSG | 单形状 latent/network 优化 | 补集、交并差结构 | 全局最短树与精确距离 |
| CADFit | 水密 Mesh → CAD 程序 | 几何搜索 + 学习型草图筛选 | 操作序列、参数及引用 | 原始设计意图和制造约束 |
| Zero-to-CAD | 描述 → 合成代码；多视图 → 代码模型 | 代理验证合成 + 监督微调 | 可重放源代码 | 完整 DFM、用户理解和编辑稳定性 |

本表综合前面各章，不以不同论文的同名 IoU 数字排名。

## 6. 三个可操作的研究方向

这些是**讲义提出的研究问题，不是已经完成的实验，也不宣称具有未被研究过的新颖性**。

### A. 预测初始化是否能减少拟合成本？

在相同基元词表下，比较随机初始化、几何初始化、学习初始化，加同一优化器。固定目标集合、时间预算、硬件和最终离散导出。报告 IoU—基元数—时间曲线，并按薄结构、孔洞和曲率分层。若只换初始化却同时换词表，就无法归因。

### B. 好看的程序是否真的好改？

给定孔径、厚度等语义明确的参数，进行小范围扰动并重执行。报告成功率、目标尺寸变化、非目标区域变化、约束维持情况。对“未暴露该参数”的程序单列覆盖率，不能只挑最容易编辑的样本。

### C. 执行反馈是在改质量，还是只在删难例？

分别测无反馈、只过滤、推断时修复、训练时反馈四种策略。记录尝试总数、成功数、成功条件质量和失败记零质量；控制总生成或训练预算。否则“有效数据更多”可能只是消耗了更多重试而非更好的算法。

## 7. 习题

1. AutoBrep 输出 token 序列，为什么仍不能说它恢复了 CAD 操作历史？
2. BrepGen 树里的重复边节点与 CSG 树里的重复基元是同一个问题吗？
3. 在数据引擎中修复程序，与用执行反馈做 RL 微调，分别在哪个阶段改变什么？
4. 设计一个能区分“可执行”与“可编辑”的最小测试，列出至少两个指标。

[答案与提示](exercises_and_answers.md)
