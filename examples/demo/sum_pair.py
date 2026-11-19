def sum_pair(xs: list[int]) -> tuple[int, int]:
    total = 0
    squares = 0
    for x in xs:
        total += x
        squares += x * x
    return (total, squares)
