import pandas as pd
from datetime import datetime
import re

def parse_tradovate_orders_csv(file_path):
    """Parse Tradovate Orders CSV format"""
    df = pd.read_csv(file_path)
    
    # Clean column names and data
    df.columns = df.columns.str.strip()
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].str.strip()
    
    # Filter only filled orders (note the leading space)
    df = df[df['Status'] == ' Filled'].copy()
    
    # Parse date and time
    df['datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Fill Time'], format='%m/%d/%y %H:%M:%S')
    
    # Convert price and quantity to numeric
    df['avgPrice'] = pd.to_numeric(df['avgPrice'])
    df['filledQty'] = pd.to_numeric(df['filledQty'])
    
    # Clean B/S column
    df['B/S'] = df['B/S'].str.strip()
    
    return df

def calculate_pnl_with_commissions(df):
    """Calculate PnL using FIFO method with commission tracking"""
    trades = []
    open_positions = []  # List of (quantity, avg_price, datetime) tuples
    total_commission = 0
    
    # Commission rate: $0.25 per contract per side
    COMMISSION_PER_CONTRACT = 0.25
    
    for _, row in df.iterrows():
        quantity = row['filledQty']
        price = row['avgPrice']
        side = row['B/S']
        dt = row['datetime']
        
        # Calculate commission for this order
        order_commission = quantity * COMMISSION_PER_CONTRACT
        total_commission += order_commission
        
        if side == ' Buy':
            # Add to open positions
            open_positions.append((quantity, price, dt))
            print(f"BUY: {quantity} @ {price} (commission: ${order_commission:.2f})")
            
        elif side == ' Sell':
            # Match against open positions using FIFO
            remaining_sell_qty = quantity
            total_cost = 0
            total_qty = 0
            matched_positions = []
            
            while remaining_sell_qty > 0 and open_positions:
                pos_qty, pos_price, pos_dt = open_positions[0]
                
                if pos_qty <= remaining_sell_qty:
                    # Use entire position
                    matched_qty = pos_qty
                    open_positions.pop(0)
                else:
                    # Use partial position
                    matched_qty = remaining_sell_qty
                    open_positions[0] = (pos_qty - remaining_sell_qty, pos_price, pos_dt)
                
                total_cost += matched_qty * pos_price
                total_qty += matched_qty
                remaining_sell_qty -= matched_qty
                matched_positions.append((matched_qty, pos_price, pos_dt))
            
            if total_qty > 0:
                avg_entry_price = total_cost / total_qty
                pnl = (price - avg_entry_price) * total_qty * 2  # MNQ multiplier
                
                # Subtract commission for this trade (both buy and sell sides)
                trade_commission = total_qty * COMMISSION_PER_CONTRACT * 2
                net_pnl = pnl - trade_commission
                
                trades.append({
                    'entry_time': matched_positions[0][2],
                    'exit_time': dt,
                    'quantity': total_qty,
                    'entry_price': avg_entry_price,
                    'exit_price': price,
                    'pnl': pnl,
                    'commission': trade_commission,
                    'net_pnl': net_pnl
                })
                
                print(f"SELL: {total_qty} @ {price} (entry: {avg_entry_price:.2f}, PnL: ${pnl:.2f}, commission: ${trade_commission:.2f}, net: ${net_pnl:.2f})")
    
    return trades, total_commission

def main():
    # Parse the CSV
    df = parse_tradovate_orders_csv('Orders.csv')
    print(f"Parsed {len(df)} filled orders")
    print(f"Date range: {df['datetime'].min()} to {df['datetime'].max()}")
    print()
    
    # Calculate PnL with commissions
    trades, total_commission = calculate_pnl_with_commissions(df)
    
    print(f"\n=== RESULTS ===")
    print(f"Total trades: {len(trades)}")
    
    total_pnl = sum(t['pnl'] for t in trades)
    total_net_pnl = sum(t['net_pnl'] for t in trades)
    
    print(f"Total gross PnL: ${total_pnl:.2f}")
    print(f"Total commission: ${total_commission:.2f}")
    print(f"Total net PnL: ${total_net_pnl:.2f}")
    
    # Show individual trades
    print(f"\n=== INDIVIDUAL TRADES ===")
    for i, trade in enumerate(trades, 1):
        print(f"Trade {i}: {trade['quantity']} contracts, Entry: {trade['entry_price']:.2f}, Exit: {trade['exit_price']:.2f}, PnL: ${trade['net_pnl']:.2f}")
    
    # Expected PnL calculation
    print(f"\n=== EXPECTED PnL ===")
    print(f"Starting balance: $25,000.00")
    print(f"Ending balance: $23,882.50")
    print(f"Expected PnL: ${23882.50 - 25000:.2f}")
    print(f"Difference from calculated: ${(23882.50 - 25000) - total_net_pnl:.2f}")

if __name__ == "__main__":
    main() 