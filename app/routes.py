from flask import render_template, redirect, url_for, request, flash, Blueprint, jsonify
from flask_login import current_user, login_required
from app import db
from app.models import Trade, Strategy
from datetime import datetime
from app.forms import ChangePasswordForm

FUTURES_SYMBOLS = [
    'MNQ', 'NQ', 'MES', 'ES', 'RTY', 'M2K', 'CL', 'MCL', 'GC', 'MGC', 'SI', 
    'SIL', 'HG', 'PA', 'PL', 'ZB', 'ZN', 'ZF', 'ZT', 'GE', 'BTC', 'MBT'
]

bp = Blueprint('main', __name__)

@bp.route('/')
@bp.route('/index')
@login_required
def index():
    trades = Trade.query.filter_by(trader=current_user).order_by(Trade.entry_date.desc()).all()
    return render_template('index.html', title='Home', trades=trades)

@bp.route('/add_trade', methods=['GET', 'POST'])
@login_required
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
                exit_date=exit_date,
                trader=current_user
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
    strategies = Strategy.query.join(Trade).filter(Trade.user_id == current_user.id).distinct().all()
    return render_template(
        'add_trade.html',
        title='Add Trade',
        strategies=strategies,
        symbols=FUTURES_SYMBOLS,
    )

@bp.route('/delete_trade/<int:trade_id>', methods=['POST'])
@login_required
def delete_trade(trade_id):
    trade = Trade.query.get_or_404(trade_id)
    if trade.user_id != current_user.id:
        flash('You are not authorized to delete this trade.', 'danger')
        return redirect(url_for('main.index'))
    try:
        db.session.delete(trade)
        db.session.commit()
        flash('Trade deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting trade: {e}', 'danger')
    return redirect(url_for('main.index'))

@bp.route('/clear_log', methods=['POST'])
@login_required
def clear_log():
    try:
        num_rows_deleted = Trade.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        flash(f'Successfully deleted {num_rows_deleted} trades.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error clearing trade log: {e}', 'danger')
    return redirect(url_for('main.index'))

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
@login_required
def statistics():
    trades = Trade.query.filter_by(user_id=current_user.id).order_by(Trade.entry_date).all()
    if not trades:
        return render_template('statistics.html', title='Statistics', no_trades=True)

    # --- Basic Stats ---
    total_trades = len(trades)
    winning_trades = [t for t in trades if t.pnl is not None and t.pnl > 0]
    losing_trades = [t for t in trades if t.pnl is not None and t.pnl < 0]
    breakeven_trades = [t for t in trades if t.pnl is not None and t.pnl == 0]

    total_wins = len(winning_trades)
    total_losses = len(losing_trades)
    win_rate = (total_wins / total_trades) * 100 if total_trades > 0 else 0

    # --- PnL Stats ---
    all_pnl = [t.pnl for t in trades if t.pnl is not None]
    total_pnl = sum(all_pnl)
    gross_profit = sum(t.pnl for t in winning_trades)
    gross_loss = sum(t.pnl for t in losing_trades)
    
    if gross_loss != 0:
        profit_factor = abs(gross_profit / gross_loss)
    elif gross_profit > 0:
        profit_factor = 'Infinite'
    else:
        profit_factor = 'N/A'

    avg_win = gross_profit / total_wins if total_wins > 0 else 0
    avg_loss = gross_loss / total_losses if total_losses > 0 else 0
    largest_win = max(winning_trades, key=lambda t: t.pnl, default=None)
    largest_loss = min(losing_trades, key=lambda t: t.pnl, default=None)

    # --- Time & Direction Stats ---
    holding_times = [(t.exit_date - t.entry_date).total_seconds() for t in trades if t.exit_date]
    avg_holding_time_seconds = sum(holding_times) / len(holding_times) if holding_times else 0

    long_trades = [t for t in trades if t.direction == 'Long']
    short_trades = [t for t in trades if t.direction == 'Short']
    long_wins = sum(1 for t in long_trades if t.pnl is not None and t.pnl > 0)
    short_wins = sum(1 for t in short_trades if t.pnl is not None and t.pnl > 0)
    long_win_rate = (long_wins / len(long_trades)) * 100 if long_trades else 0
    short_win_rate = (short_wins / len(short_trades)) * 100 if short_trades else 0

    # -- Chart 1: Cumulative PnL ---
    cumulative_pnl = []
    current_pnl = 0
    dates = []
    for t in trades:
        ref_date = t.exit_date or t.entry_date
        dates.append(ref_date.strftime('%Y-%m-%d %H:%M'))
        if t.pnl is not None:
            current_pnl += t.pnl
        cumulative_pnl.append(current_pnl)

    # --- Chart 2: PnL by Symbol ---
    symbol_pnl = {}
    for t in trades:
        symbol_pnl.setdefault(t.ticker, 0)
        symbol_pnl[t.ticker] += t.pnl or 0
    symbol_names = list(symbol_pnl.keys())
    symbol_pnls = [round(v, 2) for v in symbol_pnl.values()]
    
    # --- Chart 3: PnL by Strategy ---
    strategy_pnl = {}
    for t in trades:
        strategy_pnl.setdefault(t.strategy.name, 0)
        strategy_pnl[t.strategy.name] += t.pnl or 0
    strategy_names = list(strategy_pnl.keys())
    strategy_pnls = [round(v, 2) for v in strategy_pnl.values()]

    # --- Chart 4: Trade Outcomes by Direction ---
    long_losses = len([t for t in long_trades if t.pnl is not None and t.pnl < 0])
    long_be = len([t for t in long_trades if t.pnl is not None and t.pnl == 0])
    short_losses = len([t for t in short_trades if t.pnl is not None and t.pnl < 0])
    short_be = len([t for t in short_trades if t.pnl is not None and t.pnl == 0])
    
    # --- Other ---
    from collections import Counter
    symbol_counts = Counter(t.ticker for t in trades)
    most_traded_symbol = symbol_counts.most_common(1)[0][0] if symbol_counts else 'N/A'


    return render_template(
        'statistics.html',
        title='Statistics',
        # Overall Performance
        total_trades=total_trades,
        win_rate=win_rate,
        total_pnl=total_pnl,
        profit_factor=profit_factor,
        # PnL Details
        avg_win=avg_win,
        avg_loss=avg_loss,
        largest_win=largest_win,
        largest_loss=largest_loss,
        # By Direction
        long_win_rate=long_win_rate,
        short_win_rate=short_win_rate,
        # Other
        avg_holding_time_seconds=avg_holding_time_seconds,
        most_traded_symbol=most_traded_symbol,
        # Chart Data
        dates=dates,
        cumulative_pnl=cumulative_pnl,
        symbol_names=symbol_names,
        symbol_pnls=symbol_pnls,
        strategy_names=strategy_names,
        strategy_pnls=strategy_pnls,
        # Direction Chart Data
        long_wins=long_wins,
        long_losses=long_losses,
        long_be=long_be,
        short_wins=short_wins,
        short_losses=short_losses,
        short_be=short_be
    ) 

@bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.check_password(form.current_password.data):
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash('Your password has been changed successfully.', 'success')
            return redirect(url_for('main.index'))
        else:
            flash('Invalid current password.', 'danger')
    return render_template('change_password.html', title='Change Password', form=form) 