from __future__ import annotations


def interval_overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return left[0] < right[1] and right[0] < left[1]


def event_confusion(
    predicted: list[tuple[int, int]], actual: list[tuple[int, int]]
) -> dict[str, int]:
    """Count one-to-one overlapping events without choosing a matching tolerance."""
    matched_actual: set[int] = set()
    true_positive = 0
    for candidate in predicted:
        for index, expected in enumerate(actual):
            if index not in matched_actual and interval_overlap(candidate, expected):
                matched_actual.add(index)
                true_positive += 1
                break
    return {
        "true_positive": true_positive,
        "false_positive": len(predicted) - true_positive,
        "false_negative": len(actual) - true_positive,
    }
