#!/usr/bin/env python3
from evaluator import criterion_reward

central = {"criterion_type":"central","target":10.0,"scale_floor":1.0}
lower = {"criterion_type":"lower","target":10.0,"scale_floor":1.0}
higher = {"criterion_type":"higher","target":10.0,"scale_floor":1.0}
valid_range = {"criterion_type":"range","lower":9.0,"upper":11.0,"scale_floor":1.0}
assert criterion_reward(central, 10.0, "hard")[0] == 1.0
assert criterion_reward(lower, 9.0, "hard")[0] == 1.0
assert criterion_reward(higher, 11.0, "hard")[0] == 1.0
assert criterion_reward(valid_range, 10.0, "hard")[0] == 1.0
print("reward scale PASS")
