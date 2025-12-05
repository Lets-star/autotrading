# Bybit Testnet Mode Fix - Technical Notes

## Problem Statement

The BotDaemon was not respecting the `BYBIT_TESTNET` environment variable when set to `"1"` by the Streamlit app. This caused the daemon to create a mainnet private client even when testnet keys were configured, resulting in 401 authentication errors.

### Symptoms Observed

From the logs:
```
Environment: BYBIT_TESTNET=1
Settings: bybit_testnet=False  # ❌ WRONG - should be True
Creating mainnet private client...
Creating Bybit private mainnet client (endpoint: https://api.bybit.com)
Client created - testnet flag: False, endpoint attribute: https://api.bybit.com
Testnet mode: False
Private operations endpoint: Bybit Mainnet  # ❌ WRONG - should be Testnet
PositionTracker using session with endpoint: https://api.bybit.com
```

Then 401 errors occurred because testnet API keys don't work with mainnet endpoints.

## Root Cause

The issue was in how pydantic-settings parsed the `BYBIT_TESTNET` environment variable in `config.py`:

```python
class Settings(BaseSettings):
    bybit_testnet: bool = Field(False, description="Use Bybit testnet instead of mainnet")
```

While pydantic-settings should handle string-to-boolean conversion for common values like `"1"`, there may have been edge cases or version-specific behavior that caused the parsing to fail. The field needed an explicit validator to ensure robust parsing.

## Solution

### 1. Added Field Validator in config.py

Added a `@field_validator` decorator to the `bybit_testnet` field to explicitly handle string-to-boolean conversion:

```python
from pydantic import Field, field_validator
from typing import Any

class Settings(BaseSettings):
    bybit_testnet: bool = Field(False, description="Use Bybit testnet instead of mainnet")
    
    @field_validator('bybit_testnet', mode='before')
    @classmethod
    def parse_bybit_testnet(cls, v: Any) -> bool:
        """Parse BYBIT_TESTNET environment variable to boolean"""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ('true', '1', 'yes', 'on', 't', 'y')
        if isinstance(v, int):
            return bool(v)
        return False
```

This ensures:
- `"1"`, `"true"`, `"True"`, `"yes"`, `"on"` → `True`
- `"0"`, `"false"`, `"False"`, `"no"`, `"off"` → `False`
- Empty string or None → `False`
- Integer 1 → `True`, Integer 0 → `False`

### 2. Improved Logging in bybit_fetcher.py

When a pre-configured session is passed to BybitDataFetcher, the logs now show the actual endpoint of that session rather than inferring it from the testnet parameter:

```python
if session is not None:
    self.session = session
    # When using a pre-configured session, log its actual endpoint
    endpoint_attr = getattr(session, 'endpoint', None) or getattr(session, 'base_url', None) or getattr(session, '_endpoint', None)
    logger.info(f"BybitDataFetcher initialized with pre-configured session (endpoint: {endpoint_attr})")
else:
    # Create new session
    self.session = HTTP(testnet=testnet, api_key=api_key, api_secret=api_secret)
    endpoint = 'https://api-testnet.bybit.com' if testnet else 'https://api.bybit.com'
    logger.info(f"BybitDataFetcher initialized with testnet={testnet} (endpoint: {endpoint})")
```

This prevents misleading log messages when the fetcher's `testnet` parameter doesn't match the actual session endpoint.

## Expected Behavior After Fix

With testnet keys configured and `BYBIT_TESTNET=1`:

```
Environment: BYBIT_TESTNET=1
Settings: bybit_testnet=True  # ✓ CORRECT
Creating testnet private client...
Creating Bybit private testnet client (endpoint: https://api-testnet.bybit.com)
Client created - testnet flag: True, endpoint attribute: https://api-testnet.bybit.com
Testnet mode: True  # ✓ CORRECT
Public data endpoint: Bybit Mainnet  # ✓ Still uses mainnet for public data
Private operations endpoint: Bybit Testnet  # ✓ CORRECT
PositionTracker using session with endpoint: https://api-testnet.bybit.com
```

No 401 errors because testnet keys now match testnet endpoint.

## Testing

Three test scripts are provided:

1. **test_config_parsing.py**: Tests the field validator with various input formats
2. **test_testnet_mode.py**: Tests the full configuration flow
3. **test_daemon_testnet.py**: Integration test of BotDaemon initialization
4. **test_issue_reproduction.py**: Reproduces the exact issue and verifies the fix

Run them with:
```bash
python3 test_config_parsing.py
python3 test_testnet_mode.py
python3 test_daemon_testnet.py
python3 test_issue_reproduction.py
```

## Architecture Verification

The dual-client architecture is correctly implemented:

1. **Public Client (Mainnet)**: Created by `get_bybit_public_mainnet_client()`
   - No authentication
   - Always uses `https://api.bybit.com`
   - Used for market data: symbols, candles, orderbook
   - Assigned to `bot_daemon.public_fetcher`

2. **Private Client (Testnet/Mainnet)**: Created by `get_bybit_private_testnet_client()` or `get_bybit_private_mainnet_client()`
   - Requires authentication
   - Uses `https://api-testnet.bybit.com` OR `https://api.bybit.com` based on config
   - Used for private operations: positions, orders, trades
   - Assigned to `bot_daemon.private_fetcher`

The `bot_daemon.testnet` flag controls which private client factory is used (lines 74-87 in bot_daemon.py).

## Files Modified

1. **src/trading_bot/config.py**
   - Added `field_validator` import
   - Added `parse_bybit_testnet` validator method
   - Added `Any` type import

2. **src/trading_bot/data_feeds/bybit_fetcher.py**
   - Improved logging when using pre-configured session
   - Logs actual endpoint instead of inferring from parameter

## Backward Compatibility

These changes are fully backward compatible:
- Existing `.env` files with `BYBIT_TESTNET=true` still work
- Default value of `False` is unchanged
- Mainnet mode (testnet=False) continues to work as before
- All other configuration fields are unaffected

## Related Documentation

See also:
- **TESTNET_SETUP.md**: User guide for configuring testnet mode
- **src/trading_bot/bybit_clients.py**: Client factory functions
- **scripts/bot_daemon.py**: Daemon initialization logic
