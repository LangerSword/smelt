"""Count strict interior local maxima; fewer than 3 values -> 0."""


def count_peaks(vals: list[int]) -> int:
    count = 0
    for i in range(1, len(vals) - 1):
        if vals[i] > vals[i - 1] and vals[i] > vals[i + 1]:
            count += 1
    return count
