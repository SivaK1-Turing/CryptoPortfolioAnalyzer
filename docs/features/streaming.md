# Real-Time Data Streaming

The Crypto Portfolio Analyzer includes a comprehensive real-time data streaming system that provides live price updates, portfolio monitoring, and WebSocket-based communication for building interactive applications.

## Overview

The streaming system consists of several key components:

- **Stream Manager**: Core WebSocket connection management
- **Price Feed Manager**: Real-time price data from multiple sources
- **Event System**: Publish/subscribe event handling
- **WebSocket Server**: Real-time web interface
- **Portfolio Monitor**: Live portfolio value tracking

## Quick Start

### Basic Price Monitoring

Monitor real-time prices in your terminal:

```bash
# Monitor BTC prices with mock data
crypto-analyzer stream monitor --symbols BTC --provider mock

# Monitor multiple symbols from Binance
crypto-analyzer stream monitor --symbols BTC,ETH,ADA --provider binance
```

### Start WebSocket Server

Launch a WebSocket server for web applications:

```bash
# Start server on default port (8000)
crypto-analyzer stream start

# Start on custom port with specific symbols
crypto-analyzer stream start --port 8001 --symbols BTC,ETH --provider mock
```

### Test Streaming Components

Test the streaming system with mock data:

```bash
# Run a 10-second test with BTC
crypto-analyzer stream test --symbols BTC --duration 10
```

## Architecture

### Stream Manager

The `StreamManager` handles WebSocket connections and provides:

- Connection pooling and management
- Automatic reconnection with exponential backoff
- Message routing and filtering
- Connection health monitoring

```python
from crypto_portfolio_analyzer.streaming import StreamManager, StreamConfig

# Create stream configuration
config = StreamConfig(
    stream_id="binance_btc",
    url="wss://stream.binance.com:9443/ws/btcusdt@ticker",
    symbols=["BTC"],
    reconnect_attempts=5,
    heartbeat_interval=30.0
)

# Initialize and start stream manager
manager = StreamManager()
await manager.start()
await manager.add_stream(config)
```

### Price Feed Manager

The `PriceFeedManager` aggregates price data from multiple sources:

```python
from crypto_portfolio_analyzer.streaming import PriceFeedManager, PriceFeedProvider

# Create price feed manager
manager = PriceFeedManager()

# Add primary provider
manager.add_provider(PriceFeedProvider.BINANCE, ["BTC", "ETH"], is_primary=True)

# Add fallback provider
manager.add_provider(PriceFeedProvider.COINBASE, ["BTC", "ETH"], is_primary=False)

# Add price update handler
def handle_price_update(update):
    print(f"{update.symbol}: ${update.price}")

manager.add_handler(handle_price_update)

# Start receiving updates
await manager.start()
```

### Event System

The event system provides publish/subscribe functionality:

```python
from crypto_portfolio_analyzer.streaming import StreamEventBus, EventType

# Create event bus
event_bus = StreamEventBus()
await event_bus.start()

# Subscribe to price updates
def handle_price_event(event):
    data = event.data
    print(f"Price update: {data['symbol']} = ${data['price']}")

event_bus.subscribe("price_handler", handle_price_event, 
                   event_types={EventType.PRICE_UPDATE})

# Publish events
await event_bus.publish_price_update("BTC", {"price": 50000, "change": 2.5})
```

## Supported Data Sources

### Binance

Real-time data from Binance WebSocket API:

- **Endpoint**: `wss://stream.binance.com:9443/ws/`
- **Data**: Price, volume, 24h change
- **Update Frequency**: Real-time
- **Rate Limits**: 1200 requests per minute

### Coinbase Pro

Real-time data from Coinbase Pro WebSocket API:

- **Endpoint**: `wss://ws-feed.pro.coinbase.com`
- **Data**: Price, volume, order book
- **Update Frequency**: Real-time
- **Rate Limits**: No explicit limits

### Mock Provider

