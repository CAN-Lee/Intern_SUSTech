# 03 · SuperFit：可编辑基元与残差拟合

[总目录](README.md) · [上一章](02_math_and_optimization.md) · [下一章](04_neural_csg.md)

**核心论文：** Ganeshan 等，*Residual Primitive Fitting of 3D Shapes with SuperFrusta*，Brown University / Adobe Research。[项目页](https://bardofcodes.github.io/superfit/) 标注 CVPR 2026；[arXiv v1](https://arxiv.org/abs/2512.09201v1) 发布于 2025-12。正文核对作者的 [低分辨率 PDF](https://bardofcodes.github.io/papers/superfit/paper_lowres.pdf)，细节核对 [补充材料](https://bardofcodes.github.io/papers/superfit/supp.pdf)。

## 学习目标

能解释为何“基元表达能力”和“分解策略”必须共同设计；理解 SuperFrustum 的八个形状参数、MSD 初始化、全装配重优化与剪枝；区分软并装配和规范 CSG 扩展。

## 1. 先把问题说准确

输入一个三维形状，输出一组可变换、可编辑的解析基元，其组合逼近输入。这里的“无监督”是没有真实部件分解或基元程序标签；目标形状的几何仍提供拟合信号。ResFit 是逐形状分析与优化，不是训练一个网络后一次前向输出所有结果。

正文 §3 Eqs. (1)–(2) 用以下形式表达目标：

$$
z^*=\arg\max_z O(S,z),\qquad
O(S,z)=R(S,E(z))-\alpha|z|.
$$

$R$ 表示重建质量，$|z|$ 是基元数量。不要把它与优化时的可微 surrogate loss 混为一谈。一个用于选择程序的离散评分，可以通过另一套更易优化的连续损失间接改善。

**教学例子：** 一把玩具椅有厚坐垫、细椅腿和弯曲靠背。仅增加球或盒子的数量可能降低表面误差，却得到互相穿插的碎片。先固定错误分割再拟合，同样会让本可由一个弯曲基元解释的靠背被切碎。

## 2. 先修：superquadric 不是一般二次曲面

以 superellipsoid 为例，一种常用隐式形式是：

$$
\left(\left|\frac{x}{a_1}\right|^{2/\epsilon_2}+
\left|\frac{y}{a_2}\right|^{2/\epsilon_2}\right)^{\epsilon_2/\epsilon_1}
+\left|\frac{z}{a_3}\right|^{2/\epsilon_1}=1,
\quad a_i,\epsilon_i>0.
$$

当 $\epsilon_1=\epsilon_2=1$ 时是椭球。改变指数可使轮廓更方或更尖；这为连续形状变形提供少量参数。此处作为读懂 SuperFit 的数学先修直接讲解，不另加早期论文阅读任务。

**讲义分析：** 这个隐式等式的左边减 1 一般不是欧氏 SDF。有限指数逼近立方体与精确表达立方体也不同。Superquadrics 是一个广泛家族，不应把本节的 superellipsoid 公式当作所有超二次曲面的定义，更不能与 D²CSG 的七系数 quadric 混淆。

## 3. SuperFrustum 的参数到底是什么？

正文 §3.2 Eq. (3) 写成 $\theta=(s,r,d,t,b,o)$。$s$ 是三维，所以共有八个标量，**不包含刚体位姿和装配混合参数**。

| 参数 | 维数 | 几何作用 | 直觉 |
|---|---:|---|---|
| $s=(s_x,s_y,s_z)$ | 3 | 三轴尺寸 | 拉长、变宽、变高 |
| $r$ | 1 | 截面圆角 | 方截面向圆截面过渡 |
| $d$ | 1 | 膨胀 | 改变外表面偏移 |
| $t$ | 1 | taper | 沿轴变细或变粗 |
| $b$ | 1 | bulge / 弯曲控制 | 形成弧状轴向变化 |
| $o$ | 1 | onion / hollowing | 控制壳状结构 |

补充材料使用 $c$ 表示正文的弯曲/bulge 控制。本章记为 $b$，引用补充公式时显式提醒这一差异。项目代码的 SuperGeon 等后续扩展不是本篇八参数定义的一部分，参见 [官方代码说明](https://github.com/BardOfCodes/superfit/blob/master/notes/primitives.md)。

### 3.1 从二维距离拼出三维形状

补充材料 §2 的构造可以按以下步骤理解：

$$
p^*=\operatorname{DomainCurve3D}(p;s_z,b),
$$

$$
u=\operatorname{RoundedRect2D}(p^*_{xy};s_x,s_y,r),
$$

$$
v=\operatorname{Trapezoid2D}((u,p^*_z);s_z,t,o),\qquad
f(p;\theta)=v-d.
$$

先把三维点映射到弯曲局部域，再计算它相对横截面的二维距离。接着把“横截面距离”和“轴向位置”组成新的二维坐标，在这个空间用梯形约束控制锥度与壳厚。最后加入膨胀。理解这个组合关系比直接记住展开后的长公式更重要。

### 3.2 推导一个可核验的组成块：圆角矩形

设二维半边长 $h=(h_x,h_y)$，$0\leq r\leq\min(h_x,h_y)$。先把矩形收缩到 $h-r$，再膨胀半径 $r$：

$$
q=|p_{xy}|-(h-r),\qquad
d_{\mathrm{rr}}(p)=\|\max(q,0)\|_2+
\min(\max(q_x,q_y),0)-r.
$$

这是由第 02 章盒子公式得到的**讲义推导**，对应补充材料 §2.1 的构造。例：$h=(2,1),r=0.25$，点 $(2,0)$ 在外侧直边上，代入后距离为 0。圆角改变角部而保持外包络尺寸。

### 3.3 梯形距离为什么涉及投影？

对边段 $[A,B]$，最近点由

$$
\eta=\operatorname{clip}\left(\frac{(p-A)\cdot(B-A)}{\|B-A\|^2},0,1\right),
\quad q=A+\eta(B-A)
$$

得到。到四条边的最小距离给绝对值，再通过半空间测试判断内外。**按本讲义内部负约定**，内部取负、外部取正。不要只复制公式而忽略符号：补充材料 §2.2 的符号判别叙述与最后的 `sign(-C)` 写法存在表面不一致，若 $C\leq0$ 被定义为内部，就应采用负的内部距离。这里以几何定义校验结果。

### 3.4 关键限制：采用的是近似距离场

补充材料开头把构造称为 exact SDF，但 §2.6 的 “On SDF accuracy and exact formulations” 明确说明实际采用的是近似距离场；更严格的精确方案计算昂贵，并不自然支持全部 onion/bending 操作。因此本讲义将最终场记作 $f$，不把所有参数设置下 $\|\nabla f\|=1$ 当成定理。

连续、几乎处处可微、数值上足以支持拟合，和数学上的精确距离是三个不同属性。第 02 章的组合反例正是读懂这一点的准备。

## 4. MSD：先找厚度结构，再初始化基元

正文 §3.3 Eqs. (5)–(6)，补充材料 §4 Algorithm 2。

对内部负的目标距离场 $d$，取负阈值 $\ell$：

$$
M_\ell=\{x:d(x)\leq\ell\},\qquad\ell<0.
$$

这相当于腐蚀：距离边界不够远的薄区域先消失，较厚区域留下。算法遍历腐蚀层级，寻找满足最小规模条件的连通区域，再向原边界膨胀，作为初始化区域。

**教学例子：** 玩具椅的细腿在深腐蚀时消失，厚坐垫留下。用恢复后的坐垫区域初始化基元，比随机把一个基元放到椅子包围盒中央更有结构信息。对于弯曲管状部件，厚度一致并不要求其凸；这使 MSD 与可弯曲基元更匹配。

需要注意三个实现含义：

- 一次 MSD 可给出多个合格连通区域，轮数不等于基元数。
- 减去已解释区域后，应重新距离化并清理细小残留；不能默认相减后的隐式值还是原来的精确距离。
- 初始化用区域点云的 PCA 坐标系，并评估候选轴的截面稳定性、圆度和细长度；之后这些参数仍会优化，不是永久锁定的分割。

## 5. ResFit：新基元加入后，旧基元也会动

![ResFit 流程](figures/resfit.svg)

以下是对正文 §3.1 和补充材料 Algorithm 1 的**教学伪代码**，省略了阈值及内部采样，不可直接当成复现实现：

```text
assembly = empty
best = empty
repeat within fitting budget:
    residual = target minus explained geometry
    regions = MSD(residual)
    if no valid regions: stop
    new_parts = initialize from regional geometry
    assembly = assembly + new_parts
    optimize ALL parts jointly with local-support losses
    prune parts whose removal improves reconstruction-complexity score
    retain best-scoring assembly
    stop when score saturates
return best
```

这里的 residual 是目标尚未解释的空间，不是“每个点的梯度值”。全装配重优化意味着早期坐垫基元可以在细腿加入后重新收缩，不必把早期错误永远固定。

## 6. 损失、软删除和硬剪枝

正文 §3.4 Eq. (8)：

$$
L=L_{\mathrm{rec}}+\lambda_{\mathrm{count}}L_{\mathrm{count}}
+\lambda_{\mathrm{qual}}L_{\mathrm{qual}}.
$$

重建部分使用体积和近表面信号，强调曲率较高的区域，并限制到当前装配相关的空间带。补充 §5 Eq. (12) 进一步区分均匀体积 occupancy、表面零值和表面邻域 occupancy 三类信号。应按补充细节理解正文较简洁的写法。

每个基元有随机存在变量 $q_i$，用 Gumbel-Softmax 松弛决定保留程度：

$$
f_i^*(p)=q_i f_i(p)+(1-q_i),\qquad
L_{\mathrm{count}}=\sum_iq_i.
$$

当 $q_i=0$，该基元场成为正的常数，不再表示内部区域；中间值会影响形状，不是单纯给渲染透明度赋权。质量项还抑制多基元重叠和过度平滑连接。连续阶段后，再实际尝试删除基元，仅保留对目标评分有益的删改。

**参数核验提醒：** 正文 implementation details 与补充材料部分损失权重叙述不同。讲义不提供拼接出的“统一复现配置”；复现时需选定代码提交、配置和论文版本。这里关注机制，不把某个权重数字当成跨版本默认值。

## 7. 软并装配不等于规范 CSG

主方法按正文 Eq. (4) 递归组合软并：

$$
F_{k+1}(p)=U(F_k(p),g_{k+1}(p);\beta_k).
$$

平滑接缝有利于有机形状，但也改变精确的集合运算语义。正文应用与补充 §6.1 另讨论规范 CSG 推断：使用专门的 solid primitive 变体，并将结果转为标准基元程序。不能因为论文展示了 CSG 应用，就把主方法写成任意深度 CSG 树学习。

## 8. 如何读实验而不夸大结论？

以下是正文 Table 1 的少量数据，均为**作者报告，未在本讲义复现**。IoU 表内使用百分制。

| 协议 | 方法 | IoU | 平均基元数 |
|---|---|---:|---:|
| 作者重建的 3DGen-Prim，510 prompts | MPS | 82.67 | 42.96 |
| 同上 | SuperFit | 88.74 | 23.98 |
| Toys4K，500 个多样性选取形状 | MPS | 80.60 | 30.62 |
| 同上 | SuperFit | 89.92 | 23.67 |

这些值支持在上述协议下改善重建—复杂度权衡。Toys4K 的基元数减少约 22.7%，并非减半；3DGen-Prim 约减少 44.2%。因此摘要中的“约一半”不应不加区分地套到每个数据集。正文使用 $128^3$ voxel IoU，表面指标采样 2048 点；不能与 CADFit 的实体布尔体积 IoU 直接拼榜。

正文 Table 2 比较基元与软并，Table 3 比较单次拟合与 ResFit、MSD 与 CoACD。精读时问：改善来自更强基元，还是更好的优化，还是二者结合？这比只看总表第一名更有研究价值。

## 9. 局限与阅读定位

补充 §8 展示薄曲面、多圈弯曲、非均匀厚度等失败场景。主方法没有任意减法树，孔洞密集的机械件可能需要很多基元。PCA/厚度分析也可能对噪声残差给出不理想的种子。渲染可实时不意味着拟合可实时，正文 timing 报告完整拟合需明显的逐形状计算时间。

推荐逐项核对：正文 Fig. 2 → Fig. 3 → §3.3 → §3.4 → Tables 1–3；补充 §2.6 的距离近似说明 → Algorithms 1–2 → §5 → §6.1 → §8。

## 10. 习题

1. 为什么八个形状参数不等于一个放置到世界坐标中的基元只有八个自由度？
2. 推导圆角矩形在点 $(h_x,0)$ 的距离，假设 $h_x,h_y>r$。
3. 将 ResFit 改成“旧基元冻结，只优化新基元”，最容易失去什么能力？
4. 把 $L_{\mathrm{count}}$ 权重设得非常大，结果会怎样？为什么质量项不能完全替代它？
5. 用 Table 1 算出两个数据集相对 MPS 的 IoU 提升和基元数降幅，并区分百分点与百分比。

[答案与提示](exercises_and_answers.md)
