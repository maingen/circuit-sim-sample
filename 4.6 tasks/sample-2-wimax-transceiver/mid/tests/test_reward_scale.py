#!/usr/bin/env python3
from __future__ import annotations

from evaluator_core import criterion_score, relative_error


def close(left: float, right: float) -> None:
    assert abs(left - right) < 1e-12, (left, right)


for full, zero in ((0.25, 0.50), (0.05, 0.25), (0.01, 0.10)):
    close(criterion_score(0.0, full, zero), 1.0)
    close(criterion_score(full, full, zero), 1.0)
    close(criterion_score(zero, full, zero), 0.0)
    close(criterion_score((full + zero) / 2, full, zero), 0.5)
close(relative_error({"criterion_type": "central_fixed_point", "target": 10, "scale_floor": 1}, 12), 0.2)
close(relative_error({"criterion_type": "lower_is_better_fixed_point", "target": 10, "scale_floor": 1}, 8), 0.0)
close(relative_error({"criterion_type": "lower_is_better_fixed_point", "target": 10, "scale_floor": 1}, 12), 0.2)
close(relative_error({"criterion_type": "higher_is_better_fixed_point", "target": 10, "scale_floor": 1}, 12), 0.0)
close(relative_error({"criterion_type": "higher_is_better_fixed_point", "target": 10, "scale_floor": 1}, 8), 0.2)
close(relative_error({"criterion_type": "valid_range", "range": [5, 10], "scale_floor": 1}, 7), 0.0)
close(relative_error({"criterion_type": "valid_range", "range": [5, 10], "scale_floor": 1}, 4), 0.2)
close(relative_error({"criterion_type": "valid_range", "range": [5, 10], "scale_floor": 1}, 11), 0.2)
close(relative_error({"criterion_type": "central_fixed_point", "target": 0, "scale_floor": 0.1}, 0.01), 0.1)
print("reward scale tests passed")