Simulated data for testing and development:

- **Data**: Realistic price movements
- **Update Frequency**: Configurable (default: 1 second)
- **Symbols**: BTC, ETH, ADA, DOT, LINK

## WebSocket Server

The WebSocket server provides a real-time web interface:

### Endpoints

- `GET /`: Dashboard interface
- `GET /status`: Server status and metrics
- `WebSocket /ws`: Real-time data connection

### Client Connection

Connect to the WebSocket server from JavaScript:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = function(event) {
    console.log('Connected to streaming server');
    
    // Join price updates room
    ws.send(JSON.stringify({
        type: 'join_room',
        room: 'prices'
    }));
};

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    if (data.type === 'price_update') {
        console.log(`${data.data.symbol}: $${data.data.price}`);
    }
};
```

### Message Types

The WebSocket server sends various message types:

```json
{
    "type": "price_update",
    "data": {
        "symbol": "BTC",
        "price": 50000.00,
        "change_24h": 1000.00,
        "change_percent_24h": 2.5,
        "volume_24h": 1000000.00,
        "timestamp": "2025-07-03T10:00:00Z"
    },
    "timestamp": "2025-07-03T10:00:00Z"
}
```

```json
{
    "type": "portfolio_update",
    "data": {
        "total_value": 100000.00,
        "total_change_24h": 2500.00,
        "total_change_percent_24h": 2.56,
        "holdings": [
            {
                "symbol": "BTC",
                "amount": 2.0,
                "value": 100000.00,
                "change_24h": 2000.00
            }
        ]
    },
    "timestamp": "2025-07-03T10:00:00Z"
}
```

## Portfolio Monitoring

Monitor your portfolio value in real-time:

```python
from crypto_portfolio_analyzer.streaming import PortfolioMonitor

# Create portfolio monitor
monitor = PortfolioMonitor()

# Add holdings
monitor.add_holding("BTC", Decimal("2.0"))
monitor.add_holding("ETH", Decimal("10.0"))

# Set up price feed
await monitor.start_monitoring(provider=PriceFeedProvider.MOCK)

# Monitor will automatically update portfolio values as prices change
```

## Configuration

### Stream Configuration

Configure stream connections:

```python
config = StreamConfig(
    stream_id="my_stream",
    url="wss://example.com/ws",
    symbols=["BTC", "ETH"],
    reconnect_attempts=5,        # Number of reconnection attempts
    reconnect_delay=1.0,         # Initial reconnection delay (seconds)
    max_reconnect_delay=60.0,    # Maximum reconnection delay (seconds)
    heartbeat_interval=30.0,     # Heartbeat interval (seconds)
    buffer_size=1000,            # Message buffer size
    rate_limit=100,              # Messages per second limit
    headers={"Authorization": "Bearer token"},  # Custom headers
    params={"symbols": "BTCUSDT"}  # URL parameters
)
```

### Event Filtering

Filter events by type, source, or custom criteria:

```python
from crypto_portfolio_analyzer.streaming import EventFilter

# Filter by event type
price_filter = EventFilter(event_types={EventType.PRICE_UPDATE})

# Filter by source
binance_filter = EventFilter(sources={"binance"})

# Filter by symbol
btc_filter = EventFilter(symbols={"BTC"})

# Custom filter function
def high_value_filter(event):
    return event.data.get("price", 0) > 50000

custom_filter = EventFilter(custom_filter=high_value_filter)
```

## Error Handling

The streaming system includes comprehensive error handling:

### Connection Errors

- Automatic reconnection with exponential backoff
- Connection health monitoring
- Graceful degradation to fallback providers

### Data Errors

- Message validation and sanitization
- Error logging and metrics
- Continued operation despite individual message failures

### Rate Limiting

- Built-in rate limiting for API calls
- Automatic backoff when limits are exceeded
- Queue management for high-frequency updates

## Monitoring and Metrics

### Stream Metrics

Monitor stream performance:

```python
# Get metrics for a specific stream
metrics = manager.get_stream_metrics("binance_btc")
print(f"Messages received: {metrics.messages_received}")
print(f"Connection uptime: {metrics.uptime_seconds}s")
print(f"Average latency: {metrics.latency_ms}ms")

