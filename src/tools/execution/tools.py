"""
Simulated execution tools for Orch-xarc.

These tools simulate placing trades on Polymarket and Kalshi, allowing
the agent to demonstrate end-to-end execution of an arbitrage plan.
"""

from langchain_core.tools import tool

@tool
def exec_validate_wallet(platform: str) -> dict:
    """Simulate validating API keys, wallet connections, and available balances.
    
    Args:
        platform: The platform to validate ("polymarket" or "kalshi").
    """
    return {
        "status": "valid",
        "platform": platform,
        "balance_usd": 15000.00,
        "message": f"Wallet connected and funded on {platform.title()}."
    }

@tool
def exec_place_polymarket_order(side: str, quantity: int, price: float) -> dict:
    """Simulate placing a limit order on the Polymarket CLOB.
    
    Args:
        side: The outcome to buy ("Up" or "Down").
        quantity: Number of shares to buy.
        price: The limit price (e.g. 0.42).
    """
    cost = quantity * price
    return {
        "status": "success",
        "order_id": f"poly-ord-{hash(side + str(quantity)) % 100000}",
        "platform": "polymarket",
        "action": "buy",
        "outcome": side,
        "quantity": quantity,
        "price": price,
        "total_cost": cost,
        "message": f"Successfully placed order for {quantity} shares of {side} at ${price:.2f}."
    }

@tool
def exec_place_kalshi_order(side: str, strike: float, quantity: int, price: float) -> dict:
    """Simulate placing a limit order on Kalshi's Trade API.
    
    Args:
        side: The outcome to buy ("Yes" or "No").
        strike: The strike price of the market (e.g. 97500).
        quantity: Number of contracts to buy.
        price: The limit price in dollars (e.g. 0.52).
    """
    cost = quantity * price
    return {
        "status": "success",
        "order_id": f"kalshi-ord-{hash(side + str(strike)) % 100000}",
        "platform": "kalshi",
        "action": "buy",
        "outcome": side,
        "strike": strike,
        "quantity": quantity,
        "price": price,
        "total_cost": cost,
        "message": f"Successfully placed order for {quantity} {side} contracts at ${price:.2f}."
    }

@tool
def exec_verify_fill(order_id: str) -> dict:
    """Simulate verifying that an order has been fully filled.
    
    Args:
        order_id: The order ID returned from the placement tool.
    """
    import time
    # Simulate a tiny delay in the log (even though it's synchronous)
    return {
        "status": "filled",
        "order_id": order_id,
        "filled_quantity": "100%",
        "message": f"Order {order_id} has been completely filled."
    }

EXECUTION_TOOLS = [
    exec_validate_wallet,
    exec_place_polymarket_order,
    exec_place_kalshi_order,
    exec_verify_fill,
]
