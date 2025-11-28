def calculate_realized_pnl(entry_price: float, exit_price: float, qty: float, side: str, fees: float = 0.0) -> float:
    """
    Calculate realized PnL for a trade, accounting for commissions.
    side: 'buy' (Long) or 'sell' (Short) refers to the OPENING direction.
    Wait, usually side refers to the trade side.
    If I Bought to Open (Long), and Sell to Close.
    
    If side is the direction of the trade (Long/Short):
    Long: (Exit - Entry) * Qty - Fees
    Short: (Entry - Exit) * Qty - Fees
    """
    if side.lower() in ['buy', 'long']:
        gross_pnl = (exit_price - entry_price) * qty
    elif side.lower() in ['sell', 'short']:
        gross_pnl = (entry_price - exit_price) * qty
    else:
        raise ValueError(f"Invalid side: {side}")
        
    return gross_pnl - fees
