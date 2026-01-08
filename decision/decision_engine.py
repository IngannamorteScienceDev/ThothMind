from dataclasses import dataclass
from typing import Optional


@dataclass
class DecisionResult:
    decision: str        # ENABLE / HOLD / DISABLE
    confidence: str      # HIGH / MEDIUM / LOW
    rationale: str


class DecisionEngine:
    """
    Final investment decision layer combining:
    - risk metrics
    - market regime
    - statistical significance (bootstrap)
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
        bootstrap_p_value: Optional[float]
    ) -> DecisionResult:

        reasons = []

        # Risk checks
        if sharpe < self.min_sharpe:
            reasons.append("Sharpe below minimum threshold")

        if max_drawdown < self.max_drawdown_limit:
            reasons.append("Excessive drawdown")

        # Regime awareness
        if "Bear-HighVol" in market_regime:
            reasons.append("Unfavorable market regime")

        # Statistical significance
        if bootstrap_p_value is None:
            reasons.append("No statistical significance test")
        elif bootstrap_p_value > self.significance_level:
            reasons.append(
                f"No significant outperformance (p={bootstrap_p_value:.3f})"
            )

        # Decision logic
        if len(reasons) == 0:
            return DecisionResult(
                decision="ENABLE",
                confidence="HIGH",
                rationale="Strategy passes risk, regime and significance criteria"
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
