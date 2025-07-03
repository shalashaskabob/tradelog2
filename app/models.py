from app import db, login
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

# Association table for many-to-many relationship between Trade and Tag
trade_tags = db.Table('trade_tags',
    db.Column('trade_id', db.Integer, db.ForeignKey('trade.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

@login.user_loader
def load_user(id):
    return User.query.get(int(id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False)
    show_on_top_trades = db.Column(db.Boolean, default=False)
    trades = db.relationship('Trade', backref='trader', lazy='dynamic')
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Strategy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('name', 'user_id', name='_user_strategy_uc'),)
    user = db.relationship('User', backref=db.backref('strategies', lazy='dynamic'))

    def __repr__(self):
        return f"Strategy('{self.name}')"

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('tags', lazy='dynamic'))
    trades = db.relationship('Trade', secondary=trade_tags, back_populates='tags')

    def __repr__(self):
        return f'<Tag {self.name}>'

class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(20), nullable=False)
    account = db.Column(db.String(100), nullable=False, default='Default')
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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    screenshot = db.Column(db.String(256))  # stores filename or path
    tags = db.relationship('Tag', secondary=trade_tags, back_populates='trades')

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

class TradovateCredentials(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    username = db.Column(db.String(100), nullable=False)
    access_token = db.Column(db.String(500))
    refresh_token = db.Column(db.String(500))
    token_expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('tradovate_credentials', lazy='dynamic'))
    
    def __repr__(self):
        return f'<TradovateCredentials {self.username}>' 