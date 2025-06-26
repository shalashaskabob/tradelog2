from flask import render_template, redirect, url_for, request, flash, Blueprint
from app import db
from app.models import Trade
from datetime import datetime

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
            selected_strategy = request.form.get('strategy')
            strategy_value = None
            if selected_strategy == "__new__":
                # user provided new strategy in separate field
                strategy_value = request.form.get('strategy_new').strip() if request.form.get('strategy_new') else None
            else:
                strategy_value = selected_strategy

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
    return render_template('add_trade.html', title='Add Trade', strategies=strategies) 