from app import db
from datetime import datetime

class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(20), nullable=False)
    entry_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    exit_date = db.Column(db.DateTime)
    entry_price = db.Column(db.Float, nullable=False)
    exit_price = db.Column(db.Float)
    position_size = db.Column(db.Float, nullable=False)
    direction = db.Column(db.String(10), nullable=False) # 'Long' or 'Short'
    strategy = db.Column(db.String(100))
    notes = db.Column(db.Text)
    pnl = db.Column(db.Float)

    def __repr__(self):
        return f"Trade('{self.ticker}', '{self.entry_date}')"

    @property
    def calculate_pnl(self):
        if self.exit_price and self.exit_date:
            if self.direction.lower() == 'long':
                return (self.exit_price - self.entry_price) * self.position_size
            else:
                return (self.entry_price - self.exit_price) * self.position_size
        return None 