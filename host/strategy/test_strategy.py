import unittest
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from host.strategy.book import SimpleBook
from host.strategy.reflex import ReflexEngine, ReflexAction
from host.strategy.arbiter import Arbiter, Decision

class TestStrategy(unittest.TestCase):
    def test_book_crossing(self):
        book = SimpleBook()
        # Add Ask at 100
        book.apply_update(1, 100, 10, 1)
        self.assertFalse(book.is_crossed())
        
        # Add Bid at 99
        book.apply_update(0, 99, 10, 1)
        self.assertFalse(book.is_crossed())
        
        # Add Bid at 101 (Cross!)
        book.apply_update(0, 101, 10, 1)
        self.assertTrue(book.is_crossed())
        
    def test_reflex_panic(self):
        reflex = ReflexEngine()
        book = SimpleBook()
        
        # Normal state
        book.apply_update(1, 1000, 10, 1) # Ask 1000
        book.apply_update(0, 990, 10, 1)  # Bid 990
        
        action = reflex.evaluate(book, 990, 0)
        self.assertEqual(action, ReflexAction.NONE)
        
        # Cross the book
        book.apply_update(0, 1001, 10, 1) # Bid 1001
        action = reflex.evaluate(book, 1001, 0)
        self.assertEqual(action, ReflexAction.TAKE_LIQUIDITY)

    def test_arbiter_logic(self):
        arb = Arbiter()
        
        # Case 1: Reflex says CANCEL -> Arbiter must CANCEL
        d = arb.decide(ReflexAction.CANCEL_ALL, 999.0, {})
        self.assertEqual(d, Decision.CANCEL)
        
        # Case 2: Reflex Neutral, FPGA High Score -> BUY
        d = arb.decide(ReflexAction.NONE, 250.0, {}) # Threshold is 200
        self.assertEqual(d, Decision.BUY)
        
        # Case 3: Reflex Neutral, FPGA Low Score -> SELL
        d = arb.decide(ReflexAction.NONE, -250.0, {})
        self.assertEqual(d, Decision.SELL)
        
        # Case 4: Reflex Neutral, FPGA Noise -> HOLD
        d = arb.decide(ReflexAction.NONE, 10.0, {})
        self.assertEqual(d, Decision.HOLD)

if __name__ == '__main__':
    unittest.main()

