"""Unicode sparklines for trend series; missing points render as a gap."""

from __future__ import annotations

_BLOCKS = "▁▂▃▄▅▆▇█"
_GAP = "·"


def sparkline(series: list[float | None]) -> str:
    present = [v for v in series if v is not None]
    if not present:
        return _GAP * len(series)
    lo, hi = min(present), max(present)
    span = hi - lo
    chars: list[str] = []
    for value in series:
        if value is None:
            chars.append(_GAP)
        elif span == 0:
            chars.append(_BLOCKS[3])
        else:
            index = int((value - lo) / span * (len(_BLOCKS) - 1))
            chars.append(_BLOCKS[index])
    return "".join(chars)
