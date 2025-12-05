# Bybit Testnet Configuration Guide

## Overview

The trading bot now supports Bybit testnet for safe testing without risking real funds. The bot uses a dual-client architecture:

- **Public data client**: Always uses Bybit mainnet for market data (symbols, candles, orderbook)
- **Private operations client**: Uses testnet or mainnet based on configuration for positions, orders, and trades

This approach allows you to test trading strategies on testnet while using real market data from mainnet.

## Setup Instructions

### 1. Get Bybit Testnet API Keys

1. Visit [Bybit Testnet](https://testnet.bybit.com/)
2. Create a testnet account or log in
3. Go to API Management
4. Create a new API key with the following permissions:
   - ✅ Account (Read)
   - ✅ Position (Read/Write)
   - ✅ Orders (Read/Write)
5. Save your API Key and API Secret

**Important**: Testnet API keys are different from mainnet keys and only work on testnet endpoints.

### 2. Configure Streamlit Secrets

Add your testnet credentials to your Streamlit secrets file (`~/.streamlit/secrets.toml` or `.streamlit/secrets.toml`):

```toml
[bybit_testnet]
api_key = "YOUR_TESTNET_API_KEY"
api_secret = "YOUR_TESTNET_API_SECRET"
```

### 3. Enable Testnet Mode

In the Streamlit app sidebar:
1. Check the "Use Bybit Testnet" checkbox
2. Click "🟢 Start Bot"

The bot daemon will now use your testnet credentials for all trading operations.

## Verification

When the bot starts with testnet enabled, check the logs (`logs/bot.log`) for:

```
BOT DAEMON STARTING
Configuration Summary:
  - Testnet mode: True
  - Public data endpoint: Bybit Mainnet
  - Private operations endpoint: Bybit Testnet
```

### Checking Endpoints

The logs will show which endpoint is being used for different operations:

```
Creating Bybit private testnet client (endpoint: https://api-testnet.bybit.com)
Testnet API key (first 8 chars): abcd1234...
Client created - testnet flag: True, endpoint attribute: https://api-testnet.bybit.com
```

## Troubleshooting

### Authentication Errors (401)

If you see `Authentication exception fetching positions` errors, check:

1. **API keys are correct**: Verify your testnet API key and secret in Streamlit secrets
2. **API key permissions**: Ensure your testnet API key has "Account" and "Position" read permissions
3. **Endpoint mismatch**: Don't use mainnet keys with testnet mode (or vice versa)
4. **IP whitelist**: If you set IP restrictions on your API key, make sure your current IP is whitelisted

### Daemon Not Using Testnet

If the logs show mainnet endpoints despite checking the testnet checkbox:

1. Verify the checkbox is checked before clicking "Start Bot"
2. Check that `BYBIT_TESTNET` environment variable is set to "1" in the logs
3. Restart the bot daemon (Stop, then Start)

## Environment Variables

The bot daemon reads the following environment variables (set automatically by the Streamlit app):

- `BYBIT_TESTNET`: Set to "1" to enable testnet mode, "0" for mainnet
- `BYBIT_TESTNET_API_KEY`: Your Bybit testnet API key
- `BYBIT_TESTNET_API_SECRET`: Your Bybit testnet API secret

You can also set these manually in a `.env` file for testing:

```bash
BYBIT_TESTNET=1
BYBIT_TESTNET_API_KEY=your_testnet_key
BYBIT_TESTNET_API_SECRET=your_testnet_secret
```

## Safety Features

- The daemon will not crash on authentication errors - it will log the error and continue running
- Error messages include detailed possible causes to help diagnose issues
- API keys are never logged in full - only the first 8 characters for verification
- The bot clearly shows which endpoint (testnet/mainnet) is being used in logs and status

## Getting Testnet Funds

1. Log in to [Bybit Testnet](https://testnet.bybit.com/)
2. Go to Assets
3. Use the testnet faucet to get free test USDT
4. You can now place test trades using the bot

## Switching Back to Mainnet

To switch back to real trading:

1. Uncheck the "Use Bybit Testnet" checkbox in the Streamlit app
2. Ensure you have mainnet API keys configured in `[bybit]` section of secrets.toml
3. Click "🟢 Start Bot"

The bot will now use mainnet for trading with real funds.
