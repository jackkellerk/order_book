import databento as db
from order_book.market import Market

data = db.read_dbn(f"./data/XNAS.ITCH-TECHBASKET-20241227.mbo.dbn.zst")

market = Market()
for msg in data:
    market.apply(msg)

    if market.is_ready:
        order_book = market.get_order_book(msg.instrument_id, msg.publisher_id)
        print(order_book)