from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CancellationDecision:
    allowed: bool
    refund: bool


class CancellationPolicy(Protocol):
    def decide(self, days_until_check_in: int) -> CancellationDecision: ...


class UnpaidCancellationPolicy:
    def decide(self, days_until_check_in: int) -> CancellationDecision:
        return CancellationDecision(allowed=days_until_check_in > 0, refund=False)


class PaidCancellationPolicy:
    def decide(self, days_until_check_in: int) -> CancellationDecision:
        return CancellationDecision(
            allowed=days_until_check_in > 0,
            refund=days_until_check_in >= 2,
        )
