#!/usr/bin/env python3
"""
Test script to verify multi-buy/multi-sell import logic
"""

import csv
from collections import defaultdict
from datetime import datetime

def test_multi_buy_sell_logic():
    """Test the multi-buy/multi-sell import logic"""
    
    print("Testing Multi-Buy/Multi-Sell Import Logic")
    print("=" * 50)
    
    # Read the CSV file
    with open('Orders.csv', 'r') as file:
        csv_reader = csv.DictReader(file)
        
        # Group orders by date and symbol
        trades_by_date_symbol = defaultdict(list)
        
        for row in csv_reader:
            try:
                # Only process filled orders
                if row.get('Status', '').strip() != 'Filled':
                    continue
                    
                symbol = row.get('Contract', '')
                side = row.get('B/S', '').strip()
                quantity = row.get('filledQty', '')
                price = row.get('avgPrice', '')
                date_str = row.get('Date', '')
                fill_time = row.get('Fill Time', '')
                
                if not all([symbol, side, quantity, price, date_str]):
                    continue
                
                # Parse date
                try:
                    trade_date = datetime.strptime(date_str, '%m/%d/%y')
                except ValueError:
                    continue
                
                # Parse time if available
                try:
                    if fill_time:
                        time_part = fill_time.split(' ')[1] if ' ' in fill_time else fill_time
                        time_obj = datetime.strptime(time_part, '%H:%M:%S').time()
                        trade_date = trade_date.replace(hour=time_obj.hour, minute=time_obj.minute, second=time_obj.second)
                except:
                    pass
                
                trades_by_date_symbol[(trade_date.date(), symbol)].append({
                    'side': side,
                    'quantity': float(quantity),
                    'price': float(price),
                    'datetime': trade_date,
                    'order_id': row.get('orderId', '')
                })
                
            except (ValueError, KeyError) as e:
                continue
        
        print(f"Found {len(trades_by_date_symbol)} symbol/date groups")
        print()
        
        # Process each symbol/date group
        for (date, symbol), orders in trades_by_date_symbol.items():
            if len(orders) < 2:
                continue
            
            # Sort orders by time
            orders.sort(key=lambda x: x['datetime'])
            
            # Group into buy/sell orders
            buys = [o for o in orders if o['side'] == 'Buy']
            sells = [o for o in orders if o['side'] == 'Sell']
            
            if not buys or not sells:
                continue
            
            print(f"Processing {symbol} on {date}:")
            print(f"  Buys: {len(buys)}, Sells: {len(sells)}")
            
            # Track remaining buy quantities for partial sells
            remaining_buys = buys.copy()
            
            # Process each sell order
            for sell_idx, sell in enumerate(sells):
                # Find all buy orders that happened before this sell and still have remaining quantity
                valid_buys = [buy for buy in remaining_buys if buy['datetime'] < sell['datetime']]
                
                if not valid_buys:
                    continue
                
                # Calculate weighted average entry price and total available position
                total_available_quantity = sum(buy['quantity'] for buy in valid_buys)
                weighted_avg_price = sum(buy['price'] * buy['quantity'] for buy in valid_buys) / total_available_quantity
                
                # Determine how much to sell
                sell_quantity = min(total_available_quantity, sell['quantity'])
                
                # Calculate PnL
                pnl = (sell['price'] - weighted_avg_price) * sell_quantity
                
                print(f"    Trade {sell_idx + 1}: {len(valid_buys)} buys -> 1 sell")
                print(f"      Buys: {[(buy['quantity'], buy['price']) for buy in valid_buys]}")
                print(f"      Sell: {sell['quantity']} @ {sell['price']}")
                print(f"      Weighted Avg Entry: {weighted_avg_price:.2f}")
                print(f"      PnL: ${pnl:.2f}")
                
                # Update remaining buy quantities (for partial sells)
                remaining_quantity_to_allocate = sell_quantity
                
                # Allocate the sell quantity across the buy orders (FIFO)
                for buy in valid_buys:
                    if remaining_quantity_to_allocate <= 0:
                        break
                        
                    if buy['quantity'] <= remaining_quantity_to_allocate:
                        # This buy is fully consumed
                        remaining_quantity_to_allocate -= buy['quantity']
                        if buy in remaining_buys:
                            remaining_buys.remove(buy)
                    else:
                        # This buy is partially consumed
                        buy['quantity'] -= remaining_quantity_to_allocate
                        remaining_quantity_to_allocate = 0
                
                print()

if __name__ == "__main__":
    test_multi_buy_sell_logic() 