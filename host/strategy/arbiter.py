from enum import Enum
from .reflex import ReflexAction

class Decision(Enum):
    HOLD = 0
    BUY = 1
    SELL = 2
    CANCEL = 3

class Arbiter:
    """
    The Final Decision Maker.
    Inputs:
    1. Reflex Action (CPU) - Fast, deterministic
    2. Neural Score (FPGA) - Slow(er), probabilistic
    """
    def __init__(self):
        # Threshold for SNN score (0-255 usually, or scaled)
        self.score_threshold = 200 
        
    def decide(self, reflex_action: ReflexAction, fpga_score: float, fpga_features: dict) -> Decision:
        """
        Combine signals to produce final trading decision.
        """
        
        # PRIORITY 1: Reflex Safety Rules override everything
        if reflex_action == ReflexAction.CANCEL_ALL:
            return Decision.CANCEL
            
        if reflex_action == ReflexAction.TAKE_LIQUIDITY:
            # Simple logic: if crossed, take the side that makes sense (omitted for brevity)
            return Decision.BUY 

        # PRIORITY 2: FPGA Neural Signal
        # Assuming higher score = higher toxicity/volatility -> SELL/WIDEN
        # Or if score represents alpha, BUY/SELL based on sign.
        # Let's assume score is "Buy Signal Strength" for this demo.
        
        # The MLP returns a raw score. Let's say > 100 is Buy, < -100 is Sell.
        # Using the 'vol' feature as a proxy for now if score is raw features
        
        if fpga_score > self.score_threshold:
             return Decision.BUY
             
        if fpga_score < -self.score_threshold:
            return Decision.SELL

        return Decision.HOLD

