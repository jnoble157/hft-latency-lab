from typing import Dict, Optional

class SimpleBook:
    """
    A minimal Limit Order Book for the Reflex Lane.
    Optimized for speed.
    """
    def __init__(self):
        self.bids: Dict[int, int] = {}
        self.asks: Dict[int, int] = {}
        self.best_bid: Optional[int] = None
        self.best_ask: Optional[int] = None

    def load_snapshot(self, asks: list, bids: list):
        """
        Load initial state.
        """
        self.asks = {p: q for p, q in asks}
        self.bids = {p: q for p, q in bids}
        self._recalc_max_bid()
        self._recalc_min_ask()

    def apply_update(self, side: int, price: int, qty: int, action: int):
        """
        Update the book.
        side: 0=Bid, 1=Ask
        action: 1=Add, 2=Modify, 3=Delete/Reduce
        """
        book = self.bids if side == 0 else self.asks
        is_bid = (side == 0)
        
        if action == 1: # ADD
            if price in book:
                book[price] += qty
            else:
                book[price] = qty
                # Optimization: Only check if this improves BBO
                if is_bid:
                    if self.best_bid is None or price > self.best_bid:
                        self.best_bid = price
                else:
                    if self.best_ask is None or price < self.best_ask:
                        self.best_ask = price

        elif action == 2: # MODIFY (Set Quantity)
             # In our protocol '2' usually means explicit set or modify
             if qty > 0:
                 book[price] = qty
                 # If we modified a price that wasn't there? (Shouldn't happen)
                 if is_bid:
                     if self.best_bid is None or price > self.best_bid: self.best_bid = price
                 else:
                     if self.best_ask is None or price < self.best_ask: self.best_ask = price
             else:
                 # Treat 0 qty update as delete
                 self._remove_order(book, price, is_bid)

        elif action == 3: # REDUCE / DELETE
            if price in book:
                book[price] -= qty
                if book[price] <= 0:
                    self._remove_order(book, price, is_bid)

    def _remove_order(self, book, price, is_bid):
        del book[price]
        # Expensive Case: We deleted the BBO, must scan for next best
        if is_bid:
            if price == self.best_bid:
                self._recalc_max_bid()
        else:
            if price == self.best_ask:
                self._recalc_min_ask()

    def _recalc_max_bid(self):
        if not self.bids:
            self.best_bid = None
        else:
            self.best_bid = max(self.bids.keys())

    def _recalc_min_ask(self):
        if not self.asks:
            self.best_ask = None
        else:
            self.best_ask = min(self.asks.keys())

    def get_spread(self) -> Optional[int]:
        if self.best_bid is None or self.best_ask is None:
            return None
        return self.best_ask - self.best_bid

    def is_crossed(self) -> bool:
        if self.best_bid is None or self.best_ask is None:
            return False
        return self.best_bid >= self.best_ask
