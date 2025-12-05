#!/usr/bin/env python3
"""
Reproduce the issue described in the ticket where testnet mode is not respected.

Expected behavior BEFORE fix:
- BYBIT_TESTNET='1' set in environment
- settings.bybit_testnet reads as False (BUG)
- BotDaemon creates mainnet private client
- 401 errors when using testnet keys

Expected behavior AFTER fix:
- BYBIT_TESTNET='1' set in environment
- settings.bybit_testnet reads as True (FIXED)
- BotDaemon creates testnet private client
- No 401 errors (keys match endpoint)
"""

import os
import sys

# Setup environment BEFORE importing settings
print("=" * 70)
print("ISSUE REPRODUCTION TEST")
print("=" * 70)
print("\nScenario: User has testnet keys and sets BYBIT_TESTNET='1'")
print()

# Simulate Streamlit app setting environment variables
os.environ['BYBIT_TESTNET'] = '1'  # This is what Streamlit app does
os.environ['BYBIT_TESTNET_API_KEY'] = 'testnet_key_12345678'
os.environ['BYBIT_TESTNET_API_SECRET'] = 'testnet_secret_12345678'

print("1. Environment variables set:")
print(f"   BYBIT_TESTNET = '{os.environ['BYBIT_TESTNET']}'")
print(f"   BYBIT_TESTNET_API_KEY = 'testnet_key_...'")
print(f"   BYBIT_TESTNET_API_SECRET = 'testnet_secret_...'")
print()

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import settings - this is where the bug would manifest
from trading_bot.config import settings

print("2. Config settings loaded:")
print(f"   settings.bybit_testnet = {settings.bybit_testnet}")
print(f"   Type: {type(settings.bybit_testnet)}")
print()

# Check if the bug is fixed
if settings.bybit_testnet is True:
    print("✓ PASS: settings.bybit_testnet correctly parsed as True")
    print()
    print("Expected daemon behavior:")
    print("  - Will create TESTNET private client")
    print("  - Endpoint: https://api-testnet.bybit.com")
    print("  - Will use testnet API keys")
    print("  - No 401 errors (keys match endpoint)")
    print()
    
elif settings.bybit_testnet is False:
    print("✗ FAIL: settings.bybit_testnet incorrectly parsed as False")
    print()
    print("This is the bug described in the ticket!")
    print("Expected daemon behavior (WRONG):")
    print("  - Would create MAINNET private client")
    print("  - Endpoint: https://api.bybit.com")
    print("  - Would use mainnet API keys (but testnet keys provided)")
    print("  - 401 errors (testnet keys don't work with mainnet endpoint)")
    print()
    sys.exit(1)
else:
    print(f"✗ UNEXPECTED: settings.bybit_testnet = {settings.bybit_testnet}")
    sys.exit(1)

# Test that BotDaemon would make the correct decision
print("3. Simulating BotDaemon initialization logic:")
testnet_flag = bool(settings.bybit_testnet)
print(f"   testnet_flag = bool(settings.bybit_testnet) = {testnet_flag}")
print()

if testnet_flag:
    print("   BotDaemon will execute:")
    print("     if self.testnet:")
    print("         logger.info('Creating testnet private client...')")
    print("         private_client = get_bybit_private_testnet_client(...)")
    print()
    print("✓ PASS: BotDaemon will create testnet private client")
else:
    print("   BotDaemon will execute:")
    print("     else:")
    print("         logger.info('Creating mainnet private client...')")
    print("         private_client = get_bybit_private_mainnet_client(...)")
    print()
    print("✗ FAIL: BotDaemon will incorrectly create mainnet private client")
    sys.exit(1)

print()
print("=" * 70)
print("✓ ISSUE FIXED")
print("=" * 70)
print()
print("The config.py field_validator now correctly parses BYBIT_TESTNET='1'")
print("to boolean True, ensuring BotDaemon respects testnet mode.")
print()
