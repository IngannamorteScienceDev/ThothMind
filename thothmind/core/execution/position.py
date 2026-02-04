from __future__ import annotations


class PositionManager:
    """
    Minimal position manager for Milestone 2.

    Rule:
    - position is just the target_exposure (0 / 0.5 / 1.0)
    - turnover = abs(position_t - position_{t-1})

    We keep it as a class because later we may implement:
    - partial fills
    - max daily position change
    - holding periods
    """

    def step(self, prev_position: float, target_exposure: float) -> dict:
        position = float(target_exposure)
        turnover = abs(position - float(prev_position))
        return {"position": position, "turnover": float(turnover)}
