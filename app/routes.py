from flask import render_template, redirect, url_for, request, flash, Blueprint, jsonify
from app import db
from app.models import Trade, Strategy
from datetime import datetime

FUTURES_SYMBOLS = [
    'MNQ', 'NQ', 'MES', 'ES', 'RTY', 'M2K', 'CL', 'MCL', 'GC', 'MGC', 'SI', 
    'SIL', 'HG', 'PA', 'PL', 'ZB', 'ZN', 'ZF', 'ZT', 'GE', 'BTC', 'MBT'
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

            # --- Strategy Handling ---
            strategy_name = request.form.get('strategy_choice')
            if strategy_name == '__new__':
                strategy_name = request.form.get('strategy_new_input')

            if not strategy_name:
                flash('Strategy name cannot be empty.', 'danger')
                return redirect(url_for('main.add_trade'))

            strategy = Strategy.query.filter_by(name=strategy_name).first()
            if not strategy:
                strategy = Strategy(name=strategy_name)
                db.session.add(strategy)
                # We don't commit here, let the trade commit handle it
            
            new_trade = Trade(
                ticker=request.form['ticker'],
                entry_date=entry_date,
                entry_price=float(request.form['entry_price']),
                position_size=float(request.form['position_size']),
                direction=request.form['direction'],
                strategy=strategy,
                notes=request.form.get('notes'),
                exit_date=exit_date
            )
            
            if request.form.get('exit_price'):
                new_trade.exit_price = float(request.form.get('exit_price'))
            
            # Set PnL using the model's calculation property
            new_trade.pnl = new_trade.calculate_pnl

            db.session.add(new_trade)
            db.session.commit()
            flash('Trade added successfully!', 'success')
            return redirect(url_for('main.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding trade: {e}', 'danger')

    # GET request - gather existing strategies
    strategies = Strategy.query.order_by(Strategy.name).all()
    return render_template(
        'add_trade.html',
        title='Add Trade',
        strategies=strategies,
        symbols=FUTURES_SYMBOLS,
    )

@bp.route('/add_strategy', methods=['POST'])
def add_strategy():
    data = request.get_json()
    if not data or 'name' not in data or not data['name'].strip():
        return jsonify({'success': False, 'message': 'Invalid strategy name.'}), 400
    
    name = data['name'].strip()
    
    if Strategy.query.filter_by(name=name).first():
        return jsonify({'success': False, 'message': 'Strategy already exists.'}), 409

    try:
        new_strategy = Strategy(name=name)
        db.session.add(new_strategy)
        db.session.commit()
        return jsonify({'success': True, 'id': new_strategy.id, 'name': new_strategy.name})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

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