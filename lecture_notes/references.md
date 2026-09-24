# 参考资料、版本与阅读定位

[总目录](README.md)

论文正文与实验摘录更新日期：**2026-09-23**；原有网页核验日期为 **2026-09-17**。五篇核心论文按六部分精读，七篇扩展论文按相同结构简述；方法与表格摘录以本地 PDF 为依据。发表年份与预印本首发年份分开记录。未把商业博客、搜索摘要或评审中的稿件当成正式同行评审结论。

## A. 截图中指定的资料

### A1 · nTop 入门文章

Blake Courter. **B-rep vs. implicit modeling: Understanding the basics.** nTop 技术博客，2019-03-12。[原始页面](https://www.ntop.com/resources/blog/understanding-the-basics-of-b-reps-and-implicits/)

对应第 01 章。已读取正文；建议依次看 Precise B-reps、Meshes、Distance fields、Implicits versus distance fields。年份虽较早，但它是截图明确指定的基础材料，不是额外增加的旧论文。关于性能规模与可靠性的描述带有工业场景和产品背景。

### A2 · 隐式建模与 SDF 入门文章

nergiveup. **隐式建模与SDF [1]：技术原理、布尔运算与应用实践。** CSDN 技术博客，2026-07-13。[原始文章](https://blog.csdn.net/nergiveup/article/details/162848403)

2026-09-17 重试时通过直接下载 HTML 成功读取正文；网页阅读工具仍报错，不能据此判断原网页不可访问。建议在 nTop 之后、第 02 章之前阅读 §2–3，理解基础定义与布尔运算，再把 §4 作为 GLSL 示意代码参考。这是用户指定的入门博客，不是同行评审论文。

**阅读校正：** §2.2 的盒子公式仅保留外部距离项，内部处处为零；§4.1 的 `sdBox` 代码补上了内部项，与讲义第 02 章一致。平面公式要求单位法向量；§3.1 的指数平滑参数与 §4.1 的多项式平滑参数虽都记为 k，含义和尺度不同。§4.4 是简化框架，不能把任意近似隐式值都视为安全步长。基础公式仍以本讲义的推导和算例为准，不直接照搬博客中的概括。

### A3 · SuperFit

[本地 PDF](<../papers/SuperFit (arXiv 2512.09201v1).pdf>) · 本次新增核对：正文 Tables 1–3、§4.2 timing。补充材料的既有解读保留其独立来源，不把 arXiv 正文当作包含补充全文。

Aditya Ganeshan, Matheus Gadelha, Thibault Groueix, Zhiqin Chen, Siddhartha Chaudhuri, Vladimir Kim, Wang Yifan, Daniel Ritchie. **Residual Primitive Fitting of 3D Shapes with SuperFrusta.** Brown University / Adobe Research。arXiv:2512.09201v1，2025-12-09；作者项目页标注 CVPR 2026 oral。

- [截图原始 PDF](https://bardofcodes.github.io/papers/superfit/paper.pdf)
- [同作者低分辨率正文](https://bardofcodes.github.io/papers/superfit/paper_lowres.pdf)
- [补充材料](https://bardofcodes.github.io/papers/superfit/supp.pdf)
- [项目页](https://bardofcodes.github.io/superfit/) · [arXiv 固定版本](https://arxiv.org/abs/2512.09201v1) · [官方代码](https://github.com/BardOfCodes/superfit)

本次读取低分辨率正文与关键补充材料章节。定位：正文 §3.1–3.4、Eqs. (1)–(8)、Tables 1–3；补充 §2.6、Algorithms 1–2、§5、§6.1、§8。主表已结合 PDF 页面视觉核验。低分辨率指图像压缩，不是另一套实验。

版本/解释注意：正文八参数 bulge 记 $b$，补充记 $c$；补充 §2.6 明确最终场是近似 SDF；部分损失权重与符号叙述有不一致。讲义明确标注，不合成为虚构的统一复现参数。最新代码扩展不自动视为论文原始方法。

### A4 · UCSG-Net

[本地 PDF](<../papers/UCSG-Net (NeurIPS 2020).pdf>) · 本次新增核对：§4.1–4.2、Tables 1–2；二维与三维 CD 分开报告，三维结果不概括为全部基线最优。

Kacper Kania, Maciej Zięba, Tomasz Kajdanowicz. **UCSG-Net — Unsupervised Discovering of Constructive Solid Geometry Tree.** NeurIPS 2020。Wrocław University of Science and Technology / Tooploox。arXiv:2006.09102。

[arXiv](https://arxiv.org/abs/2006.09102) · [会议正文](https://proceedings.neurips.cc/paper/2020/file/63d5fb54a858dd033fe90e6e4a74b0f0-Paper.pdf) · [官方实现](https://github.com/kacperkan/ucsgnet)

本次读取论文正文；对应第 04 章前半。核心位置 §2.1–2.2、Eqs. (1)–(12)、Figs. 1–3。由截图指定而保留，不延伸成早期 CSG 文献史。

### A5 · D²CSG

[本地 PDF](<../papers/D2CSG (arXiv 2301.11497v2).pdf>) · 本次新增核对：Tables 2–3 的主结果与 CP/DB/DO 消融；CD/ECD 表值乘 1,000，NC 无此缩放。

Fenggen Yu, Qimin Chen, Maham Tanveer, Ali Mahdavi Amiri, Hao Zhang. **D²CSG: Unsupervised Learning of Compact CSG Trees with Dual Complements and Dropouts.** NeurIPS 2023。会议版机构包括 Simon Fraser University / Amazon；arXiv v2 的页头机构与会议版有差别，勿据此统一改写所有版本。

[正式会议入口](https://proceedings.neurips.cc/paper_files/paper/2023/hash/4732d425125832887f6c5a9675d49ead-Abstract-Conference.html) · [arXiv v2](https://arxiv.org/abs/2301.11497v2) · [正文 HTML](https://arxiv.org/html/2301.11497v2)

本次读取 HTML 正文，核心位置 §3.1–3.3、Eqs. (1)–(7)、Table 1 和 §4–5。讲义的 DNF 推导是教学解释，不声称重新完成了补充材料中的全部定理证明。本地 v2 PDF 已可用；本次另核对 Tables 2–4、§4 的采样、指标缩放和逐形状优化成本。

### A6 · CADFit

[本地 PDF](<../papers/CADFit (arXiv 2605.01171v3).pdf>) · 本次新增核对：Tables 3–4 的程序长度和 learned sketch prior 消融，以及 Appendix B 的指标口径。

Ghadi Nehme, Eamon Whalen, Faez Ahmed. **CADFit: Precise Mesh-to-CAD Program Generation with Hybrid Optimization.** arXiv:2605.01171，2026；本章锁定 **v3，2026-06-07**，记为预印本。

[截图链接](https://arxiv.org/abs/2605.01171) · [固定版本](https://arxiv.org/abs/2605.01171v3) · [正文与附录](https://arxiv.org/html/2605.01171v3)

本次读取 PDF 正文与相关附录。定位：§3、Eq. (1)、Algorithm 1、Tables 1–2；Appendix B（指标）、F（失败）、I–N（草图、候选、组装、prior、圆角倒角）。不要把候选生成的平方单向 CD 与最终评价的非平方双向 CD 混淆。

### A7 · Zero-to-CAD

[本地 PDF](<../papers/Zero-to-CAD (arXiv 2604.24479v1).pdf>) · 本次新增核对：Tables 2–4 与 §6。下游训练使用 979,633 个训练样本，不将 100,000 精选集误写为其全部训练数据。

Mohammadmehdi Ataei, Farzaneh Askari, Kamal Rahimi Malekshan, Pradeep Kumar Jayaraman. **Zero-to-CAD: Agentic Synthesis of Interpretable CAD Programs at Million-Scale Without Real Data.** Autodesk Research。arXiv:2604.24479v1，2026-04-27；记为预印本。

[固定版本](https://arxiv.org/abs/2604.24479v1) · [正文](https://arxiv.org/html/2604.24479v1) · [官方模型卡与数据链接](https://huggingface.co/ADSKAILab/Zero-To-CAD-Qwen3-VL-2B)

本次读取 PDF 正文，定位：§4.1–4.6、§6.1–6.2、Tables 2/4、Appendix D/E。Table 4 明确几何指标只统计成功样本；GPT 与 Qwen 的 ID 测试样本数不同。数据发布状态依据官方模型卡核验，不沿用较早匿名评审稿的“将来发布”表述。

## B. 七篇近期扩展阅读

### B1 · PrimitiveAnything（2025）

[本地 PDF](<../papers/PrimitiveAnything (arXiv 2505.04622).pdf>) · 本次阅读 §3–4、Tables 1–5，摘录 Table 2 的 RI/SC；几何 Voxel-IoU 为点云体素化协议。

Jingwen Ye, Yuze He, Yanning Zhou, Yiqin Zhu, Kaiwen Xiao, Yong-Jin Liu, Wei Yang, Xiao Han. **PrimitiveAnything: Human-Crafted 3D Primitive Assembly Generation with Auto-Regressive Transformer.** SIGGRAPH 2025；腾讯 AIPD / 清华大学。arXiv:2505.04622。

[项目与方法概览](https://primitiveanything.github.io/) · [论文入口](https://arxiv.org/abs/2505.04622)

用途：接在 SuperFit 后，比较人类装配监督与逐形状拟合。核验项目方法图说明和发表信息，未在讲义复现其指标。

### B2 · BrepGen（2024）

[本地 PDF](<../papers/BrepGen (TOG 2024).pdf>) · 本次阅读 §4–6，摘录 Table 1 的 COV/Valid；Novel/Unique 只对有效结果计算。

Xiang Xu, Joseph G. Lambourne, Pradeep Kumar Jayaraman, Zhengqing Wang, Karl D. D. Willis, Yasutaka Furukawa. **BrepGen: A B-rep Generative Diffusion Model with Structured Latent Geometry.** ACM Transactions on Graphics 43(4), 2024；Autodesk Research / Simon Fraser University。

[Autodesk 原始发布页](https://www.research.autodesk.com/publications/brepgen/) · [机构托管论文](https://damassets.autodesk.net/content/dam/autodesk/www/pdfs/brepgen.pdf)

用途：理解层次潜几何、重复节点和拓扑合并。先看整体表示图，再读几何/拓扑编码，暂不追求所有 diffusion 训练细节。

### B3 · AutoBrep（2025）

[本地 PDF](<../papers/AutoBrep (arXiv 2512.03018).pdf>) · 本次阅读 §4–7、Table 1；记录 ABC-1M 划分、BFT 与局部引用消融，不将其 BrepGen 重训练基线与旧论文混用。

Xiang Xu, Pradeep Kumar Jayaraman, Joseph G. Lambourne, Yilin Liu, Durvesh Malpure, Pete Meltzer. **AutoBrep: Autoregressive B-Rep Generation with Unified Topology and Geometry.** SIGGRAPH Asia 2025；Autodesk Research 相关团队。arXiv:2512.03018。

[机构发布页](https://www.research.autodesk.com/publications/auto-brep-generation-unified-topology-geometry/) · [论文入口](https://arxiv.org/abs/2512.03018) · [官方代码及会议标注](https://github.com/AutodeskAILab/AutoBrep)

用途：理解几何 token 与拓扑引用，比较面邻接图遍历和真实建模历史的区别。已核对官方表示说明，并阅读论文 §4–5 的公开摘取内容。

### B4 · BrepARG（2026）

[本地 PDF](<../papers/BrepARG (CVPR 2026).pdf>) · 本次阅读 §3–5、Tables 1–3；摘录 DeepCAD 的 COV/Valid 和 top-p 取舍。

Jiahao Li, Yunpeng Bai, Yongkang Dai, Hao Guo, Hongping Gan, Yilei Shi. **AutoRegressive Generation with B-rep Holistic Token Sequence Representation.** CVPR 2026；arXiv:2601.16771。

[论文入口](https://arxiv.org/abs/2601.16771) · [CVPR 正式 PDF](https://openaccess.thecvf.com/content/CVPR2026/papers/Li_AutoRegressive_Generation_with_B-rep_Holistic_Token_Sequence_Representation_CVPR_2026_paper.pdf)

用途：与 AutoBrep 对照整体序列和面索引编码；讲义按六部分简述，并给出原文 Table 1/3 的代表性结果；不据此作跨论文排名。

### B5 · CAD-Recode（2025，预印本 2024）

[本地 PDF](<../papers/CAD-Recode (arXiv 2412.14042).pdf>) · 本次阅读 §3–5、Tables 1–4；摘录 CC3D IoU/IR，注明 10 候选 test-time sampling。

Danila Rukhovich, Elona Dupont, Dimitrios Mallis, Kseniya Cherenkova, Anis Kacem, Djamila Aouada. **CAD-Recode: Reverse Engineering CAD Code from Point Clouds.** ICCV 2025；University of Luxembourg 团队。arXiv:2412.14042。

[官方代码与发布信息](https://github.com/filaPro/cad-recode) · [论文入口](https://arxiv.org/abs/2412.14042)

用途：理解点云到代码、合成 sketch-extrude 监督与 CADFit/Zero-to-CAD 的关系。代码有不同模型版本，选择基线时必须锁定。

### B6 · cadrille（2026，预印本 2025）

[本地 PDF](<../papers/cadrille (arXiv 2505.22914v3).pdf>) · 本次阅读 v3 的方法与 Tables 1–3，摘录 Table 2 的 CC3D 图像重建结果；同时记录 RL 额外数据与训练的影响。

Maksim Kolodiazhnyi, Denis Tarasov, Dmitrii Zhemchuzhnikov, Alexander Nikulin, Ilya Zisman, Anna Vorontsova, Anton Konushin, Vladislav Kurenkov, Danila Rukhovich. **cadrille: Multi-modal CAD Reconstruction with Reinforcement Learning.** ICLR 2026 oral；arXiv:2505.22914v3，2026-02-17。

[v3 与会议标注](https://arxiv.org/abs/2505.22914v3) · [正式评审平台 PDF](https://openreview.net/pdf?id=w2tnhhMbXv)

用途：理解 SFT 后的在线执行反馈，与 Zero-to-CAD 的推断时数据修复区分。早期版本题名中有 Online，讲义采用最新版名称。

### B7 · FlexCAD（2025）

[本地 PDF](<../papers/FlexCAD (ICLR 2025).pdf>) · 本次阅读方法、Table 1 与 masking 消融；PV 指可渲染三维输出比例，不视为严格水密内核检查。

Zhanwei Zhang, Shizhao Sun, Wenxiao Wang, Deng Cai, Jiang Bian. **FlexCAD: Unified and Versatile Controllable CAD Generation with Fine-tuned Large Language Models.** ICLR 2025。

[微软研究原始发布页](https://www.microsoft.com/en-us/research/publication/flexcad-unified-and-versatile-controllable-cad-generation-with-fine-tuned-large-language-models/) · [官方代码](https://github.com/microsoft/FlexCAD)

用途：从“生成整个对象”转向“按层级编辑局部”。阅读 hierarchy-aware masking 的定义，再思考编辑后不应变化的区域如何评价。

## C. 基础工具资料与来源边界

- [sdfCAD](https://gitlab.com/nobodyinperson/sdfcad)：Yann Büchau 的 Python 项目，官方简介为基于 SDF 生成三维网格。对应第 01 章 §4，可作为 SDF 到网格的实践入口。2026-09-17 核对项目主页简介；未运行代码，不据此宣称支持解析 B-rep 或参数化建模历史的恢复。
- [Open CASCADE Modeling Data](https://dev.opencascade.org/doc/overview/html/occt_user_guides__modeling_data.html)：核对几何、拓扑、边界组织；本次网页跳转到现行 OCCT 文档。
- [Inigo Quilez distance functions](https://iquilezles.org/articles/distfunctions/)：解析距离公式的作者资料入口；本次自动网页读取未成功，不据此引出未经核验的额外结论。讲义中的球、盒、圆角矩形公式已独立推导并由算例验证。

图示为讲义原创示意图，不是论文图片的重排。伪代码标注为教学概括，不是官方实现。所有实验数字均明确来自作者的指定表格；没有声称进行 GPU 实验、代码复现或统计显著性检验。
