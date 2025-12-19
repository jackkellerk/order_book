from __future__ import annotations

from typing import Optional
from .message import Message
from dataclasses import dataclass

@dataclass
class OrderNode:
    """ Class used as node object for use within the order LinkedList class. """
    
    order_id: int
    price: float
    size: int
    publisher_id: int
    instrument_id: int
    side: str
    ts_recv: int

    prev: Optional[OrderNode] = None
    next: Optional[OrderNode] = None

@dataclass
class OrderLinkedList:
    """ Data structure used to keep track of order priority for a given price level in the order book. This implementation is a doubly-linked list for time complexity efficiency. """
    
    price: float

    _depth: int = 0
    _num_orders: int = 0
    _head: Optional[OrderNode] = None
    _tail: Optional[OrderNode] = None

    def append(self, msg: Message) -> OrderNode:
        """ 
            Adds a new order for this price level at the end of the linked list.

            Runtime complexity: `O(1)`

            :param msg: message object sent via databento.
        """

        self._num_orders += 1
        self._depth += msg.size

        node = OrderNode(
            order_id = msg.order_id, 
            price = msg.price,
            size = msg.size,
            publisher_id = msg.publisher_id,
            instrument_id = msg.instrument_id,
            side = msg.side,
            ts_recv = msg.ts_recv
        )
        
        node.prev = self._tail

        if self._tail:
            self._tail.next = node

        if not self._head:
            self._head = node
        
        self._tail = node

        return node

    def remove(self, order_node: OrderNode, amount: Optional[int] = None) -> None:
        """ 
            Decreases an existing order's size within the linked list. If size is zero, removes the order from the linked list.

            Runtime complexity: `O(1)`

            :param order_node: node object containing the order details.
            :param ammount: size to subtract from existing order.

            :raises ValueError: if amount is greater than existing size. In this case, order loses priority and should be treated as a cancel and replace.
        """
        
        if amount > order_node.size:
            raise ValueError(f"Amount ({amount}) is greater than existing size {order_node.size} for order id {order_node.order_id}.")
        
        order_node.size -= amount
        self._depth -= amount

        if order_node.size == 0:
            self._num_orders -= 1

            if order_node == self._head:
                self._head = order_node.next
            if order_node == self._tail:
                if order_node.next:
                    self._tail = order_node.next
                else:
                    self._tail = order_node.prev

            if order_node.prev:
                order_node.prev.next = order_node.next
            if order_node.next:
                order_node.next.prev = order_node.prev

    def get_num_orders(self) -> int:
        return self._num_orders

    def get_num_shares(self) -> int:
        return self._depth

    def __len__(self) -> int:
        return self.get_num_orders()
