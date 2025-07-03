import csv
import random
from datetime import datetime, timedelta
import uuid

# Configuration
NUM_TRADES = 50
NUM_ACCOUNTS = 20
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2025, 1, 1)

# Account names - TakeProfitTrader format
ACCOUNT_PREFIXES = [
    "TAKEPROFIT6215418", "TAKEPROFIT6215419", "TAKEPROFIT6215420", "TAKEPROFIT6215421", "TAKEPROFIT6215422",
    "TAKEPROFIT6215423", "TAKEPROFIT6215424", "TAKEPROFIT6215425", "TAKEPROFIT6215426", "TAKEPROFIT6215427",
    "TAKEPROFIT6215428", "TAKEPROFIT6215429", "TAKEPROFIT6215430", "TAKEPROFIT6215431", "TAKEPROFIT6215432",
    "TAKEPROFIT6215433", "TAKEPROFIT6215434", "TAKEPROFIT6215435", "TAKEPROFIT6215436", "TAKEPROFIT6215437"
]

# Trading instruments (only MNQ)
INSTRUMENTS = [
    ("MNQU5", "MNQ", "Micro E-mini NASDAQ-100")
]

# Price ranges for each instrument (min, max)
PRICE_RANGES = {
    "MNQU5": (22000, 24000)
}

def generate_random_date():
    """Generate a random date between START_DATE and END_DATE"""
    time_between = END_DATE - START_DATE
    days_between = time_between.days
    random_days = random.randrange(days_between)
    random_date = START_DATE + timedelta(days=random_days)
    
    # Add random time during trading hours (9:30 AM - 4:00 PM ET)
    hour = random.randint(9, 15)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    
    return random_date.replace(hour=hour, minute=minute, second=second)

def generate_order_id():
    """Generate a unique order ID"""
    return random.randint(245914870000, 245914879999)

def generate_price(instrument):
    """Generate a realistic price for the given instrument"""
    min_price, max_price = PRICE_RANGES[instrument]
    base_price = random.uniform(min_price, max_price)
    
    # Round to appropriate decimal places
    if instrument in ["MNQU5"]:
        return round(base_price, 2)
    else:
        return round(base_price, 2)

def generate_trade_pair():
    """Generate a buy/sell trade pair with realistic prices"""
    instrument, symbol, description = random.choice(INSTRUMENTS)
    account = random.choice(ACCOUNT_PREFIXES)
    
    # Generate entry price
    entry_price = generate_price(instrument)
    
    # Generate exit price (within reasonable range)
    price_variance = entry_price * random.uniform(-0.02, 0.02)  # ±2% variance
    exit_price = entry_price + price_variance
    
    # Ensure exit price is positive
    if exit_price <= 0:
        exit_price = entry_price * 0.98
    
    # Generate dates
    entry_date = generate_random_date()
    exit_date = entry_date + timedelta(minutes=random.randint(5, 480))  # 5 minutes to 8 hours
    
    # Generate quantities
    quantity = random.choice([1, 2, 3, 5, 10])
    
    # Generate order IDs
    buy_order_id = generate_order_id()
    sell_order_id = generate_order_id()
    
    # Create buy order
    buy_order = {
        'orderId': buy_order_id,
        'Account': account,
        'Order ID': buy_order_id,
        'B/S': ' Buy',
        'Contract': instrument,
        'Product': symbol,
        'Product Description': description,
        'avgPrice': entry_price,
        'filledQty': quantity,
        'Fill Time': entry_date.strftime('%m/%d/%Y %H:%M:%S'),
        'lastCommandId': buy_order_id,
        'Status': ' Filled',
        '_priceFormat': '-2',
        '_priceFormatType': '0',
        '_tickSize': '0.25',
        'spreadDefinitionId': '',
        'Version ID': buy_order_id,
        'Timestamp': entry_date.strftime('%m/%d/%Y %H:%M:%S'),
        'Date': entry_date.strftime('%m/%d/%y').lstrip('0').replace('/0', '/'),
        'Quantity': quantity,
        'Text': 'Tradingview',
        'Type': ' Market',
        'Limit Price': '',
        'Stop Price': '',
        'decimalLimit': '',
        'decimalStop': '',
        'Filled Qty': quantity,
        'Avg Fill Price': f"{entry_price:.2f}",
        'decimalFillAvg': entry_price
    }
    
    # Create sell order
    sell_order = {
        'orderId': sell_order_id,
        'Account': account,
        'Order ID': sell_order_id,
        'B/S': ' Sell',
        'Contract': instrument,
        'Product': symbol,
        'Product Description': description,
        'avgPrice': exit_price,
        'filledQty': quantity,
        'Fill Time': exit_date.strftime('%m/%d/%Y %H:%M:%S'),
        'lastCommandId': sell_order_id,
        'Status': ' Filled',
        '_priceFormat': '-2',
        '_priceFormatType': '0',
        '_tickSize': '0.25',
        'spreadDefinitionId': '',
        'Version ID': sell_order_id,
        'Timestamp': exit_date.strftime('%m/%d/%Y %H:%M:%S'),
        'Date': exit_date.strftime('%m/%d/%y').lstrip('0').replace('/0', '/'),
        'Quantity': quantity,
        'Text': 'Exit',
        'Type': ' Market',
        'Limit Price': '',
        'Stop Price': '',
        'decimalLimit': '',
        'decimalStop': '',
        'Filled Qty': quantity,
        'Avg Fill Price': f"{exit_price:.2f}",
        'decimalFillAvg': exit_price
    }
    
    return [buy_order, sell_order]

def main():
    """Generate the CSV file with simulated trades"""
    trades = []
    
    # Generate 200 trade pairs (400 total orders)
    for i in range(NUM_TRADES // 2):
        trade_pair = generate_trade_pair()
        trades.extend(trade_pair)
    
    # Sort trades by date
    trades.sort(key=lambda x: datetime.strptime(x['Fill Time'], '%m/%d/%Y %H:%M:%S'))
    
    # Write to CSV
    fieldnames = [
        'orderId', 'Account', 'Order ID', 'B/S', 'Contract', 'Product', 'Product Description',
        'avgPrice', 'filledQty', 'Fill Time', 'lastCommandId', 'Status', '_priceFormat',
        '_priceFormatType', '_tickSize', 'spreadDefinitionId', 'Version ID', 'Timestamp',
        'Date', 'Quantity', 'Text', 'Type', 'Limit Price', 'Stop Price', 'decimalLimit',
        'decimalStop', 'Filled Qty', 'Avg Fill Price', 'decimalFillAvg'
    ]
    
    with open('simulated_trades.csv', 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(trades)
    
    print(f"Generated {len(trades)} orders ({len(trades)//2} trades) across {NUM_ACCOUNTS} accounts")
    print("File saved as 'simulated_trades.csv'")
    
    # Print some statistics
    accounts_used = set(trade['Account'] for trade in trades)
    instruments_used = set(trade['Contract'] for trade in trades)
    
    print(f"\nStatistics:")
    print(f"- Accounts used: {len(accounts_used)}")
    print(f"- Instruments traded: {len(instruments_used)}")
    print(f"- Date range: {trades[0]['Date']} to {trades[-1]['Date']}")
    
    # Show sample of accounts
    print(f"\nSample accounts:")
    for account in sorted(list(accounts_used))[:5]:
        count = len([t for t in trades if t['Account'] == account])
        print(f"  {account}: {count} orders")

if __name__ == "__main__":
    main() 