from typing import Optional
from dataclasses import dataclass

@dataclass
class BestBidOffer:
    """ Used as a data class specifically for bbo() function of OrderBook class. """
            
    size: int = 0
    price: Optional[float] = None