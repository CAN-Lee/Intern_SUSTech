"""Independent numeric teaching checks; standard library only, no file writes."""
from math import exp, hypot, isclose, log, sqrt
from itertools import product


def norm(v):
    return sqrt(sum(x * x for x in v))


def sphere_sdf(p, radius):
    return norm(p) - radius


def box_sdf(p, half_sizes):
    q = [abs(x) - b for x, b in zip(p, half_sizes)]
    return norm([max(v, 0.0) for v in q]) + min(max(q), 0.0)


def rounded_rectangle_sdf(p, half_sizes, radius):
    if not 0 <= radius <= min(half_sizes):
        raise ValueError("Corner radius must fit inside the half sizes")
    return box_sdf(p, [b - radius for b in half_sizes]) - radius


def soft_min(a, b, temperature):
    if temperature <= 0:
        raise ValueError("Temperature must be positive")
    m = min(a, b)
    return m - temperature * log(exp(-(a - m) / temperature)
                                + exp(-(b - m) / temperature))


def directed_cd_squared(points, target):
    return sum(min(sum((a - b) ** 2 for a, b in zip(p, q))
                   for q in target) for p in points) / len(points)


def main():
    assert isclose(sphere_sdf((3, 0, 0), 2), 1)
    assert isclose(box_sdf((0, 0, 0), (2, 1, 1)), -1)
    assert isclose(box_sdf((3, 2, 1), (2, 1, 1)), sqrt(2))
    assert isclose(rounded_rectangle_sdf((2, 0), (2, 1), .25), 0)
    assert isclose(rounded_rectangle_sdf((2, 1), (2, 1), .25),
                   .25 * (sqrt(2) - 1))
    print("球、盒、圆角矩形的已知距离：通过")

    # Off-boundary queries: independently compare algebraic sets and field signs.
    for p in product((-.83, -.37, .13, .71, 1.23), repeat=2):
        in_a = abs(p[0]) <= 1 and abs(p[1]) <= .8
        in_b = p[0] ** 2 + p[1] ** 2 <= .5 ** 2
        a, b = box_sdf(p, (1, .8)), sphere_sdf(p, .5)
        assert (min(a, b) <= 0) == (in_a or in_b)
        assert (max(a, b) <= 0) == (in_a and in_b)
        assert (max(a, -b) <= 0) == (in_a and not in_b)
    print("25 个离边界查询点的并、交、差内外判定：通过")

    assert max(1, 1) != hypot(1, 1)
    assert max(2, 1) != hypot(2, 1)
    print(f"交集反例：组合场 = 1，真实距离 = {sqrt(2):.6f}")

    x, y = [(0, 0, 0)], [(0, 0, 0), (2, 0, 0)]
    xy, yx = directed_cd_squared(x, y), directed_cd_squared(y, x)
    assert xy == 0 and yx == 2
    print(f"单向平方 CD = {xy:g}，双向平方 CD 和 = {xy + yx:g}")

    distances = [1.9, 2.0, 2.1]
    fitted_radius = sum(distances) / len(distances)
    loss = lambda r: sum((d - r) ** 2 for d in distances) / len(distances)
    assert isclose(fitted_radius, 2)
    assert loss(2) < loss(1.99) and loss(2) < loss(2.01)
    print("固定中心球拟合半径 = 2：通过")

    t = .1
    assert isclose(soft_min(0, 0, t), -t * log(2))
    for a, b in ((-2, 3), (1, 1), (.1, -.2)):
        value = soft_min(a, b, t)
        assert min(a, b) - t * log(2) - 1e-12 <= value <= min(a, b) + 1e-12
    print(f"相同场软并的偏移 = {t * log(2):.6f}")

    assert isclose(.5 * .9, .45) and isclose(.9 * .6, .54)
    print(f"Zero-to-CAD ABC 汇总近似，失败记零：{.610 * .377:.6f} vs {.662 * .344:.6f}")
    print("全部基础算例通过；未运行任何论文复现。")


if __name__ == "__main__":
    main()
