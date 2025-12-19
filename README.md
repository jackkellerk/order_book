# Order book implementation

### Introduction
There are a variety of venues for trading equities. Each venue is classified as either a 1) lit venue or exchange, or 2) dark pool or alternative trading system (ATS). An example of a lit venue or exchange is [NYSE Chicago](https://en.wikipedia.org/wiki/NYSE_Chicago), and an example of a dark pool or ATS is [JPM-X, JPM's dark pool](https://www.jpmorgan.com/content/dam/jpm/cib/complex/content/markets/aqua/pdf-0.pdf). Exchanges have market data subscriptions that provide either top-of-book market data, or full order book market depth. Top-of-book market data provides updates only for the highest limit order bid price and size as well as for the lowest limit order offer price and size for that exchange. Full order book market depth data provides updates for every individual limit order within that exchange. Dark pools usually do not provide any market data subscriptions or color on any limit orders resting within them.

Across all listed U.S. securities, approximately 56% of all trades by volume are traded through exchanges per [Nasdaq's 2024 Market Share Update](https://www.nasdaq.com/docs/2024/US_Equity_Market_Data_Whitepaper). The remaining 44% share are traded through dark pools. Of the share of trades executed on exchanges, ~50% trades through Nasdaq exchanges, ~25% trade through NYSE exchanges, and the rest is split up among other smaller exchanges such as MIAX and IEX.

### Data specification

The market data we are subscribed to from databento is market-by-order ([mbo](https://databento.com/docs/schemas-and-data-formats/mbo?historical=python&live=python&reference=python)). This data feed will give us status updates for each individual resting limit order in the order book per exchange; so on our end, we need to construct the order book for each exchange and manage its state.

There are multiple product offerings from databento. Each product offering contains mbo updates from either one or a collection of exchanges. For example, the product offering [Databento Equities Basic](https://databento.com/docs/venues-and-datasets/dbeq-basic?historical=python&live=python&reference=python) contains mbo updates from NYSE Chicago, NYSE National, and IEX exchanges. Specifically, the Databento Equities Basic product offering contains full market depth data for NYSE Chicago, top-of-book data for NYSE National, and top-of-book data for IEX. There are many additional product offerings from databento. For example, the product offering called [Nasdaq TotalView-ITCH](https://databento.com/docs/venues-and-datasets/xnas-itch?historical=python&live=python&reference=python) provides full market depth data for its flagship exchange, [The Nasdaq Stock Market](https://www.nasdaq.com/solutions/nasdaq-stock-market). Also, the product offering called [MIAX Depth of Market](https://databento.com/docs/venues-and-datasets/eprl-dom?historical=python&live=python&reference=python) provides full market depth data for its flagship exchange, [MIAX Pearl Equities](https://www.miaxglobal.com/markets/us-equities/pearl-equities).

Status updates are called [actions](https://databento.com/docs/standards-and-conventions/common-fields-enums-types#action?historical=python&live=python&reference=python) per convention from databento. Actions can either be add, cancel, modify, clear, trade, fill, or none. The metadata of each action is stored in an instantiated object of class MBOMsg that contains the metadata as its fields. Usually actions are individual messages, but sometimes actions can come in paired messages. In the case of paired messages, the subsequent actions will have the same ```ts_recv``` and ```sequence``` fields indicating they happened at the same time.

An add action adds a new limit order to the order book of an exchange. It contains a unique ```order_id``` field that future mbo messages from that exchange will use to indicate updates to that specific limit order going forward. Order ids are unique per exchange, so its possible per databento product offering that the same order id is used to reference two separate limit orders in different exchange's order books. The definition of the add action differs between full order book market depth data feeds and top-of-book data feeds. For full order book market depth data feeds, each add action will contain the flag ```LAST (130)``` indicating that there is no paired message associated with it. For top-of-book data feeds, each add action comes with a paired message. The first message will be one of the top bid or top offer, while the second message will be the corresponding top bid or top offer. These add actions will have the same ```ts_recv``` and ```sequence``` fields indicating they happened at the same time, and they will also have the same ```order_id``` despite them being two separate limit orders. The first add action of the pair will contain only the ```TOB (64)``` flag, while the second add action of the pair will contain both ```TOB (64)``` and ```LAST (130)``` flags; the last flag indicating that the status update is completed. Either one or both of the paired messages can have a ```price``` field with value of ```UNDEF_PRICE```. This indicates there is currently no top bid or top offer on that exchange.

A trade action is sent when an aggressing order is matched to a limit order for both top-of-book and full order book market depth data feeds. In top-of-book data feeds, the next action will be a paired add action indicating the new top-of-book bid and offer prices and sizes. For full order book market depth feeds, the subsequent action will be a fill action, and then a separate cancel action for the resting limit order that was filled. For purposes of maintaing the state of the order book on our end, we can ignore trade and fill status updates -- although there is probably interesting info that can be gained from those status updates for future trading strategies.

Sometimes a mbo update will contain the flag ```BAD_TS_RECV``` indicating 	the ts_recv value is inaccurate due to clock issues or packet reordering. We can probably ignore this because the state of the order book should still be correctly maintained. The flag ```MAYBE_BAD_BOOK``` may also be sent indicating an unrecoverable gap was detected in the channel. This is more serious and we may need to reset our connection and order book.

Sample add order message from a full market depth data feed:
``` 
MboMsg 
{ 
    hd: RecordHeader 
        { 
            length: 14, 
            rtype: Mbo, 
            publisher_id: DbeqBasicXchi, 
            instrument_id: 10451, 
            ts_event: 1732545110195434332 
        },
    order_id: 15493218347188284, 
    price: 560.800000000, 
    size: 200, 
    flags: LAST (130), 
    channel_id: 4, 
    action: 'A', 
    side: 'B', 
    ts_recv: 1732545110195649913, 
    ts_in_delta: 203531, 
    sequence: 164784
}
```

Sample add order message from a top-of-book data feed:
```
MboMsg 
{ 
    hd: RecordHeader 
    { 
        length: 14, 
        rtype: Mbo, 
        publisher_id: DbeqBasicIexg, 
        instrument_id: 10451, 
        ts_event: 1732545107712841206 
    }, 
    order_id: 6342, 
    price: UNDEF_PRICE, 
    size: 0, 
    flags: TOB (64), 
    channel_id: 0, 
    action: 'A', 
    side: 'B', 
    ts_recv: 1732545107712926885, 
    ts_in_delta: 26043, 
    sequence: 2357458 
}

MboMsg 
{ 
    hd: RecordHeader 
    { 
        length: 14, 
        rtype: Mbo, 
        publisher_id: DbeqBasicIexg, 
        instrument_id: 10451, 
        ts_event: 1732545107712841206 
    }, 
    order_id: 6342, 
    price: 561.600000000, 
    size: 200, 
    flags: LAST | TOB (194), 
    channel_id: 0, 
    action: 'A', 
    side: 'A', 
    ts_recv: 1732545107712926885, 
    ts_in_delta: 26043, 
    sequence: 2357458 
}
```