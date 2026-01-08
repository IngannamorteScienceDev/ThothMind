from dataclasses import dataclass
from typing import Optional


@dataclass
class DecisionResult:
    decision: str          # ENABLE / HOLD / DISABLE
    confidence: str        # HIGH / MEDIUM / LOW
    rationale: str


class DecisionEngine:
    """
    Decision layer for investment approval.
    Translates metrics into an actionable decision.
    """

    def __init__(
        self,
        min_sharpe: float = 0.3,
        max_drawdown_limit: float = -0.30,
        significance_level: float = 0.10
    ):
        self.min_sharpe = min_sharpe
        self.max_drawdown_limit = max_drawdown_limit
        self.significance_level = significance_level

    def evaluate(
        self,
        expected_return: float,
        sharpe: float,
        max_drawdown: float,
        market_regime: str,
        bootstrap_p_value: Optional[float] = None
    ) -> DecisionResult:

        reasons = []

        # 1. Risk constraints
        if sharpe < self.min_sharpe:
            reasons.append("Sharpe below minimum threshold")

        if max_drawdown < self.max_drawdown_limit:
            reasons.append("Max drawdown exceeds risk limit")

        # 2. Regime-based caution
        if "Bear" in market_regime and "HighVol" in market_regime:
            reasons.append("Unfavorable market regime (Bear-HighVol)")

        # 3. Statistical significance (optional)
        if bootstrap_p_value is not None:
            if bootstrap_p_value > self.significance_level:
                reasons.append("No statistically significant outperformance")

        # ---- Final decision logic ----
        if len(reasons) == 0:
            return DecisionResult(
                decision="ENABLE",
                confidence="HIGH",
                rationale="All risk, regime, and performance criteria satisfied"
            )

        if len(reasons) <= 2:
            return DecisionResult(
                decision="HOLD",
                confidence="MEDIUM",
                rationale=" | ".join(reasons)
            )

        return DecisionResult(
            decision="DISABLE",
            confidence="LOW",
            rationale=" | ".join(reasons)
        )
