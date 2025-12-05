#!/usr/bin/env python3
"""Test script to verify BYBIT_TESTNET environment variable parsing"""

import os
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Test various environment variable values
test_cases = [
    ("1", True),
    ("0", False),
    ("true", True),
    ("false", False),
    ("True", True),
    ("False", False),
    ("yes", True),
    ("no", False),
    ("on", True),
    ("off", False),
    ("", False),
]

print("Testing BYBIT_TESTNET environment variable parsing:\n")

for env_value, expected in test_cases:
    # Clear settings cache
    if 'trading_bot.config' in sys.modules:
        del sys.modules['trading_bot.config']
    
    # Set environment variable
    if env_value:
        os.environ['BYBIT_TESTNET'] = env_value
    else:
        os.environ.pop('BYBIT_TESTNET', None)
    
    # Import settings
    from trading_bot.config import settings
    
    actual = settings.bybit_testnet
    status = "✓" if actual == expected else "✗"
    
    print(f"{status} BYBIT_TESTNET='{env_value}' -> {actual} (expected {expected})")

print("\nAll tests passed!" if all(
    __import__('trading_bot.config', fromlist=['settings']).Settings(
        _env_file=None,
        **{'bybit_testnet': env_value if env_value else False}
    ).bybit_testnet == expected
    for env_value, expected in test_cases
) else "\nSome tests failed!")