# Get metrics for all streams
all_metrics = manager.get_all_metrics()
```

### Event Bus Metrics

Monitor event processing:

```python
# Get event bus statistics
stats = event_bus.get_bus_stats()
print(f"Events published: {stats['events_published']}")
print(f"Events processed: {stats['events_processed']}")
print(f"Active subscriptions: {stats['active_subscriptions']}")
```

## CLI Commands

### stream monitor

Monitor real-time prices in the terminal:

```bash
crypto-analyzer stream monitor [OPTIONS]

Options:
  --symbols TEXT                  Comma-separated list of symbols to monitor
  --provider [binance|coinbase|mock]  Price feed provider
  --refresh FLOAT                 Refresh interval in seconds
```

### stream start

Start the WebSocket server:

```bash
crypto-analyzer stream start [OPTIONS]

Options:
  --host TEXT                     WebSocket server host
  --port INTEGER                  WebSocket server port
  --symbols TEXT                  Comma-separated list of symbols to stream
  --provider [binance|coinbase|mock]  Price feed provider
  --dashboard / --no-dashboard    Open dashboard in browser
```

### stream test

Test streaming components:

```bash
crypto-analyzer stream test [OPTIONS]

Options:
  --symbols TEXT                  Comma-separated list of symbols to test
  --provider [binance|coinbase|mock]  Price feed provider
  --duration INTEGER              Test duration in seconds
```

### stream status

Check server status:

```bash
crypto-analyzer stream status [OPTIONS]

Options:
  --host TEXT                     Server host
  --port INTEGER                  Server port
```

### stream alert

Set up price alerts:

```bash
crypto-analyzer stream alert [OPTIONS]

Options:
  --symbol TEXT                   Symbol to monitor
  --condition TEXT                Alert condition (e.g., "price > 50000")
  --message TEXT                  Alert message
```

## Best Practices

### Performance

1. **Use connection pooling**: Reuse WebSocket connections when possible
2. **Implement rate limiting**: Respect API rate limits to avoid disconnections
3. **Buffer messages**: Use message buffering for high-frequency updates
4. **Monitor memory usage**: Clean up old events and metrics regularly

### Reliability

1. **Implement fallback providers**: Use multiple data sources for redundancy
2. **Handle reconnections**: Implement exponential backoff for reconnections
3. **Validate data**: Always validate incoming data before processing
4. **Log errors**: Comprehensive error logging for debugging

### Security

1. **Use secure connections**: Always use WSS (WebSocket Secure) in production
2. **Authenticate connections**: Implement proper authentication for sensitive data
3. **Validate inputs**: Sanitize all user inputs and API responses
4. **Rate limit clients**: Implement rate limiting for WebSocket clients

## Troubleshooting

### Common Issues

**Connection timeouts**:
- Check network connectivity
- Verify WebSocket URL and parameters
- Increase timeout values in configuration

**High memory usage**:
- Reduce event history size
- Implement message cleanup
- Monitor buffer sizes

**Missing price updates**:
- Check provider status
- Verify symbol names
- Review rate limiting settings

**WebSocket disconnections**:
- Implement proper reconnection logic
- Check for rate limit violations
- Monitor connection health

### Debug Mode

Enable debug logging for troubleshooting:

```python
import logging
logging.getLogger('crypto_portfolio_analyzer.streaming').setLevel(logging.DEBUG)
```

## Examples

See the `examples/streaming/` directory for complete examples:

- `basic_monitoring.py`: Basic price monitoring
- `websocket_client.py`: WebSocket client implementation
- `portfolio_tracking.py`: Real-time portfolio tracking
- `custom_alerts.py`: Custom alert system
