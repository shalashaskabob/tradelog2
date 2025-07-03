import pandas as pd
from datetime import datetime, timedelta
import re

def analyze_order_patterns():
    # Read the CSV file
    df = pd.read_csv('Orders.csv')
    
    print("=== ORDER PATTERN ANALYSIS ===\n")
    
    # Convert timestamp to datetime
    df['Fill Time'] = pd.to_datetime(df['Fill Time'], format='%m/%d/%Y %H:%M:%S', errors='coerce')
    df['Date'] = pd.to_datetime(df['Date'], format='%m/%d/%Y', errors='coerce')
    
    # Sort by timestamp
    df = df.sort_values('Fill Time')
    
    print("1. ORDER ID ANALYSIS:")
    print("Unique Order IDs:", len(df['orderId'].unique()))
    print("Total rows:", len(df))
    print()
    
    print("2. TEXT FIELD ANALYSIS:")
    text_counts = df['Text'].value_counts()
    print(text_counts)
    print()
    
    print("3. QUANTITY ANALYSIS:")
    qty_counts = df['filledQty'].value_counts().sort_index()
    print(qty_counts)
    print()
    
    print("4. TIMING PATTERNS:")
    # Group by date and analyze timing within each day
    for date in df['Date'].unique():
        if pd.isna(date):
            continue
        day_orders = df[df['Date'] == date].sort_values('Fill Time')
        print(f"\nDate: {date.strftime('%m/%d/%Y')}")
        
        for i, (idx, order) in enumerate(day_orders.iterrows()):
            fill_time = order['Fill Time']
            if pd.isna(fill_time):
                fill_time_str = 'NaT'
            else:
                fill_time_str = fill_time.strftime('%H:%M:%S')
            print(f"  {i+1:2d}. {fill_time_str} | "
                  f"{str(order['B/S']).strip():4s} | "
                  f"Qty: {order['filledQty']} | "
                  f"Price: {order['avgPrice']} | "
                  f"Text: {str(order['Text']):12s} | "
                  f"OrderID: {order['orderId']}")
    
    print("\n5. FIFO TRADE MATCHING (REALISTIC LEDGER):")
    
    open_positions = []  # Each item: dict with qty, price, time
    closed_trades = []
    
    for idx, order in df.iterrows():
        side = str(order['B/S']).strip()
        qty = order['filledQty']
        price = order['avgPrice']
        time = order['Fill Time']
        if pd.isna(qty) or pd.isna(price) or pd.isna(time):
            continue
        qty = int(qty)
        if side == 'Buy':
            open_positions.append({'qty': qty, 'price': price, 'time': time})
        elif side == 'Sell':
            qty_to_close = qty
            while qty_to_close > 0 and open_positions:
                open_pos = open_positions[0]
                close_qty = min(open_pos['qty'], qty_to_close)
                trade = {
                    'entry_time': open_pos['time'],
                    'exit_time': time,
                    'qty': close_qty,
                    'entry_price': open_pos['price'],
                    'exit_price': price,
                    'pnl': (price - open_pos['price']) * close_qty
                }
                closed_trades.append(trade)
                open_pos['qty'] -= close_qty
                qty_to_close -= close_qty
                if open_pos['qty'] == 0:
                    open_positions.pop(0)
    print(f"Closed trades: {len(closed_trades)}")
    for i, trade in enumerate(closed_trades):
        print(f"Trade {i+1}: Qty {trade['qty']} | Entry {trade['entry_time'].strftime('%H:%M:%S')} @ {trade['entry_price']:.2f} | Exit {trade['exit_time'].strftime('%H:%M:%S')} @ {trade['exit_price']:.2f} | PnL: {trade['pnl']:.2f}")

if __name__ == "__main__":
    analyze_order_patterns() 