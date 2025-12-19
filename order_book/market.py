import databento as db
from .message import Message
from typing import Optional, Tuple
from typing_extensions import Self
from .best_bid_offer import BestBidOffer
from .order_book import OrderBook, TopOfBookOrderBook
from databento_dbn import SymbolMappingMsg, MBOMsg, SystemMsg

class Market:
    """        
        This class is used to keep track of all trading activity across all imnts. 
        This tracks the market in real-time via status updates via databento messages.

        Specifically, this market object manages the internal state of the different exchanges per imnt.
    """

    def __init__(self) -> Self:
        self.exchanges = {}
        self.symbology = {}

        # For messages that come in pairs (i.e. TOB data feeds).
        # Market() state should only be viewed when is_ready is true.
        self.is_ready = True

    def _set_symbology(self, msg: SymbolMappingMsg) -> None:
        """
            Sets the instrument_id, ticker pair for each ticker traded.

            :param msg: databento SymbolMappingMsg
        """
        self.symbology[msg.instrument_id] = msg.stype_out_symbol
    
    def _get_order_book(self, msg: Message) -> OrderBook:
        """
            Private method. Grabs the order book for a specific exchange and instrument id.
            If the order book or exchange dict does not exist, create it.

            :param msg: message object sent via databento.

            :return OrderBook: the order book object.
        """

        # If add action, and we don't have exchange dictionary, create it
        if (not msg.publisher_id in self.exchanges) and (msg.action == "A"):
            self.exchanges[msg.publisher_id] = {}

        # Grab exchange if exists
        if msg.publisher_id in self.exchanges:   
            exchange = self.exchanges[msg.publisher_id]

            # If instrument id order book is being tracked by exchange, return it
            if msg.instrument_id in exchange:
                return exchange[msg.instrument_id]

            # Else, create the order book for the exchange if msg is an add action
            elif msg.action == "A":
                instrument = self.symbology[msg.instrument_id] if msg.instrument_id in self.symbology else msg.instrument_id

                if msg.flags & db.RecordFlags.F_TOB:
                    exchange[msg.instrument_id] = TopOfBookOrderBook(instrument, msg.publisher_id)
                else:
                    exchange[msg.instrument_id] = OrderBook(instrument, msg.publisher_id)

                return exchange[msg.instrument_id]

        # Otherwise, return an empty order book to perform the operation on
        return OrderBook(msg.instrument_id, msg.publisher_id)
    
    def bbo(self, instrument_id: int, publisher_id: Optional[int] = None) -> Tuple[BestBidOffer, BestBidOffer]:
        """
            Returns the best bid and offer for a particular exchange or across all data feeds.

            :param publisher_id: this is the id of the exchange (or data publisher)
            :param instrument_id: this is the id of the instrument being traded      

            :return BestBidOffer, BestBidOffer: the best bid and offer tuple
        """
        
        if publisher_id:
            return self.get_order_book(instrument_id, publisher_id).bbo()
        
        else:
            # Set temporary best bid and offer
            best_bid, best_offer = BestBidOffer(), BestBidOffer()
        
            # Loop over all exchange data feeds
            for publisher_id in self.exchanges:
                order_book = self.get_order_book(instrument_id, publisher_id)
                exchange_best_bid, exchange_best_offer = order_book.bbo()

                # If best bids exists (for comparison)
                if best_bid.price and exchange_best_bid.price:
                    if best_bid.price < exchange_best_bid.price:
                        best_bid = exchange_best_bid
                
                elif exchange_best_bid.price:
                    best_bid = exchange_best_bid
                
                # If best offers exists (for comparison)
                if best_offer.price and exchange_best_offer.price:
                    if best_offer.price > exchange_best_offer.price:
                        best_offer = exchange_best_offer
                
                elif exchange_best_offer.price:
                    best_offer = exchange_best_offer
            
            return best_bid, best_offer
    
    def get_order_book(self, instrument_id: int, publisher_id: int) -> OrderBook:
        """
            Grabs the order book for a specific exchange and instrument id.

            :param publisher_id: this is the id of the exchange (or data publisher)
            :param instrument_id: this is the id of the instrument being traded      

            :return OrderBook: the order book object. if doesnt exist, returns empty order book.
        """
        
        if publisher_id in self.exchanges:
            if instrument_id in self.exchanges[publisher_id]:
                return self.exchanges[publisher_id][instrument_id]
        
        return OrderBook(instrument_id, publisher_id)

    def apply(self, msg: MBOMsg | SymbolMappingMsg | SystemMsg) -> None:
        """
            Update the state of our order book given a databento msg object.

            :param msg: databento SymbolMappingMsg or MBOMsg or SystemMsg.

            :raise TypeError: if type is not either databento SymbolMappingMsg or MBOMsg.
        """

        if isinstance(msg, SymbolMappingMsg):
            self._set_symbology(msg)
        
        elif isinstance(msg, MBOMsg):
            
            # Sanitize the message
            msg = Message(msg)

            # Apply this message to the order book
            self._get_order_book(msg).apply(msg)

            # If messages is last, order book state is ready
            self.is_ready = msg.flags & db.RecordFlags.F_LAST

        elif isinstance(msg, SystemMsg):       
            pass # Skip heartbeat messages
        
        else:            
            raise TypeError(f"{type(msg)} is not a valid type of message.")
