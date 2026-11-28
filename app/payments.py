from abc import ABC, abstractmethod
from decimal import Decimal
from enum import StrEnum
from typing import Protocol


class DemoPaymentOutcome(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class PaymentGateway(Protocol):
    def charge(self, outcome: DemoPaymentOutcome) -> bool: ...

    def refund(self, amount: Decimal) -> Decimal: ...


class DemoPaymentSimulator:
    def settle(self, approved: bool) -> bool:
        return approved

    def reverse(self, minor_units: int) -> int:
        return minor_units


class DemoPaymentAdapter:
    def __init__(self, simulator: DemoPaymentSimulator):
        self.simulator = simulator

    def charge(self, outcome: DemoPaymentOutcome) -> bool:
        return self.simulator.settle(approved=outcome == DemoPaymentOutcome.SUCCEEDED)

    def refund(self, amount: Decimal) -> Decimal:
        return Decimal(self.simulator.reverse(int(amount.scaleb(2)))).scaleb(-2)


class PaymentGatewayFactory(ABC):
    @abstractmethod
    def create_gateway(self) -> PaymentGateway:
        raise NotImplementedError


class DemoPaymentGatewayFactory(PaymentGatewayFactory):
    def create_gateway(self) -> PaymentGateway:
        return DemoPaymentAdapter(DemoPaymentSimulator())
