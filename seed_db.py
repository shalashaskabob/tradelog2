import random
import datetime
from app import create_app, db
from app.models import Trade

app = create_app()

SYMBOLS = ['MNQ', 'NQ', 'MES', 'ES', 'GC', 'MGC']
STRATEGIES = ['Breakout', 'Mean Reversion', 'Scalp', 'Swing']
DIRECTIONS = ['Long', 'Short']


def random_trade():
    entry_date = datetime.datetime.utcnow() - datetime.timedelta(days=random.randint(0, 365))
    exit_date = entry_date + datetime.timedelta(hours=random.randint(1, 72))
    entry_price = round(random.uniform(100, 5000), 2)
    exit_price = round(entry_price + random.uniform(-100, 100), 2)
    position_size = random.randint(1, 5)
    direction = random.choice(DIRECTIONS)
    ticker = random.choice(SYMBOLS)
    strategy = random.choice(STRATEGIES)

    trade = Trade(
        ticker=ticker,
        entry_date=entry_date,
        exit_date=exit_date,
        entry_price=entry_price,
        exit_price=exit_price,
        position_size=position_size,
        direction=direction,
        strategy=strategy,
    )
    trade.pnl = trade.calculate_pnl
    return trade


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        count = Trade.query.count()
        to_create = max(0, 50 - count)
        for _ in range(to_create):
            db.session.add(random_trade())
        db.session.commit()
        print(f"Added {to_create} trades (total now {Trade.query.count()}).") 