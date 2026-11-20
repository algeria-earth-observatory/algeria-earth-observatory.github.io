"""Write tests/fixtures/trend_cases.json: SYNTHETIC series + Python trend results.

The JS implementation (src/lib/trend.js) must reproduce these numbers
(tests/js/trend.test.mjs). Synthetic data, never published as observations.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "pipelines"))
from aeo.stats import mann_kendall, theil_sen  # noqa: E402

rng = np.random.default_rng(2026)
cases = []
for k in range(40):
    n = int(rng.integers(8, 60))
    kind = k % 4
    t = np.arange(n, dtype=float)
    if kind == 0:
        y = rng.normal(300, 60, n)                       # white noise
    elif kind == 1:
        y = 200 + 2.5 * t + rng.normal(0, 30, n)          # trend
    elif kind == 2:
        e = np.zeros(n)
        for i in range(1, n):
            e[i] = 0.7 * e[i - 1] + rng.normal(0, 20)     # AR(1)
        y = 250 + e
    else:
        y = np.round(rng.normal(50, 10, n))              # ties
    y = [None if (k % 5 == 0 and i in (2, 5)) else round(float(v), 3) for i, v in enumerate(y)]
    arr = np.array([np.nan if v is None else v for v in y])
    ts = theil_sen(arr)
    mk = mann_kendall(arr)
    cases.append({"y": y, "theil_sen": ts, "mann_kendall": {k2: mk[k2] for k2 in ("n", "s", "tau", "z", "p", "r1", "corrected")}})
(ROOT / "tests" / "fixtures" / "trend_cases.json").write_text(json.dumps(cases, indent=0))
print(len(cases), "cases")
