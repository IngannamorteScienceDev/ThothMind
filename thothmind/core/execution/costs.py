from __future__ import annotations


def compute_costs(
    turnover: float,
    realized_vol: float,
    commission_bps: float,
    slippage_k: float,
) -> dict:
    """
    Turnover-aware transaction costs.

    commission_cost = commission_bps/10000 * turnover
    slippage_cost   = slippage_k * realized_vol * turnover
    """
    commission_cost = (commission_bps / 10_000.0) * float(turnover)
    slippage_cost = float(slippage_k) * float(realized_vol) * float(turnover)
    total_cost = commission_cost + slippage_cost

    return {
        "commission_cost": float(commission_cost),
        "slippage_cost": float(slippage_cost),
        "total_cost": float(total_cost),
    }
