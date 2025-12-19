import databento as db
from .message import Message
from typing_extensions import Self
from databento_dbn import UNDEF_PRICE
from sortedcontainers import SortedDict
from .best_bid_offer import BestBidOffer
from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta, timezone
from .order_linked_list import OrderLinkedList, OrderNode

class OrderBook:
    """
        This class is used to manage the state of a full depth order book for an imnt per exchange.
    """

    def __init__(self, instrument: int | str, publisher: int | str) -> Self:
                
        self.instrument: int | str = instrument
        self.publisher: int | str = publisher
        self.ts_last_update: int = 0

        # Keep a reference to each order node using the order id as the key.
        self.orders: Dict[int, OrderNode] = {}
    
        # Create two separate sorted dictionaries (Red-Black Tree implementations) for bid and offer price levels.
        # Keys are price levels, values are the OrderLinkedList objects containing the unique orders per price level.
        self.bids: SortedDict[float, OrderLinkedList] = SortedDict()
        self.offers: SortedDict[float, OrderLinkedList] = SortedDict()

    def _clear(self) -> None:
        """
            Clear the entire order book.
        """

        self.orders = {}
        self.bids = SortedDict()
        self.offers = SortedDict()

    def _side_dict(self, side: str) -> SortedDict[float, OrderLinkedList]:
        """
            Return the correct sorted dictionary (Red-Black Tree implementations) for the side.

            :param side: the str representing the side to return.
            :raise ValueError: for invalid side. 'A' for offer and 'B' for bid are valid sides.
        """

        if side == "A":
            return self.offers
        elif side == "B":
            return self.bids
        else:
            raise ValueError(f"{side} not a valid side. 'A' for offer and 'B' for bid are valid sides.")

    def _add(self, msg: Message) -> None:
        """
            Add an order to the order book.

            Runtime complexity: 
                `O(log L)` if price level doesn't exist. 
                `O(1)` if price level exists.

            :param msg: message object sent via databento.
        """
        
        # Assert order id does not already exist
        assert not msg.order_id in self.orders
        
        # Assert we are inserting a real price
        assert not msg.price == UNDEF_PRICE
            
        # Get the side sorted dictionary
        px_level_tree = self._side_dict(msg.side)

        # If price level doesn't exist, create the price level in the sorted dictionary
        if not msg.price in px_level_tree:
            px_level_tree[msg.price] = OrderLinkedList(msg.price)

        # Create the order node
        order_list = px_level_tree[msg.price]
        order_node = order_list.append(msg)
        
        # Place the order node in the orders dictionary for easy lookup later
        self.orders[msg.order_id] = order_node

    def _cancel(self, msg: Message) -> None:
        """
            Cancel an order currently in the order book.

            Runtime complexity: 
                `O(log L)` if price level doesn't have any other orders.
                `O(1)` if price level does have other orders.

            :param msg: message object sent via databento.
        """
        
        # Grab order node
        order_node = self.orders[msg.order_id]

        # Find which side tree it is on, and get the order linked list 
        px_level_tree = self._side_dict(order_node.side)
        order_list = px_level_tree[order_node.price]

        # Cancel the order node
        order_list.remove(order_node, msg.size)
        
        # If size is zero, delete this order from the linked list at the price level, and remove it from the orders dictionary.
        if order_node.size == 0:            
            del self.orders[msg.order_id]

            # If there are no more orders at this price level, remove it from the tree.
            if len(order_list) == 0:
                del px_level_tree[order_node.price]
        
        # Else, update the modify time for the order node.
        else:
            order_node.ts_recv = msg.ts_recv

    def _modify(self, msg: Message) -> None:
        """
            Modify an order currently in the order book.

            Runtime complexity:
                `O(log L)` if limit px was modified or order size is increased.
                `O(1)` if order size was decreased.

            :param msg: message object sent via databento.
        """

        order_node = self.orders[msg.order_id]
        px_level_tree = self._side_dict(order_node.side)
        order_list = px_level_tree[order_node.price]

        # Orders cannot change side
        assert order_node.side == msg.side

        # Changing limit price loses priority
        if not msg.price == order_node.price:
            self._cancel(msg)
            self._add(msg)

        # Increasing size loses priority
        elif msg.size > order_node.size:
            self._cancel(msg)
            self._add(msg)
        
        # Last modification is decreasing the size
        else:
            cancel_size = order_node.size - msg.size
            order_list.remove(order_node, cancel_size)
                        
            order_node.ts_recv = msg.ts_recv

    def apply(self, msg: Message) -> None:
        """
            Update the order book based on a new message (Message).

            :param msg: message object sent via databento.

            :raise ValueError: for invalid action. 'T', 'F', 'N', 'R', 'A', 'C', and 'M' are valid actions types.
        """

        # Raise exception if TOB flag is sent.
        if msg.flags & db.RecordFlags.F_TOB:
            raise ValueError("TOB (64) flag indicates that the TopOfBookOrderBook class should be used.")
        
        # Trade, Fill, or None: no change. Trade and Fill actions do not affect the book because all fills will be accompanied by cancel actions that do update the book.
        if msg.action in ("T", "F", "N"):
            pass
        
        # Clear entire book: remove all resting orders.
        elif msg.action == "R":
            self._clear()

        # Add: insert a new order.
        elif msg.action == "A":
            self._add(msg)

        # Cancel: partially or fully cancel some size from a resting order.
        elif msg.action == "C":
            self._cancel(msg)

        # Modify: change the price and/or size of a resting order.
        elif msg.action == "M":
            self._modify(msg)

        # Else, raise error
        else:
            raise ValueError(f"Unknown action = {msg.action}")
        
        # Save last update time
        self.ts_last_update = msg.ts_recv
        
    def bbo(self) -> Tuple[BestBidOffer, BestBidOffer]:
        """ Returns best bid and offer in the order book. """

        if len(self.bids) > 0:
            _, best_bid_level = self.bids.peekitem(-1)
            best_bid = BestBidOffer(
                price = best_bid_level.price,
                size = best_bid_level.get_num_shares()
            )  
        
        else:
            best_bid = BestBidOffer()

        if len(self.offers) > 0:
            _, best_offer_level = self.offers.peekitem(0)
            best_offer = BestBidOffer(
                price = best_offer_level.price,
                size = best_offer_level.get_num_shares()
            )
        
        else:
            best_offer = BestBidOffer()

        return best_bid, best_offer
    
    def __str__(self) -> str:
        """ Print the L2 order book """

        # Get last update time
        utc_last_update_time = datetime.fromtimestamp(self.ts_last_update // 1_000_000_000, timezone.utc)
        est_last_update_time = utc_last_update_time - timedelta(hours = 5)
        nanoseconds = str(int(self.ts_last_update % 1_000_000_000)).zfill(9)

        # Dynamically construct string to return
        imnt = str(self.instrument)
        pub = "Exchange: " + str(self.publisher)
        
        imnt_dash_size = (52 - len(imnt)) // 2
        pub_dash_size = (52 - len(pub)) // 2
        res = f"{'-' * imnt_dash_size} {imnt} {'-' * imnt_dash_size}\n{'-' * pub_dash_size} {pub} {'-' * pub_dash_size}\nLast update (UTC): {utc_last_update_time}.{nanoseconds}\nLast update (EST): {est_last_update_time}.{nanoseconds}\n"

        # Loop over offers        
        for i in range( len(self.offers) ):
            px, order_linked_list = self.offers.peekitem((-1 * i) - 1)
            res += f"\t\t{ order_linked_list.price } x { order_linked_list.get_num_shares() }\n"
        
        # Loop over bids
        for i in range( len(self.bids) ):
            px, order_linked_list = self.bids.peekitem((-1 * i) - 1)
            res += f"{ order_linked_list.price } x { order_linked_list.get_num_shares() }\n"
        
        return res

class TopOfBookOrderBook(OrderBook):
    """
        This class is used to manage the state of a top of book order book for an imnt per exchange.
    """

    def __init__(self, instrument: int | str, publisher: int | str) -> Self:
                
        self.instrument: int | str = instrument
        self.publisher: int | str = publisher
        self.ts_last_update: int = 0
    
        # Top of book order book feeds only track the current best bid and best offer
        self.bid: Optional[OrderNode] = None
        self.offer: Optional[OrderNode] = None

    @property
    def orders(self) -> List[OrderNode]:
        res = []

        if self.bid:
            res.append(self.bid)
        if self.offer:
            res.append(self.offer)

        return res

    def _clear(self) -> None:
        """
            Clear the entire order book.
        """

        self.bid = None
        self.offer = None

    def _add(self, msg: Message) -> None:
        """
            Add an order to the order book.

            Runtime complexity: `O(1)`

            :param msg: message object sent via databento.
        """

        # Sides that do not have any orders come as messages where the size is zero and limit price is UNDEF_PRICE.
        # For sides without an order, set it as null.
        if msg.size == 0 and msg.price == UNDEF_PRICE:
            node = None
        else:
            node = OrderNode(
                order_id = msg.order_id, 
                price = msg.price,
                size = msg.size,
                publisher_id = msg.publisher_id,
                instrument_id = msg.instrument_id,
                side = msg.side,
                ts_recv = msg.ts_recv
            )

        if msg.side == "B":
            self.bid = node
        else:
            self.offer = node

        # Top of book messages are sent in pairs. If the current message does not contain the F_LAST (128) flag, 
        # update the other side to null while you wait to process the next message for the pair.
        if not msg.flags & db.RecordFlags.F_LAST:
            if msg.side == "B":
                self.offer = None
            else:
                self.bid = None

        # Update time
        self.ts_last_update = msg.ts_recv

    def apply(self, msg: Message) -> None:
        """
            Update the order book based on a new message (AggregatedMessage).

            :param msg: message object sent via databento.

            :raise ValueError: for invalid action. 'T', 'F', 'N', 'R', 'A', 'C', and 'M' are valid actions types.
        """
        
        # Trade or None: no change. Trade action does not affect the book because all trades will be accompanied by new add actions that do update the book.
        if msg.action in ("T", "N"):
            pass
        
        # Clear entire book: remove all resting orders.
        elif msg.action == "R":
            self._clear()

        # Add: insert a new order.
        elif msg.action == "A":
            
            # Raise exception if TOB flag is not sent.
            if not msg.flags & db.RecordFlags.F_TOB:
                raise ValueError("Needs to have a TOB (64) flag, which indicates that the TopOfBookOrderBook class should be used.")
            
            self._add(msg)

        # Else, raise error
        else:
            raise ValueError(f"Unknown action = {msg.action}")
        
        # Save last update time
        self.ts_last_update = msg.ts_recv

    def bbo(self) -> Tuple[BestBidOffer, BestBidOffer]:
        """ Returns best bid and offer in the order book. """
        
        if self.bid:
            best_bid = BestBidOffer(                
                price = self.bid.price,
                size = self.bid.size
            )
        
        else:
            best_bid = BestBidOffer()

        if self.offer:
            best_offer = BestBidOffer(                
                price = self.offer.price,
                size = self.offer.size   
            )
        
        else:
            best_offer = BestBidOffer()

        return best_bid, best_offer
    
    def __str__(self) -> str:
        """ Print the bbo """

        # Get last update time
        utc_last_update_time = datetime.fromtimestamp(self.ts_last_update // 1_000_000_000, timezone.utc)
        est_last_update_time = utc_last_update_time - timedelta(hours = 5)
        nanoseconds = str(int(self.ts_last_update % 1_000_000_000)).zfill(9)

        # Dynamically construct string to return
        imnt = str(self.instrument)
        pub = "Exchange: " + str(self.publisher)
        
        imnt_dash_size = (52 - len(imnt)) // 2
        pub_dash_size = (52 - len(pub)) // 2
        res = f"{'-' * imnt_dash_size} {imnt} {'-' * imnt_dash_size}\n{'-' * pub_dash_size} {pub} {'-' * pub_dash_size}\nLast update (UTC): {utc_last_update_time}.{nanoseconds}\nLast update (EST): {est_last_update_time}.{nanoseconds}\n"

        # Print best bid offer
        best_bid, best_offer = self.bbo()

        if best_offer.price:
            res += f"\t\t{best_offer.price} x {best_offer.size}\n"
        else:
            res += f"\t\t\n"
        
        if best_bid.price:
            res += f"{best_bid.price} x {best_bid.size}\n"
        else:
            res += f"\n"
        
        return res
