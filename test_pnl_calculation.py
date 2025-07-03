import pandas as pd
from datetime import datetime

def test_pnl_calculations():
    """Test PnL calculations against actual CSV data"""
    
    # Read the CSV file
    df = pd.read_csv('Orders.csv')
    
    print("=== PNL CALCULATION TEST ===\n")
    
    # Convert timestamp to datetime
    df['Fill Time'] = pd.to_datetime(df['Fill Time'], format='%m/%d/%Y %H:%M:%S', errors='coerce')
    df['Date'] = pd.to_datetime(df['Date'], format='%m/%d/%Y', errors='coerce')
    
    # Sort by timestamp
    df = df.sort_values('Fill Time')
    
    # Filter only filled orders
    df = df[df['Status'].str.strip() == 'Filled']
    
    # Group by symbol and process FIFO
    symbols = df['Contract'].unique()
    
    for symbol in symbols:
        print(f"\n=== {symbol} ===")
        symbol_orders = df[df['Contract'] == symbol].sort_values('Fill Time')
        
        open_positions = []
        trades = []
        
        for idx, order in symbol_orders.iterrows():
            side = order['B/S'].strip()
            qty = float(order['filledQty'])
            price = float(order['avgPrice'])
            dt = order['Fill Time']
            oid = order['orderId']
            
            if pd.isna(dt):
                continue
                
            if side == 'Buy':
                open_positions.append({'qty': qty, 'price': price, 'time': dt, 'order_id': oid})
                print(f"  BUY: {dt.strftime('%H:%M:%S')} | Qty: {qty} | Price: {price:.2f} | Order: {oid}")
            elif side == 'Sell':
                qty_to_close = qty
                print(f"  SELL: {dt.strftime('%H:%M:%S')} | Qty: {qty} | Price: {price:.2f} | Order: {oid}")
                
                while qty_to_close > 0 and open_positions:
                    open_pos = open_positions[0]
                    close_qty = min(open_pos['qty'], qty_to_close)
                    
                    # Calculate PnL
                    pnl = (price - open_pos['price']) * close_qty
                    
                    trade_info = {
                        'entry_time': open_pos['time'],
                        'exit_time': dt,
                        'qty': close_qty,
                        'entry_price': open_pos['price'],
                        'exit_price': price,
                        'pnl': pnl,
                        'buy_order': open_pos['order_id'],
                        'sell_order': oid
                    }
                    trades.append(trade_info)
                    
                    print(f"    → Trade: Qty {close_qty} | Entry {open_pos['time'].strftime('%H:%M:%S')} @ {open_pos['price']:.2f} | Exit {dt.strftime('%H:%M:%S')} @ {price:.2f} | PnL: {pnl:.2f}")
                    
                    # Update open position
                    open_pos['qty'] -= close_qty
                    qty_to_close -= close_qty
                    if open_pos['qty'] == 0:
                        open_positions.pop(0)
        
        # Summary for this symbol
        if trades:
            total_pnl = sum(trade['pnl'] for trade in trades)
            print(f"\n  Total PnL for {symbol}: {total_pnl:.2f}")
            print(f"  Number of trades: {len(trades)}")
            
            # Show a few example calculations
            print("\n  Example calculations:")
            for i, trade in enumerate(trades[:3]):  # Show first 3 trades
                calc = f"({trade['exit_price']:.2f} - {trade['entry_price']:.2f}) × {trade['qty']} = {trade['pnl']:.2f}"
                print(f"    Trade {i+1}: {calc}")

if __name__ == "__main__":
    test_pnl_calculations() 