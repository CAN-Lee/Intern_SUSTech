# 07 · 扩展论文：按六部分快速阅读

[总目录](README.md) · [上一章](06_zero_to_cad.md)

七篇扩展论文均按“前置知识 → 动机 → 贡献 → 方法流程 → 实验 → 局限性”介绍，深度低于前面五篇核心精读。数字来自 `papers/` 中对应 PDF 的指定表格，是作者报告，讲义未复现。每篇的评价任务与数据协议不同，不跨论文直接比较同名指标。

生成任务的 COV ↑、MMD ↓、JSD ↓ 衡量样本集对参考分布的覆盖和距离；它们不等同于给定一个输入 Mesh 后的逐样本重建误差。Valid / IR 另行衡量有效性，具体判据以各论文为准。

## 1. PrimitiveAnything

**原文：** [arXiv:2505.04622](https://arxiv.org/abs/2505.04622)，本地 PDF 对应 §3–4、Tables 1–5。

### 1. 前置知识

[基元与坐标变换](02_math_and_optimization.md)、point-cloud encoder、自回归序列建模、离散参数量化和 Gumbel-Softmax。一个基元需要类型、尺度、旋转和平移；基元序列还需定义排序与终止符。

### 2. 动机

只按几何距离拟合基元，常得到与人类部件划分不同的装配。作者希望利用人工制作的基元装配，学习从点云到可变长度、可解释基元序列的条件分布。

### 3. 贡献

HumanPrim 提供人工装配监督；对基元自身对称性设计规范化编码以减少等价标签歧义；自回归 Transformer 配合级联属性预测生成多类型、可变长度序列（§3）。

### 4. 方法流程 / Pipeline

**训练：** 人工装配规范化并按中心排序 → 编码类型、尺度、旋转、平移 → 点云 encoder 提供条件 → next-token / 属性监督、EOS 损失和基元 CD 损失。

**推断：** 点云 → Michelangelo encoder → 自回归预测基元属性 → EOS 停止 → cuboid、elliptical cylinder、ellipsoid 装配。其主要输出是基元装配，没有预测通用差集 CSG 树。CD 项通过 Gumbel-Softmax 使离散属性获得梯度。

### 5. 实验

§4.1：HumanPrim 约 120K 样本，测试集选取 314 个高质量人工标注样本；另评测 ShapeNet 泛化。Table 1 比较 EMS、Marching Primitives（MP）；Table 2 比较分解标签一致性。Table 2 中 RI ↑：EMS 0.696、MP 0.821、本文 0.892；SC ↑ 分别为 0.280、0.254、0.409，支持人工装配先验改善部件划分的结论。

几何实验的 Voxel-IoU 使用 $32^3$ 网格上体素化的点云，不能与 SuperFit 的体积占据 IoU 混用。Table 5 消融规范化、级联预测和 CD 损失，检验表示及训练目标的作用。

### 6. 局限性

固定的三类基元限制复杂曲面的精细重建，人工装配监督有采集成本且带分解偏好。自回归误差会影响后续部件；训练分布外的形状仍需专门评测。若增加 test-time optimization，应把额外优化成本与前向生成分别报告。后两点是讲义分析。

## 2. BrepGen

**原文：** [作者机构论文 PDF](https://damassets.autodesk.net/content/dam/autodesk/www/pdfs/brepgen.pdf)，本地 TOG 2024 版 §4–6、Tables 1–2。

### 1. 前置知识

[第 01 章 B-rep](01_representations.md)、face/edge/vertex incidence、VAE 的潜表示、diffusion 的加噪与去噪，以及几何内核的曲面拟合和 sewing。

### 2. 动机

只生成 sketch-extrude 历史会受操作词表限制；直接生成 B-rep 又要处理数量可变的面、边及共享关系。论文用统一层次表示组织几何和拓扑，使扩散生成可以逐层进行。

### 3. 贡献

提出 structured latent geometry：将 B-rep 展开为层次树，用节点位置与局部几何 latent 表示实体；共享拓扑通过重复节点表达，再恢复合并。另构建 Furniture B-rep 数据用于类别条件生成。

### 4. 方法流程 / Pipeline

**训练：** B-rep → 曲面/曲线采样与 VAE 编码 → 包含重复共享节点的层次树 → 训练分层条件 diffusion。

**生成：** 去噪生成 face 位置与几何 → 生成附属 edge / vertex 信息 → 识别并合并重复节点 → 对齐几何、拟合曲线曲面 → sewing 成实体。输出是 B-rep，层次树不表示草图拉伸历史（§4、Figs. 2–4）。

### 5. 实验

DeepCAD 使用原始数据划分；ABC、Furniture 按 90%/5%/5% 分为 train/val/test（§6）。DeepCAD 无条件生成 Table 1：BrepGen 的 COV 为 73.87%、Valid 为 62.9%；SolidGen 分别为 71.03%、60.3%。这说明其在该生成协议下提高覆盖与有效率，仍有无效结果。

Valid 要求水密且拓扑完整；Novel / Unique 在有效 B-rep 上计算。MMD、JSD 的表值乘以 $10^2$。Table 2 使用给定 topology 的条件实验分析结构恢复；不能把它当成无条件生成结果。

### 6. 局限性

生成的几何与重复节点未必一致，合并阈值、几何优化和 sewing 会影响有效率。表示与采样几何也带来误差，复杂面数受到模型容量和预处理约束。输出不携带原始参数化特征历史，因此用 B-rep 编辑它与修改原始设计步骤是不同操作。

## 3. AutoBrep

**原文：** [arXiv:2512.03018](https://arxiv.org/abs/2512.03018)，本地 PDF §4–7、Tables 1–3。

### 1. 前置知识

B-rep 面邻接图、广度优先遍历（BFT）、几何量化 token、自回归 Transformer 和拓扑引用。需要区分“面在 token 序列中的编号”与“CAD 建模历史步骤”。

### 2. 动机

几何与拓扑分开生成，容易在后处理时出现不匹配；面数增加后，全局引用还会扩大序列复杂度。论文希望在一个序列中联合生成相邻面、边和共享关系，并支持给定部分面后的补全。

### 3. 贡献

以面邻接图 BFT 组织几何和拓扑 token；使用局部上下文窗口中的面引用；构建 ABC-1M、ABC-Constraint 支持无条件预训练与受约束补全。

### 4. 方法流程 / Pipeline

**训练：** B-rep 几何编码 → BFT 排序 → face / edge geometry token 与局部拓扑 reference token 混合序列 → next-token 训练 → 补全任务微调。

**生成：** 无条件起始符或给定 faces → 逐步生成相邻面、边与引用 → 几何解码 → 根据预测 incidence 裁剪、sewing。补全任务以保留输入几何为约束；不需要把面邻接顺序解释成机械建模顺序（§4–5）。

### 5. 实验

ABC-1M 从去重后的约 1.3M 实体按面数分层，以 70%/15%/15% 划分。Table 1 的无条件生成：AutoBrep Valid=70.8%、COV=71.49%；在该数据上重新训练的 BrepGen 为 46.6%、67.41%。这些值与 BrepGen 原论文的 DeepCAD 表不可直接比较。

Table 1 消融：坐标排序 AutoBrep coord 的 Valid=63.6%；移除局部窗口并采用全局引用的 AutoBrep global 为 65.3%。它们支持遍历与局部引用设计的作用。Valid 为水密实体比例；推断时间按有效结果的每个 face 平均，不能当作每个零件的总耗时。

### 6. 局限性

几何 token 的压缩、长序列和复杂拓扑仍影响有效性；70.8% 的有效率不是始终成功。给定面保持与整个实体的拓扑、制造约束有效性是不同要求。B-rep 补全结果也不自动提供原始特征树（§7 与讲义分析）。

## 4. BrepARG

**原文：** [CVPR 2026 PDF](https://openaccess.thecvf.com/content/CVPR2026/papers/Li_AutoRegressive_Generation_with_B-rep_Holistic_Token_Sequence_Representation_CVPR_2026_paper.pdf)，本地 PDF §3–5、Tables 1–5。

### 1. 前置知识

B-rep、VQ-VAE、标量量化、面索引与自回归生成；top-p sampling 控制生成多样性与保守程度。

### 2. 动机

B-rep 同时包含连续几何和离散关联，分开建模会增加生成及拓扑恢复的复杂度。作者希望将两者编码为统一 token 序列，通过 next-token prediction 学习联合分布。

### 3. 贡献

设计 geometry、position、face index 三类 token；构造 face / edge blocks 并排序为 holistic sequence；用共享几何 tokenizer 与统一自回归模型完成生成（Fig. 2、§3）。

### 4. 方法流程 / Pipeline

**训练：** 面/边采样 → VQ-VAE geometry token；bounding box → 标量量化 position token；关联面 → face index token → 拼接 block 序列并训练 Transformer。

**生成：** 起始符或类别 token → 自回归采样 blocks → 解码几何和位置 → 用 face indices 恢复关联 → 曲面拟合与实体重建。面索引显式表示关联，但几何是否能拼合仍需检查。

### 5. 实验

§5.2 每轮用 3,000 个生成 B-rep 和 1,000 个参考形状计算分布指标，每个形状采 2,000 个点，报告 10 次独立运行均值。Table 1 中 DeepCAD：BrepARG Valid=87.60%、COV=75.45%；该表的 DTGBrepGen 为 79.80%、74.52%。ABC 上本文 Valid=67.54%。

Table 3 调整 top-p：从 0.9 到 0.6，DeepCAD Valid 从 87.60% 升至 90.25%，COV 从 75.45% 降至 63.50%。这直接展示有效性与覆盖的取舍。MMD/JSD 表值乘 $10^2$，Valid 是所有生成实体中通过内核检查的比例。

### 6. 局限性

§5.4 展示量化精度与几何/拓扑不一致相关的失败案例。统一 token 序列并不消除解码误差；提高有效性可能损失多样性。其生成任务也不等于从任意 Mesh 恢复 CAD 历史。

## 5. CAD-Recode

**原文：** [arXiv:2412.14042](https://arxiv.org/abs/2412.14042)，本地 PDF §3–5、Tables 1–4。

### 1. 前置知识

点云采样与位置编码、预训练代码 LLM、自回归条件生成、CadQuery sketch-extrude 程序及 Chamfer Distance。

### 2. 动机

已有 CAD 序列模型受专用命令格式和训练数据规模限制。作者研究能否使用预训练代码模型直接输出 Python CAD 程序，并用程序化合成数据扩大监督。

### 3. 贡献

将点云条件接到轻量代码 LLM；用 Python/CadQuery 表示重建；构建百万级程序化合成数据；执行多个候选并按几何距离选择输出（§3–4）。

### 4. 方法流程 / Pipeline

**训练：** 合成 sketch-extrude 程序 → 执行并采样点云 → 位置编码和投影得到 point tokens → 与代码配对微调 Qwen2-1.5B。

**推断：** 输入点云 → 多次采样 → 自回归生成 10 个代码候选 → 执行候选并采表面点 → 选择 CD 最小的有效结果。一次 decoder 生成与完整的多候选选择应分别计时（§4.3）。

### 5. 实验

Table 1 在 DeepCAD 与 Fusion360 测试，Table 2 在真实扫描 CC3D 测试。CC3D 的 IoU ↑ / IR ↓：CAD-SIGNet 为 42.6% / 2.5%，CAD-Recode 为 74.2% / 0.3%。IR 是无法生成有效 CAD 的序列比例；IoU 属于几何质量，两者需同时报告。

Table 3 比较 DeepCAD 训练、同规模合成数据、百万合成数据及 test-time sampling，区分表示、数据规模和候选选择的作用；Table 4 研究输入点数与 backbone 大小。上述 CC3D 数字来自该论文自身配置，不能与 CADFit 中重新评测的 CAD-Recode 混用。

### 6. 局限性

§5.1 明确指出复杂 revolve、fillet 等超出其合成 sketch-extrude 分布的结构仍难恢复。Python 语言表达能力大于训练数据覆盖的 CAD 操作范围。扫描缺失信息与相同形状的多种程序历史也使“恢复原始设计”无法由低 CD 保证。

## 6. cadrille

**原文：** [arXiv:2505.22914v3](https://arxiv.org/abs/2505.22914v3)，本地 v3 §3–4、Tables 1–3。

### 1. 前置知识

多模态条件生成、SFT、策略优化与奖励、可执行 CAD 代码、几何 CD。理解“修复当前程序”和“反馈更新模型权重”的区别。

### 2. 动机

仅做 next-token 监督，生成代码的概率不一定反映执行后的几何质量。论文希望同一模型接受点云、图像或文本，并利用 CAD 执行结果继续优化重建策略。

### 3. 贡献

统一多模态 CAD 程序重建；在 SFT 后加入执行与几何反馈的强化学习；通过跨数据集结果验证 RL 是否改善几何和有效率。

### 4. 方法流程 / Pipeline

**训练第一阶段：** 多模态条件 + CAD 代码 → SFT。

**训练第二阶段：** 采样代码 → CAD 执行 → 依据有效性和目标几何计算奖励 → Dr. CPPO 更新生成策略。

**推断：** 点云、图像或文本条件 → 代码生成 → 执行出实体。评价时区分有无 RL、有无 test-time sampling；不能把推断时搜索的收益算作 SFT 的收益。

### 5. 实验

Table 1 比较无 RL、无 test-time sampling 的基础多模态模型；Tables 2–3 分别报告图像与点云任务，在 DeepCAD、Fusion360 和 CC3D 上测 CD ↓、IoU ↑、IR ↓。

Table 2 的图像重建：以 CAD-Recode 合成数据做 SFT、在 DeepCAD/Fusion360 上做 RL 后，CC3D 的 CD 表值由 0.81 降至 0.57，IR 从 7.7% 降至 0.1%，IoU 从 56.1% 升至 65.0%。它支持该设置下的跨数据集改善；对照同时增加了 RL 阶段的数据与训练，因此不是只替换一个 loss 的等预算实验。这里 CD 保留原表尺度，不跨论文比较。

### 6. 局限性

奖励受执行预算和几何度量影响；几何相近不保证程序语义或机械约束正确。操作覆盖仍依赖模型与训练数据，RL 无法自动补足所有 CAD 功能。样本难度和奖励分布也可能改变生成偏好，需同时观察失败率与几何质量（讲义分析）。

## 7. FlexCAD

**原文：** [官方论文与代码](https://github.com/microsoft/FlexCAD)，本地 ICLR 2025 PDF §3–4、Table 1 与消融实验。

### 1. 前置知识

CAD 的 sketch、loop、curve、extrusion 层次；文本序列化、masked completion、预训练 LLM 微调；分布质量与局部编辑控制的区别。

### 2. 动机

从零生成整个 CAD 模型不能满足“保留主体，仅改变一个草图或拉伸”的需求。论文希望用一个模型支持不同层级的可控补全和修改。

### 3. 贡献

将 CAD 层次结构表达为文本；设计 hierarchy-aware masking 与层级专用标记；微调 LLM 在 CAD、sketch-extrusion、face、loop、curve 等层级进行条件生成。

### 4. 方法流程 / Pipeline

**训练：** CAD 层次序列化 → 选定层级并遮盖子结构 → 保留上下文作为条件 → 学习生成遮盖内容。

**推断：** 用户指定待改部分 → 层级 mask → LLM 补全 → 合并未遮盖上下文 → 执行 CAD。它解决条件生成/编辑，主要输入并非一个待逆向的任意 Mesh。

### 5. 实验

Table 1：从 DeepCAD test 取 1,000 个模型，每个生成 10 个结果；分布指标用 3,000 个参考模型，报告三次运行平均。Sketch-level 的 Prediction Validity（PV）↑：FlexCAD 93.4%，Hnc-cad 72.6%；extrusion-level 分别为 93.3%、79.7%。PV 定义为能够渲染出三维形状的预测比例，不等同于 BrepGen 的水密内核有效率。

还报告 COV/MMD/JSD、Novel/Unique 和人工 Realism；随机 masking 与层级 token 消融检验层次表示作用。SkexGen 的部分任务会改变所有草图或拉伸，而本文指定一个子结构，原文承认比较任务存在差异。

### 6. 局限性

有效率和分布接近训练集，不足以证明某次局部修改满足尺寸、装配或制造约束。补全能力依赖层次表示和训练数据覆盖；需要额外验证修改后非目标结构的保持。此处是对实验指标能覆盖何种工程需求的讲义分析。

## 核心论文对照

| 方法 | 输入与输出 | 优化 / 监督 | 保留的结构 | 不能由该输出直接保证的内容 |
|---|---|---|---|---|
| SuperFit | 形状 → 解析基元软并装配 | 单形状几何优化 | 基元形状参数、装配 | 原始 CAD 操作与约束 |
| UCSG-Net | 形状 → CSG | 无真实树标签的 encoder 与可微重建 | 基元与布尔组合 | 任意复杂度、原始历史 |
| D²CSG | 形状 → 双分支 CSG | 单形状 latent/network 优化 | 补集、交并差结构 | 全局最短树与精确距离 |
| CADFit | 水密 Mesh → CAD 程序 | 几何搜索 + 学习型草图筛选 | 操作序列、参数及引用 | 原始设计意图和制造约束 |
| Zero-to-CAD | 描述 → 合成代码；多视图 → 代码模型 | 代理验证合成 + 监督微调 | 可重放源代码 | 完整 DFM、用户理解和编辑稳定性 |

本表综合前面各章，不以不同论文的同名 IoU 数字排名。

## 后续研究问题

这些是**讲义提出的研究问题，不是已经完成的实验，也不宣称具有未被研究过的新颖性**。

### A. 预测初始化是否能减少拟合成本？

在相同基元词表下，比较随机初始化、几何初始化、学习初始化，加同一优化器。固定目标集合、时间预算、硬件和最终离散导出。报告 IoU—基元数—时间曲线，并按薄结构、孔洞和曲率分层。若只换初始化却同时换词表，就无法归因。

### B. 好看的程序是否真的好改？

给定孔径、厚度等语义明确的参数，进行小范围扰动并重执行。报告成功率、目标尺寸变化、非目标区域变化、约束维持情况。对“未暴露该参数”的程序单列覆盖率，不能只挑最容易编辑的样本。

### C. 执行反馈是在改质量，还是只在删难例？

分别测无反馈、只过滤、推断时修复、训练时反馈四种策略。记录尝试总数、成功数、成功条件质量和失败记零质量；控制总生成或训练预算。否则“有效数据更多”可能只是消耗了更多重试而非更好的算法。

## 习题

1. AutoBrep 输出 token 序列，为什么仍不能说它恢复了 CAD 操作历史？
2. BrepGen 树里的重复边节点与 CSG 树里的重复基元是同一个问题吗？
3. 在数据引擎中修复程序，与用执行反馈做 RL 微调，分别在哪个阶段改变什么？
4. 设计一个能区分“可执行”与“可编辑”的最小测试，列出至少两个指标。

[答案与提示](exercises_and_answers.md)
