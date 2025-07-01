from flask import render_template, redirect, url_for, request, flash, Blueprint, jsonify, send_from_directory, send_file
from flask_login import current_user, login_required
from app import db
from app.models import Trade, Strategy, User, Tag
from datetime import datetime, timedelta
from app.forms import ChangePasswordForm
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from calendar import monthrange
import calendar as cal
from io import BytesIO
import sys

FUTURES_SYMBOLS = [
    'MNQ', 'NQ', 'MES', 'ES', 'RTY', 'M2K', 'CL', 'MCL', 'GC', 'MGC', 'SI', 
    'SIL', 'HG', 'PA', 'PL', 'ZB', 'ZN', 'ZF', 'ZT', 'GE', 'BTC', 'MBT'
]

bp = Blueprint('main', __name__)

UPLOAD_FOLDER = '/var/data/uploads'
THUMB_SIZE = (150, 150)

@bp.route('/')
@bp.route('/index')
@login_required
def index():
    # Get filter parameters from request
    search_query = request.args.get('search', '').strip()
    symbol_filter = request.args.get('symbol', '').strip()
    strategy_filter = request.args.get('strategy', '').strip()
    direction_filter = request.args.get('direction', '').strip()
    pnl_filter = request.args.get('pnl', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    
    # Start with base query for current user's trades
    query = Trade.query.filter_by(user_id=current_user.id)
    
    # Apply filters
    if search_query:
        # Search in ticker and notes
        query = query.filter(
            db.or_(
                Trade.ticker.ilike(f'%{search_query}%'),
                Trade.notes.ilike(f'%{search_query}%')
            )
        )
    
    if symbol_filter:
        query = query.filter(Trade.ticker == symbol_filter)
    
    if strategy_filter:
        query = query.join(Strategy).filter(Strategy.name == strategy_filter)
    
    if direction_filter:
        query = query.filter(Trade.direction == direction_filter)
    
    if pnl_filter:
        if pnl_filter == 'profit':
            query = query.filter(Trade.pnl > 0)
        elif pnl_filter == 'loss':
            query = query.filter(Trade.pnl < 0)
        elif pnl_filter == 'breakeven':
            query = query.filter(Trade.pnl == 0)
        elif pnl_filter == 'open':
            query = query.filter(Trade.pnl.is_(None))
    
    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Trade.entry_date >= start_datetime)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
            # Add 23:59:59 to include the entire end date
            end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
            query = query.filter(Trade.entry_date <= end_datetime)
        except ValueError:
            pass
    
    # Get filtered trades
    trades = query.order_by(Trade.entry_date.desc()).all()
    
    # Get filter options for the form
    user_strategies = Strategy.query.filter_by(user_id=current_user.id).order_by(Strategy.name).all()
    user_symbols = db.session.query(Trade.ticker).filter_by(user_id=current_user.id).distinct().order_by(Trade.ticker).all()
    user_symbols = [symbol[0] for symbol in user_symbols]
    
    return render_template('index.html', 
                         title='Home', 
                         trades=trades,
                         search_query=search_query,
                         symbol_filter=symbol_filter,
                         strategy_filter=strategy_filter,
                         direction_filter=direction_filter,
                         pnl_filter=pnl_filter,
                         start_date=start_date,
                         end_date=end_date,
                         symbols=FUTURES_SYMBOLS,
                         user_symbols=user_symbols,
                         strategies=user_strategies)

@bp.route('/uploads/<path:filepath>')
def uploaded_file(filepath):
    # Serve files from persistent storage
    return send_from_directory(UPLOAD_FOLDER, filepath)

