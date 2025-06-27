from flask import render_template, redirect, url_for, request, flash, Blueprint
from app import db
from app.models import Trade
from datetime import datetime

FUTURES_SYMBOLS = [
    'MNQ', 'NQ', 'MES', 'ES', 'GC', 'MGC'
]

bp = Blueprint('main', __name__)

@bp.route('/')
@bp.route('/index')
def index():
    trades = Trade.query.order_by(Trade.entry_date.desc()).all()
    return render_template('index.html', title='Trade Log', trades=trades)

@bp.route('/add_trade', methods=['GET', 'POST'])
def add_trade():
    if request.method == 'POST':
        try:
            entry_date = datetime.strptime(request.form['entry_date'], '%Y-%m-%dT%H:%M')
            
            exit_date = None
            if request.form.get('exit_date'):
                exit_date = datetime.strptime(request.form['exit_date'], '%Y-%m-%dT%H:%M')

            # Determine strategy
            strategy_value = request.form.get('strategy_choice')

            # If the user clicks '+ Add New' but doesn't create one, this prevents an error
            if strategy_value == '__new__':
                strategy_value = request.form.get('strategy_new_input') or 'Unspecified'

            new_trade = Trade(
                ticker=request.form['ticker'],
                entry_date=entry_date,
                entry_price=float(request.form['entry_price']),
                position_size=float(request.form['position_size']),
                direction=request.form['direction'],
                strategy=strategy_value,
                notes=request.form.get('notes'),
                exit_date=exit_date
            )
            
            if request.form.get('exit_price'):
                new_trade.exit_price = float(request.form.get('exit_price'))
            
            # Calculate PnL before saving
            if new_trade.exit_price and new_trade.exit_date:
                if new_trade.direction.lower() == 'long':
                    new_trade.pnl = (new_trade.exit_price - new_trade.entry_price) * new_trade.position_size
                else:
                    new_trade.pnl = (new_trade.entry_price - new_trade.exit_price) * new_trade.position_size

            db.session.add(new_trade)
            db.session.commit()
            flash('Trade added successfully!', 'success')
            return redirect(url_for('main.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding trade: {e}', 'danger')

    # GET request - gather existing strategies for dropdown
    strategies = [row[0] for row in db.session.query(Trade.strategy).distinct().all() if row[0]]
    strategies.sort()
    return render_template(
        'add_trade.html',
        title='Add Trade',
        strategies=strategies,
        symbols=FUTURES_SYMBOLS,
    )

# ---------------------- Statistics ----------------------

@bp.route('/statistics')
def statistics():
    trades = Trade.query.order_by(Trade.entry_date).all()

    total = len(trades)
    winning = sum(1 for t in trades if t.pnl is not None and t.pnl > 0)
    losing = sum(1 for t in trades if t.pnl is not None and t.pnl < 0)
    win_rate = round((winning / total) * 100, 2) if total else 0
    avg_pnl = round(sum(t.pnl or 0 for t in trades) / total, 2) if total else 0

    cumulative = []
    cum = 0
    dates = []
    for t in trades:
        ref_date = t.exit_date or t.entry_date
        dates.append(ref_date.strftime('%Y-%m-%d'))
        if t.pnl is not None:
            cum += t.pnl
        cumulative.append(cum)

    # PnL by symbol
    symbol_dict = {}
    for t in trades:
        symbol_dict.setdefault(t.ticker, 0)
        symbol_dict[t.ticker] += t.pnl or 0

    symbol_names = list(symbol_dict.keys())
    symbol_pnls = [round(v, 2) for v in symbol_dict.values()]

    return render_template(
        'statistics.html',
        title='Statistics',
        total_trades=total,
        win_rate=win_rate,
        avg_pnl=avg_pnl,
        dates=dates,
        cumulative=cumulative,
        symbol_names=symbol_names,
        symbol_pnls=symbol_pnls,
    ) 