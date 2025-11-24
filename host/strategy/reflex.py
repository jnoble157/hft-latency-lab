from enum import Enum
from .book import SimpleBook

class ReflexAction(Enum):
    NONE = 0
    CANCEL_ALL = 1    # Panic button
    TAKE_LIQUIDITY = 2 # Arb opportunity
    WIDEN_SPREADS = 3 # High volatility/uncertainty

class ReflexEngine:
    """
    CPU-side rule engine.
    Run this immediately after sending the packet to FPGA.
    """
    def __init__(self):
        self.packet_count = 0
        self.panic_threshold_ticks = 500 # Example: if price moves 500 ticks
        self.max_inventory = 100
        self.inventory = 0

    def evaluate(self, book: SimpleBook, update_price: int, update_side: int) -> ReflexAction:
        """
        Check hard-coded rules against the current book state.
        """
        self.packet_count += 1

        # Rule 1: Crossed Book (Arbitrage / Error)
        if book.is_crossed():
            # In production, you'd check if you can take the other side
            return ReflexAction.TAKE_LIQUIDITY

        # Rule 2: Spread blow-out (Risk management)
        spread = book.get_spread()
        if spread and spread > 1000:
             return ReflexAction.WIDEN_SPREADS

        # Rule 3: Inventory Limits (not fully implemented in this mock)
        if abs(self.inventory) > self.max_inventory:
            return ReflexAction.CANCEL_ALL

        # Default
        return ReflexAction.NONE