@bp.route('/add_trade', methods=['GET', 'POST'])
@login_required
def add_trade():
    if request.method == 'POST':
        try:
            entry_date = datetime.strptime(request.form['entry_date'], '%Y-%m-%dT%H:%M')
            exit_date = None
            if request.form.get('exit_date'):
                exit_date = datetime.strptime(request.form['exit_date'], '%Y-%m-%dT%H:%M')
            strategy_name = request.form.get('strategy_choice')
            if strategy_name == '__new__':
                strategy_name = request.form.get('strategy_new_input')
            if not strategy_name:
                flash('Strategy name cannot be empty.', 'danger')
                return redirect(url_for('main.add_trade'))
            strategy = Strategy.query.filter_by(name=strategy_name, user_id=current_user.id).first()
            if not strategy:
                strategy = Strategy(name=strategy_name, user_id=current_user.id)
                db.session.add(strategy)
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
            new_trade.pnl = new_trade.calculate_pnl
            # Handle tags
            tag_names = request.form.getlist('tags')
            new_tag_names = [t.strip() for t in request.form.get('new_tags', '').split(',') if t.strip()]
            all_tag_names = set(tag_names + new_tag_names)
            tags = []
            for tag_name in all_tag_names:
                tag = Tag.query.filter_by(name=tag_name, user_id=current_user.id).first()
                if not tag:
                    tag = Tag(name=tag_name, user_id=current_user.id)
                    db.session.add(tag)
                tags.append(tag)
            new_trade.tags = tags
            db.session.add(new_trade)
            db.session.flush()  # Get trade.id before commit
            # --- Screenshot upload logic ---
            file = request.files.get('screenshot')
            if file and file.filename:
                user_id = current_user.id
                trade_id = new_trade.id
                trade_folder = os.path.join(UPLOAD_FOLDER, str(user_id), str(trade_id))
                os.makedirs(trade_folder, exist_ok=True)
                ext = os.path.splitext(file.filename)[1].lower()
                img_filename = f'screenshot{ext}'
                img_path = os.path.join(trade_folder, img_filename)
                file.save(img_path)
                thumb_filename = f'thumb{ext}'
                thumb_path = os.path.join(trade_folder, thumb_filename)
                with Image.open(img_path) as img:
                    img.thumbnail(THUMB_SIZE)
                    img.save(thumb_path)
                new_trade.screenshot = f'{user_id}/{trade_id}/{img_filename}'
            db.session.commit()
            flash('Trade added successfully!', 'success')
            return redirect(url_for('main.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding trade: {e}', 'danger')
    strategies = Strategy.query.filter_by(user_id=current_user.id).order_by(Strategy.name).all()
    user_tags = Tag.query.filter_by(user_id=current_user.id).order_by(Tag.name).all()
    return render_template(
        'add_trade.html',
        title='Add Trade',
        strategies=strategies,
        symbols=FUTURES_SYMBOLS,
        user_tags=user_tags
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
@login_required
def add_strategy():
    data = request.get_json()
    if not data or 'name' not in data or not data['name'].strip():
        return jsonify({'success': False, 'message': 'Invalid strategy name.'}), 400
    name = data['name'].strip()
    # User-specific strategy
    if Strategy.query.filter_by(name=name, user_id=current_user.id).first():
        return jsonify({'success': False, 'message': 'Strategy already exists.'}), 409
    try:
        new_strategy = Strategy(name=name, user_id=current_user.id)
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
    trades = Trade.query.filter_by(user_id=current_user.id).all()
    if not trades:
        return render_template('statistics.html', title='Statistics', no_trades=True)

    # Sort trades by execution date (exit_date if present, else entry_date)
    trades_sorted = sorted(trades, key=lambda t: t.exit_date or t.entry_date)

    # --- Basic Stats ---
    total_trades = len(trades_sorted)
    winning_trades = [t for t in trades_sorted if t.pnl is not None and t.pnl > 0]
    losing_trades = [t for t in trades_sorted if t.pnl is not None and t.pnl < 0]
    breakeven_trades = [t for t in trades_sorted if t.pnl is not None and t.pnl == 0]

    total_wins = len(winning_trades)
    total_losses = len(losing_trades)
    win_rate = (total_wins / total_trades) * 100 if total_trades > 0 else 0

    # --- PnL Stats ---
    all_pnl = [t.pnl for t in trades_sorted if t.pnl is not None]
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
    holding_times = [(t.exit_date - t.entry_date).total_seconds() for t in trades_sorted if t.exit_date]
    avg_holding_time_seconds = sum(holding_times) / len(holding_times) if holding_times else 0

    long_trades = [t for t in trades_sorted if t.direction == 'Long']
    short_trades = [t for t in trades_sorted if t.direction == 'Short']
    long_wins = sum(1 for t in long_trades if t.pnl is not None and t.pnl > 0)
    short_wins = sum(1 for t in short_trades if t.pnl is not None and t.pnl > 0)
    long_win_rate = (long_wins / len(long_trades)) * 100 if long_trades else 0
    short_win_rate = (short_wins / len(short_trades)) * 100 if short_trades else 0

    # -- Chart 1: Cumulative PnL ---
    cumulative_pnl = []
    current_pnl = 0
    dates = []
    for t in trades_sorted:
        ref_date = t.exit_date or t.entry_date
        dates.append(ref_date.strftime('%Y-%m-%d %H:%M'))
        if t.pnl is not None:
            current_pnl += t.pnl
        cumulative_pnl.append(current_pnl)

    # --- Chart 2: PnL by Symbol ---
    symbol_pnl = {}
    for t in trades_sorted:
        symbol_pnl.setdefault(t.ticker, 0)
        symbol_pnl[t.ticker] += t.pnl or 0
    symbol_names = list(symbol_pnl.keys())
    symbol_pnls = [round(v, 2) for v in symbol_pnl.values()]
    
    # --- Chart 3: PnL by Strategy ---
    strategy_pnl = {}
    for t in trades_sorted:
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
    symbol_counts = Counter(t.ticker for t in trades_sorted)
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
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'danger')
            return redirect(url_for('main.change_password'))
        
        current_user.set_password(form.new_password.data)
        db.session.commit()
        flash('Your password has been changed.', 'success')
        return redirect(url_for('main.index'))
    
    return render_template('change_password.html', title='Change Password', form=form)

@bp.route('/admin')
@login_required
def admin_dashboard():
    """Admin dashboard to view user statistics."""
    # Check if user is admin
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    # Get user statistics
    total_users = User.query.count()
    active_users = User.query.join(Trade).distinct().count()
    inactive_users = total_users - active_users
    
    # Get users with their trade counts
    users = db.session.query(
        User.id, 
        User.username, 
        User.is_admin,
        db.func.count(Trade.id).label('trade_count')
    ).outerjoin(Trade).group_by(User.id, User.username, User.is_admin).order_by(User.id).all()
    
    # Get recent registrations (last 10 users)
    recent_users = User.query.order_by(User.id.desc()).limit(10).all()
    
    return render_template(
        'admin_dashboard.html',
        title='Admin Dashboard',
        total_users=total_users,
        active_users=active_users,
        inactive_users=inactive_users,
        users=users,
        recent_users=recent_users
    ) 

@bp.route('/edit_trade/<int:trade_id>', methods=['GET', 'POST'])
@login_required
def edit_trade(trade_id):
    trade = Trade.query.get_or_404(trade_id)
    if trade.user_id != current_user.id:
        flash('You are not authorized to edit this trade.', 'danger')
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        try:
            trade.ticker = request.form['ticker']
            trade.entry_date = datetime.strptime(request.form['entry_date'], '%Y-%m-%dT%H:%M')
            trade.entry_price = float(request.form['entry_price'])
            trade.position_size = float(request.form['position_size'])
            trade.direction = request.form['direction']
            trade.exit_date = datetime.strptime(request.form['exit_date'], '%Y-%m-%dT%H:%M') if request.form.get('exit_date') else None
            trade.exit_price = float(request.form['exit_price']) if request.form.get('exit_price') else None
            trade.notes = request.form.get('notes')
            strategy_name = request.form.get('strategy_choice')
            if strategy_name == '__new__':
                strategy_name = request.form.get('strategy_new_input')
            if not strategy_name:
                flash('Strategy name cannot be empty.', 'danger')
                return redirect(url_for('main.edit_trade', trade_id=trade.id))
            strategy = Strategy.query.filter_by(name=strategy_name, user_id=current_user.id).first()
            if not strategy:
                strategy = Strategy(name=strategy_name, user_id=current_user.id)
                db.session.add(strategy)
            trade.strategy = strategy
            # Handle tags
            tag_names = request.form.getlist('tags')
            new_tag_names = [t.strip() for t in request.form.get('new_tags', '').split(',') if t.strip()]
            all_tag_names = set(tag_names + new_tag_names)
            tags = []
            for tag_name in all_tag_names:
                tag = Tag.query.filter_by(name=tag_name, user_id=current_user.id).first()
                if not tag:
                    tag = Tag(name=tag_name, user_id=current_user.id)
                    db.session.add(tag)
                tags.append(tag)
            trade.tags = tags
            # Screenshot update
            file = request.files.get('screenshot')
            if file and file.filename:
                user_id = current_user.id
                trade_id = trade.id
                trade_folder = os.path.join(UPLOAD_FOLDER, str(user_id), str(trade_id))
                os.makedirs(trade_folder, exist_ok=True)
                ext = os.path.splitext(file.filename)[1].lower()
                img_filename = f'screenshot{ext}'
                img_path = os.path.join(trade_folder, img_filename)
                file.save(img_path)
                thumb_filename = f'thumb{ext}'
                thumb_path = os.path.join(trade_folder, thumb_filename)
                with Image.open(img_path) as img:
                    img.thumbnail(THUMB_SIZE)
                    img.save(thumb_path)
                trade.screenshot = f'{user_id}/{trade_id}/{img_filename}'
            trade.pnl = trade.calculate_pnl
            db.session.commit()
            flash('Trade updated successfully!', 'success')
            return redirect(url_for('main.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating trade: {e}', 'danger')
    strategies = Strategy.query.filter_by(user_id=current_user.id).order_by(Strategy.name).all()
    user_tags = Tag.query.filter_by(user_id=current_user.id).order_by(Tag.name).all()
    return render_template(
        'add_trade.html',
        title='Edit Trade',
        strategies=strategies,
        symbols=FUTURES_SYMBOLS,
        trade=trade,
        edit_mode=True,
        user_tags=user_tags
    ) 

@bp.route('/delete_strategy/<int:strategy_id>', methods=['POST'])
@login_required
def delete_strategy(strategy_id):
    # Only get the strategy for the current user
    strategy = Strategy.query.filter_by(id=strategy_id, user_id=current_user.id).first_or_404()
    # Only allow deletion if no trades (from the current user) reference this strategy
    trade_exists = Trade.query.filter_by(strategy_id=strategy.id, user_id=current_user.id).first()
    if trade_exists:
        flash('Cannot delete a strategy that is in use by your trades.', 'danger')
        return redirect(url_for('main.index'))
    db.session.delete(strategy)
    db.session.commit()
    flash('Strategy deleted successfully.', 'success')
    return redirect(url_for('main.index'))

@bp.route('/calendar')
@login_required
def calendar():
    from datetime import datetime, timedelta, date
    # Get month/year from query params or default to current
    year = request.args.get('year', type=int) or datetime.now().year
    month = request.args.get('month', type=int) or datetime.now().month
    # Get all trades for the user in this month
    start_date = date(year, month, 1)
    last_day = monthrange(year, month)[1]
    end_date = date(year, month, last_day)
    trades = Trade.query.filter(
        Trade.user_id == current_user.id,
        Trade.entry_date >= start_date,
        Trade.entry_date < end_date + timedelta(days=1)
    ).all()
    # Aggregate PnL by day
    daily_pnl = {}
    daily_trades = {}
    for t in trades:
        d = t.entry_date.date()
        daily_pnl.setdefault(d, 0)
        daily_trades.setdefault(d, []).append(t)
        daily_pnl[d] += t.pnl or 0
    # Aggregate PnL by week (ISO week)
    week_pnl = {}
    for d, pnl in daily_pnl.items():
        week = d.isocalendar()[1]
        week_pnl.setdefault(week, 0)
        week_pnl[week] += pnl
    # Prepare calendar grid
    cal_grid = cal.monthcalendar(year, month)
    # Build a mapping from (year, month, day) to date object
    calendar_cells = {}
    for week in cal_grid:
        for day in week:
            if day != 0:
                calendar_cells[(year, month, day)] = date(year, month, day)
    return render_template('calendar.html',
        title='PnL Calendar',
        year=year,
        month=month,
        cal_grid=cal_grid,
        daily_pnl=daily_pnl,
        daily_trades=daily_trades,
        week_pnl=week_pnl,
        month_name=start_date.strftime('%B'),
        calendar_cells=calendar_cells) 

@bp.route('/share_trade/<int:trade_id>')
@login_required
def share_trade(trade_id):
    trade = Trade.query.get_or_404(trade_id)
    if trade.user_id != current_user.id:
        flash('You are not authorized to share this trade.', 'danger')
        return redirect(url_for('main.index'))

    # Use pre-designed card background as-is (no masking needed)
    # Use absolute path based on current file location for Render compatibility
    current_dir = os.path.dirname(os.path.abspath(__file__))
    bg_path = os.path.join(current_dir, 'static', 'card_bg.png')
    with Image.open(bg_path).convert('RGBA') as base_img:
        card = base_img.copy()
    width, height = card.size

    # Load Roboto font (log error if not found)
    # Use absolute path based on current file location for Render compatibility
    current_dir = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(current_dir, 'static', 'fonts', 'Roboto-VariableFont_wdth,wght.ttf')
    try:
        font_title = ImageFont.truetype(font_path, 64)
        font_label = ImageFont.truetype(font_path, 36)
        font_value = ImageFont.truetype(font_path, 48)
        font_pnl = ImageFont.truetype(font_path, 96)
        font_small = ImageFont.truetype(font_path, 28)
    except Exception as e:
        print(f"[ERROR] Could not load Roboto font: {e}", file=sys.stderr)
        font_title = font_label = font_value = font_pnl = font_small = ImageFont.load_default()

    draw = ImageDraw.Draw(card)

    # Helper for text size (Pillow >=8.0)
    def get_text_size(font, text):
        bbox = font.getbbox(text)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    # Centered layout variables
    center_x = width // 2
    top_margin = 250  # Estimated lion logo height + padding
    y = top_margin

    # TRADELOG branding (centered top, below lion logo)
    title_text = "TRADELOG"
    title_w, title_h = get_text_size(font_title, title_text)
    draw.text((center_x - title_w//2, y), title_text, font=font_title, fill='#f7b32b')
    y += title_h + 10  # 10px spacing
    y += 20  # Move ticker and badge 20px lower

    # Ticker and badge (centered, badge to right or below if needed)
    ticker_text = trade.ticker
    # Increase ticker font size
    font_value_large = ImageFont.truetype(font_path, 60)
    ticker_w, ticker_h = get_text_size(font_value_large, ticker_text)
    badge_text = trade.direction.capitalize()
    badge_color = (0, 212, 170, 255) if badge_text == 'Long' else (255, 107, 107, 255)
    # Increase badge font size
    font_badge = ImageFont.truetype(font_path, 44)
    badge_text_w, badge_text_h = get_text_size(font_badge, badge_text)
    badge_padding_x = 36  # horizontal padding inside badge
    badge_padding_y = 16  # vertical padding inside badge
    badge_w = badge_text_w + badge_padding_x
    badge_h = badge_text_h + badge_padding_y
    badge_gap = 20
    badge_x_right = center_x + ticker_w//2 + badge_gap
    badge_x_left = badge_x_right
    badge_y = y + (ticker_h - badge_h) // 2
    badge_fits = badge_x_right + badge_w < width - 20  # 20px right margin
    if badge_fits:
        # Draw ticker
        draw.text((center_x - ticker_w//2, y), ticker_text, font=font_value_large, fill='#fff')
        # Draw badge to right of ticker
        badge = Image.new('RGBA', (badge_w, badge_h), (0,0,0,0))
        badge_draw = ImageDraw.Draw(badge)
        badge_draw.rounded_rectangle([(0,0),(badge_w,badge_h)], radius=badge_h//2, fill=badge_color)
        card.paste(badge, (int(badge_x_left), int(badge_y)), badge)
        draw.text((badge_x_left + (badge_w-badge_text_w)//2, badge_y + (badge_h-badge_text_h)//2), badge_text, font=font_badge, fill='#fff')
        y += max(ticker_h, badge_h) + 30  # 30px spacing
    else:
        # Draw ticker centered
        draw.text((center_x - ticker_w//2, y), ticker_text, font=font_value_large, fill='#fff')
        y += ticker_h + 10
        # Draw badge centered below ticker
        badge_x_center = center_x - badge_w//2
        badge_y = y
        badge = Image.new('RGBA', (badge_w, badge_h), (0,0,0,0))
        badge_draw = ImageDraw.Draw(badge)
        badge_draw.rounded_rectangle([(0,0),(badge_w,badge_h)], radius=badge_h//2, fill=badge_color)
        card.paste(badge, (int(badge_x_center), int(badge_y)), badge)
        draw.text((badge_x_center + (badge_w-badge_text_w)//2, badge_y + (badge_h-badge_text_h)//2), badge_text, font=font_badge, fill='#fff')
        y += badge_h + 30  # 30px spacing

    # Large PnL (centered, colored)
    pnl_color = '#00d4aa' if trade.pnl and trade.pnl > 0 else '#ff6b6b' if trade.pnl and trade.pnl < 0 else '#fff'
    pnl_text = f"{trade.pnl if trade.pnl is not None else '-'}"
    pnl_label = "PnL"
    pnl_label_w, pnl_label_h = get_text_size(font_label, pnl_label)
    pnl_text_w, pnl_text_h = get_text_size(font_pnl, pnl_text)
    draw.text((center_x - pnl_label_w//2, y), pnl_label, font=font_label, fill='#b0b0b0')
    y += pnl_label_h + 8  # slightly more spacing
    draw.text((center_x - pnl_text_w//2, y), pnl_text, font=font_pnl, fill=pnl_color)
    y += pnl_text_h + 36  # more spacing before prices

    # Entry/Exit price (two columns, centered below PnL)
    price_y = y
    col_gap = 120
    col1_x = center_x - col_gap
    col2_x = center_x + col_gap
    entry_label = "Entry Price"
    exit_label = "Exit Price"
    entry_label_w, entry_label_h = get_text_size(font_label, entry_label)
    exit_label_w, exit_label_h = get_text_size(font_label, exit_label)
    entry_val = f"{trade.entry_price}"
    exit_val = f"{trade.exit_price if trade.exit_price is not None else '-'}"
    entry_val_w, entry_val_h = get_text_size(font_value, entry_val)
    exit_val_w, exit_val_h = get_text_size(font_value, exit_val)
    # Draw labels
    draw.text((col1_x - entry_label_w//2, price_y), entry_label, font=font_label, fill='#b0b0b0')
    draw.text((col2_x - exit_label_w//2, price_y), exit_label, font=font_label, fill='#b0b0b0')
    # Draw values
    draw.text((col1_x - entry_val_w//2, price_y + entry_label_h + 8), entry_val, font=font_value, fill='#fff')
    draw.text((col2_x - exit_val_w//2, price_y + exit_label_h + 8), exit_val, font=font_value, fill='#fff')
    # Increment y by the height of label + value + spacing
    y = price_y + entry_label_h + max(entry_val_h, exit_val_h) + 32

    # Strategy and date (bottom center)
    bottom_y = height - 80
    strat_text = f"Strategy: {trade.strategy.name if trade.strategy else '-'}"
    date_text = f"Date: {trade.entry_date.strftime('%Y-%m-%d')}"
    strat_w, strat_h = get_text_size(font_small, strat_text)
    date_w, date_h = get_text_size(font_small, date_text)
    draw.text((center_x - strat_w//2, bottom_y), strat_text, font=font_small, fill='#b0b0b0')
    draw.text((center_x - date_w//2, bottom_y+strat_h+4), date_text, font=font_small, fill='#b0b0b0')

    # Screenshot thumbnail (bottom right, above logo)
    if trade.screenshot:
        screenshot_path = os.path.join(UPLOAD_FOLDER, trade.screenshot.replace('\\', '/'))
        if os.path.exists(screenshot_path):
            try:
                with Image.open(screenshot_path) as img:
                    img.thumbnail((80, 80))
                    screenshot_mask = Image.new('L', (80, 80), 0)
                    screenshot_mask_draw = ImageDraw.Draw(screenshot_mask)
                    screenshot_mask_draw.rounded_rectangle([(0, 0), (80, 80)], radius=12, fill=255)
                    img.putalpha(screenshot_mask)
                    card.paste(img, (card.width-110, card.height-130), img)
            except Exception as e:
                pass

    # Output to BytesIO
    img_io = BytesIO()
    # Save as PNG with alpha preserved
    card.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png', as_attachment=False, download_name=f'trade_{trade.id}_card.png') 

@bp.route('/shared/<int:trade_id>')
def shared_card(trade_id):
    trade = Trade.query.get_or_404(trade_id)
    card_url = url_for('main.share_trade', trade_id=trade.id, _external=True)
    share_url = request.url.replace('http://', 'https://')
    return render_template('shared_card.html', card_url=card_url, share_url=share_url) 

@bp.route('/top_trades')
@login_required
def top_trades():
    today = datetime.utcnow().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    trades = (
        Trade.query
        .join(User, Trade.user_id == User.id)
        .filter(User.show_on_top_trades == True)
        .filter(Trade.exit_date >= start_of_week)
        .filter(Trade.exit_date <= end_of_week)
        .order_by(Trade.pnl.desc())
        .limit(10)
        .all()
    )
    return render_template('top_trades.html', trades=trades) 

@bp.route('/update_top_trades_optin', methods=['POST'])
@login_required
def update_top_trades_optin():
    show = bool(request.form.get('show_on_top_trades'))
    current_user.show_on_top_trades = show
    from app import db
    db.session.commit()
    flash('Top Trades opt-in updated.', 'success')
    return redirect(url_for('main.index')) 

@bp.route('/share_trade/<int:trade_id>.png')
@login_required
def share_trade_png(trade_id):
    trade = Trade.query.get_or_404(trade_id)
    # Only allow if the trade's user has opted in to the leaderboard
    if not getattr(trade.trader, 'show_on_top_trades', False):
        flash('You are not authorized to share this trade.', 'danger')
        return redirect(url_for('main.index'))

    # Path to save PNG
    save_dir = os.path.join('var', 'data', 'trade_cards')
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, f"trade_{trade.id}.png")

    # If file exists, serve it
    if os.path.exists(save_path):
        return send_file(save_path, mimetype='image/png', as_attachment=False, download_name=f'trade_{trade.id}_card.png')

    current_dir = os.path.dirname(os.path.abspath(__file__))
    bg_path = os.path.join(current_dir, 'static', 'card_bg.png')
    with Image.open(bg_path).convert('RGBA') as base_img:
        card = base_img.copy()
    width, height = card.size
    font_path = os.path.join(current_dir, 'static', 'fonts', 'Roboto-VariableFont_wdth,wght.ttf')
    try:
        font_title = ImageFont.truetype(font_path, 64)
        font_label = ImageFont.truetype(font_path, 36)
        font_value = ImageFont.truetype(font_path, 48)
        font_pnl = ImageFont.truetype(font_path, 96)
        font_small = ImageFont.truetype(font_path, 28)
    except Exception as e:
        print(f"[ERROR] Could not load Roboto font: {e}", file=sys.stderr)
        font_title = font_label = font_value = font_pnl = font_small = ImageFont.load_default()
    draw = ImageDraw.Draw(card)
    def get_text_size(font, text):
        bbox = font.getbbox(text)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    center_x = width // 2
    top_margin = 240
    y = top_margin
    title_text = "TRADELOG"
    title_w, title_h = get_text_size(font_title, title_text)
    draw.text((center_x - title_w//2, y), title_text, font=font_title, fill='#f7b32b')
    y += title_h + 10
    y += 20
    ticker_text = trade.ticker
    font_value_large = ImageFont.truetype(font_path, 60)
    ticker_w, ticker_h = get_text_size(font_value_large, ticker_text)
    badge_text = trade.direction.capitalize()
    badge_color = (0, 212, 170, 255) if badge_text == 'Long' else (255, 107, 107, 255)
    font_badge = ImageFont.truetype(font_path, 44)
    badge_text_w, badge_text_h = get_text_size(font_badge, badge_text)
    badge_padding_x = 36
    badge_padding_y = 16
    badge_w = badge_text_w + badge_padding_x
    badge_h = badge_text_h + badge_padding_y
    badge_gap = 20
    badge_x_right = center_x + ticker_w//2 + badge_gap
    badge_x_left = badge_x_right
    badge_y = y + (ticker_h - badge_h) // 2
    badge_fits = badge_x_right + badge_w < width - 20
    if badge_fits:
        draw.text((center_x - ticker_w//2, y), ticker_text, font=font_value_large, fill='#fff')
        badge = Image.new('RGBA', (badge_w, badge_h), (0,0,0,0))
        badge_draw = ImageDraw.Draw(badge)
        badge_draw.rounded_rectangle([(0,0),(badge_w,badge_h)], radius=badge_h//2, fill=badge_color)
        card.paste(badge, (int(badge_x_left), int(badge_y)), badge)
        draw.text((badge_x_left + (badge_w-badge_text_w)//2, badge_y + (badge_h-badge_text_h)//2), badge_text, font=font_badge, fill='#fff')
        y += max(ticker_h, badge_h) + 30
    else:
        draw.text((center_x - ticker_w//2, y), ticker_text, font=font_value_large, fill='#fff')
        y += ticker_h + 10
        badge_x_center = center_x - badge_w//2
        badge_y = y
        badge = Image.new('RGBA', (badge_w, badge_h), (0,0,0,0))
        badge_draw = ImageDraw.Draw(badge)
        badge_draw.rounded_rectangle([(0,0),(badge_w,badge_h)], radius=badge_h//2, fill=badge_color)
        card.paste(badge, (int(badge_x_center), int(badge_y)), badge)
        draw.text((badge_x_center + (badge_w-badge_text_w)//2, badge_y + (badge_h-badge_text_h)//2), badge_text, font=font_badge, fill='#fff')
        y += badge_h + 30
    pnl_color = '#00d4aa' if trade.pnl and trade.pnl > 0 else '#ff6b6b' if trade.pnl and trade.pnl < 0 else '#fff'
    pnl_text = f"{trade.pnl if trade.pnl is not None else '-'}"
    pnl_label = "PnL"
    pnl_label_w, pnl_label_h = get_text_size(font_label, pnl_label)
    pnl_text_w, pnl_text_h = get_text_size(font_pnl, pnl_text)
    draw.text((center_x - pnl_label_w//2, y), pnl_label, font=font_label, fill='#b0b0b0')
    y += pnl_label_h + 8
    draw.text((center_x - pnl_text_w//2, y), pnl_text, font=font_pnl, fill=pnl_color)
    y += pnl_text_h + 36
    price_y = y
    col_gap = 120
    col1_x = center_x - col_gap
    col2_x = center_x + col_gap
    entry_label = "Entry Price"
    exit_label = "Exit Price"
    entry_label_w, entry_label_h = get_text_size(font_label, entry_label)
    exit_label_w, exit_label_h = get_text_size(font_label, exit_label)
    entry_val = f"{trade.entry_price}"
    exit_val = f"{trade.exit_price if trade.exit_price is not None else '-'}"
    entry_val_w, entry_val_h = get_text_size(font_value, entry_val)
    exit_val_w, exit_val_h = get_text_size(font_value, exit_val)
    draw.text((col1_x - entry_label_w//2, price_y), entry_label, font=font_label, fill='#b0b0b0')
    draw.text((col2_x - exit_label_w//2, price_y), exit_label, font=font_label, fill='#b0b0b0')
    draw.text((col1_x - entry_val_w//2, price_y + entry_label_h + 8), entry_val, font=font_value, fill='#fff')
    draw.text((col2_x - exit_val_w//2, price_y + exit_label_h + 8), exit_val, font=font_value, fill='#fff')
    y = price_y + entry_label_h + max(entry_val_h, exit_val_h) + 32
    bottom_y = height - 80
    strat_text = f"Strategy: {trade.strategy.name if trade.strategy else '-'}"
    date_text = f"Date: {trade.entry_date.strftime('%Y-%m-%d')}"
    strat_w, strat_h = get_text_size(font_small, strat_text)
    date_w, date_h = get_text_size(font_small, date_text)
    draw.text((center_x - strat_w//2, bottom_y), strat_text, font=font_small, fill='#b0b0b0')
    draw.text((center_x - date_w//2, bottom_y+strat_h+4), date_text, font=font_small, fill='#b0b0b0')
    # Save PNG to disk
    card.save(save_path, 'PNG')
    return send_file(save_path, mimetype='image/png', as_attachment=False, download_name=f'trade_{trade.id}_card.png') 