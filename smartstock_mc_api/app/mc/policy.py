import math
from typing import Optional

def apply_rounding(qty: float, moq: int, multiplo: int, q_cap: Optional[int]) -> float:
    q = max(0.0, float(qty or 0.0))
    moq = int(moq or 1)
    multiplo = int(multiplo or 1)

    if moq < 1:
        moq = 1
    if multiplo < 1:
        multiplo = 1

    if q <= 0:
        return 0.0

    q = max(q, float(moq))
    q = math.ceil(q / multiplo) * multiplo

    if q_cap is not None:
        cap = int(q_cap)
        if cap > 0:
            q = min(q, float(cap))

    return float(q)
