from app import db
from datetime import datetime

class Strategy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

    def __repr__(self):
        return f"Strategy('{self.name}')"

class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(20), nullable=False)
    entry_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    exit_date = db.Column(db.DateTime)
    entry_price = db.Column(db.Float, nullable=False)
    exit_price = db.Column(db.Float)
    position_size = db.Column(db.Float, nullable=False)
    direction = db.Column(db.String(10), nullable=False) # 'Long' or 'Short'
    strategy_id = db.Column(db.Integer, db.ForeignKey('strategy.id'), nullable=False)
    strategy = db.relationship('Strategy', backref=db.backref('trades', lazy=True))
    notes = db.Column(db.Text)
    pnl = db.Column(db.Float, default=0)

    TICKER_POINT_VALUES = {
        'MNQ': 2,
        'NQ': 20,
        'MES': 5,
        'ES': 50,
        'RTY': 5,
        'M2K': 5,
        'CL': 1000,
        'MCL': 100,
        'GC': 100,
        'MGC': 10,
        'SI': 5000,
        'SIL': 1000,
        'HG': 25000,
        'PA': 100,
        'PL': 50,
        'ZB': 1000,
        'ZN': 1000,
        'ZF': 1000,
        'ZT': 1000,
        'GE': 2500,
        'BTC': 5,
        'MBT': 0.1,
    }

    def __repr__(self):
        return f"Trade('{self.ticker}', '{self.entry_date}')"

    @property
    def calculate_pnl(self):
        if self.exit_price is not None and self.exit_date is not None:
            point_value = self.TICKER_POINT_VALUES.get(self.ticker.upper(), 1)
            if self.direction.lower() == 'long':
                return (self.exit_price - self.entry_price) * self.position_size * point_value
            else:
                return (self.entry_price - self.exit_price) * self.position_size * point_value
        return 0 