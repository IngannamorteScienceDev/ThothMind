from dataclasses import dataclass


@dataclass
class AllocationResult:
    allocation: float       # 0.0 / 0.5 / 1.0
    rationale: str


class AllocationEngine:
    """
    Capital allocation policy based on final investment decision.
    """

    def allocate(self, decision: str) -> AllocationResult:

        if decision == "ENABLE":
            return AllocationResult(
                allocation=1.0,
                rationale="Full allocation: strategy statistically validated"
            )

        if decision == "HOLD":
            return AllocationResult(
                allocation=0.5,
                rationale="Partial allocation: uncertain advantage"
            )

        return AllocationResult(
            allocation=0.0,
            rationale="No allocation: strategy disabled"
        )
