#!/bin/bash
# Quick validation script to verify the testnet mode fix

echo "=========================================="
echo "Validating Bybit Testnet Mode Fix"
echo "=========================================="
echo ""

cd "$(dirname "$0")"

# Check that the key files were modified
echo "1. Checking modified files..."
if grep -q "field_validator" src/trading_bot/config.py; then
    echo "   ✓ config.py contains field_validator"
else
    echo "   ✗ config.py missing field_validator"
    exit 1
fi

if grep -q "pre-configured session" src/trading_bot/data_feeds/bybit_fetcher.py; then
    echo "   ✓ bybit_fetcher.py has improved logging"
else
    echo "   ✗ bybit_fetcher.py missing logging improvements"
    exit 1
fi

echo ""
echo "2. Running issue reproduction test..."
python3 test_issue_reproduction.py
if [ $? -eq 0 ]; then
    echo "   ✓ Issue reproduction test passed"
else
    echo "   ✗ Issue reproduction test failed"
    exit 1
fi

echo ""
echo "3. Running testnet mode test..."
python3 test_testnet_mode.py
if [ $? -eq 0 ]; then
    echo "   ✓ Testnet mode test passed"
else
    echo "   ✗ Testnet mode test failed"
    exit 1
fi

echo ""
echo "=========================================="
echo "✓ All validations passed!"
echo "=========================================="
echo ""
echo "The fix is working correctly:"
echo "  • BYBIT_TESTNET='1' is parsed as boolean True"
echo "  • BotDaemon will create testnet private client"
echo "  • Logs accurately show endpoints being used"
echo ""
