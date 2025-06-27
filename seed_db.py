import random
import datetime
from app import create_app, db
from app.models import Trade, Strategy

app = create_app()

SYMBOLS = ['MNQ', 'NQ', 'MES', 'ES', 'GC', 'MGC']
STRATEGY_NAMES = ['Breakout', 'Mean Reversion', 'Scalp', 'Swing']
DIRECTIONS = ['Long', 'Short']


def get_or_create_strategy(name):
    strategy = Strategy.query.filter_by(name=name).first()
    if not strategy:
        strategy = Strategy(name=name)
        db.session.add(strategy)
        db.session.commit()
    return strategy

def random_trade(strategies):
    entry_date = datetime.datetime.utcnow() - datetime.timedelta(days=random.randint(0, 365))
    exit_date = entry_date + datetime.timedelta(hours=random.randint(1, 72))
    entry_price = round(random.uniform(100, 5000), 2)
    exit_price = round(entry_price + random.uniform(-100, 100), 2)
    position_size = random.randint(1, 5)
    direction = random.choice(DIRECTIONS)
    ticker = random.choice(SYMBOLS)
    
    trade = Trade(
        ticker=ticker,
        entry_date=entry_date,
        exit_date=exit_date,
        entry_price=entry_price,
        exit_price=exit_price,
        position_size=position_size,
        direction=direction,
        strategy=random.choice(strategies),
    )
    trade.pnl = trade.calculate_pnl
    return trade


if __name__ == '__main__':
    with app.app_context():
        # Clear existing data
        db.session.query(Trade).delete()
        db.session.query(Strategy).delete()
        print(f"Deleted existing trades and strategies.")
        
        db.create_all()

        # Create strategies
        strategies = []
        for name in STRATEGY_NAMES:
            strategies.append(get_or_create_strategy(name))
        print(f"Created {len(strategies)} strategies.")

        to_create = 50
        for _ in range(to_create):
            db.session.add(random_trade(strategies))
        db.session.commit()
        print(f"Added {to_create} trades (total now {Trade.query.count()}).") 