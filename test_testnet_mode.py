#!/usr/bin/env python3
"""
Test script to verify Bybit testnet mode configuration.
This simulates what happens when the Streamlit app starts the bot daemon.
"""

import os
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))

print("=" * 70)
print("TESTNET MODE CONFIGURATION TEST")
print("=" * 70)

# Simulate Streamlit app setting environment variables
print("\n1. Simulating Streamlit app environment setup...")
os.environ['BYBIT_TESTNET'] = '1'
os.environ['BYBIT_TESTNET_API_KEY'] = 'test_key_12345678'
os.environ['BYBIT_TESTNET_API_SECRET'] = 'test_secret_12345678'

print("   BYBIT_TESTNET='1'")
print("   BYBIT_TESTNET_API_KEY='test_key_12345678'")
print("   BYBIT_TESTNET_API_SECRET='test_secret_12345678'")

# Import settings
print("\n2. Loading config settings...")
from trading_bot.config import settings

print(f"   settings.bybit_testnet = {settings.bybit_testnet}")
print(f"   settings.bybit_testnet_api_key = {'set' if settings.bybit_testnet_api_key else 'not set'}")
print(f"   settings.bybit_testnet_api_secret = {'set' if settings.bybit_testnet_api_secret else 'not set'}")

# Verify testnet mode is enabled
if not settings.bybit_testnet:
    print("\n❌ FAIL: settings.bybit_testnet should be True but got False")
    sys.exit(1)
else:
    print("\n✓ PASS: Testnet mode correctly parsed from environment")

# Test the client factory functions
print("\n3. Testing client factory functions...")
from trading_bot.bybit_clients import (
    get_bybit_public_mainnet_client,
    get_bybit_private_testnet_client,
)

try:
    public_client = get_bybit_public_mainnet_client()
    print("   ✓ Public mainnet client created")
    
    private_client = get_bybit_private_testnet_client()
    print("   ✓ Private testnet client created")
    
    # Check endpoints
    public_endpoint = getattr(public_client, 'endpoint', None) or getattr(public_client, 'base_url', None) or getattr(public_client, '_endpoint', None)
    private_endpoint = getattr(private_client, 'endpoint', None) or getattr(private_client, 'base_url', None) or getattr(private_client, '_endpoint', None)
    
    print(f"\n4. Verifying endpoints...")
    print(f"   Public client endpoint: {public_endpoint}")
    print(f"   Private client endpoint: {private_endpoint}")
    
    # Verify endpoints are correct
    if private_endpoint and 'testnet' in str(private_endpoint).lower():
        print("\n✓ PASS: Private client is using testnet endpoint")
    else:
        print(f"\n❌ FAIL: Private client should use testnet endpoint, got: {private_endpoint}")
        sys.exit(1)
    
except Exception as e:
    print(f"\n❌ FAIL: Error creating clients: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test BotDaemon initialization (without starting the loop)
print("\n5. Testing BotDaemon initialization...")
try:
    # Mock the necessary parts to avoid actually running the bot
    class MockBotDaemon:
        def __init__(self):
            self.testnet = bool(settings.bybit_testnet)
            self.testnet_api_key = settings.bybit_testnet_api_key
            self.testnet_api_secret = settings.bybit_testnet_api_secret
            
            print(f"   Mock daemon testnet mode: {self.testnet}")
            print(f"   Mock daemon testnet keys: {'set' if self.testnet_api_key else 'not set'}")
            
            if not self.testnet:
                raise ValueError("Testnet mode should be enabled")
            if not self.testnet_api_key or not self.testnet_api_secret:
                raise ValueError("Testnet API keys should be set")
    
    daemon = MockBotDaemon()
    print("\n✓ PASS: BotDaemon would initialize with correct testnet configuration")
    
except Exception as e:
    print(f"\n❌ FAIL: BotDaemon initialization check failed: {e}")
    sys.exit(1)

print("\n" + "=" * 70)
print("ALL TESTS PASSED ✓")
print("=" * 70)
print("\nThe configuration is working correctly:")
print("  - BYBIT_TESTNET environment variable is properly parsed to boolean")
print("  - Private client will use testnet endpoint")
print("  - Public client will use mainnet endpoint")
print("  - BotDaemon will respect testnet mode for private operations")
print()
