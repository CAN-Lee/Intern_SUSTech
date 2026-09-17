# 可运行的基础算例

[讲义总目录](../README.md) · [数学章节](../02_math_and_optimization.md)

只需 Python 3 标准库，无需 CAD 内核、GPU 或网络。从项目根目录执行：

```bash
python3 lecture_notes/examples/math_checks.py
```

算例验证球与盒距离、圆角矩形、集合布尔的内外分类、组合场不等于精确距离、单向/双向 Chamfer、固定中心球拟合、软并偏移及失败记零指标。

其中贯穿孔是二维截面示例；它不计算完整三维 B-rep，不是 UCSG-Net 或 SuperFit 复现。运行不会写文件。
