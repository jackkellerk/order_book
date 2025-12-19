from typing import Dict, Tuple
from typing_extensions import Self
from databento_dbn import MBOMsg, FIXED_PRICE_SCALE, UNDEF_PRICE

class Message:
    """
        This class is used to preprocess MBOMsgs for the Market class.
    """

    def __init__(self, msg: MBOMsg) -> Self:        
        self.action = msg.action
        self.order_id = msg.order_id
        self.size = msg.size
        self.publisher_id = msg.publisher_id
        self.instrument_id = msg.instrument_id
        self.ts_event = msg.ts_event
        self.side = msg.side
        self.ts_recv = msg.ts_recv
        self.flags = msg.flags

        # Prices are sent in increments of 1e9, so we either rescale 
        # the prices or keep them as UNDEF_PRICE.
        if msg.price == UNDEF_PRICE:
            self.price = msg.price
        else:
            self.price = msg.price / FIXED_PRICE_SCALE