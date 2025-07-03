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
            db.session.add(new_trade)  # Add to session before assigning tags
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
        # Get all trade IDs for this user
        trade_ids = [t.id for t in Trade.query.filter_by(user_id=current_user.id).all()]
        
        # Delete trade-tag associations first
        if trade_ids:
            from app.models import trade_tags
            db.session.execute(
                trade_tags.delete().where(trade_tags.c.trade_id.in_(trade_ids))
            )
        
        # Delete all trades for this user
        num_rows_deleted = Trade.query.filter_by(user_id=current_user.id).delete()
        
        db.session.commit()
        flash(f'Successfully deleted {num_rows_deleted} trades and all associated tags.', 'success')
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
    
    # Online users: last_seen within 10 minutes (exclude NULL values)
    ten_minutes_ago = datetime.utcnow() - timedelta(minutes=10)
    online_users = User.query.filter(
        User.last_seen.isnot(None),
        User.last_seen >= ten_minutes_ago
    ).count()
    
    return render_template(
        'admin_dashboard.html',
        title='Admin Dashboard',
        total_users=total_users,
        active_users=active_users,
        inactive_users=inactive_users,
        users=users,
        recent_users=recent_users,
        online_users=online_users
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
    title_text = "KINGLINE"
    title_w, title_h = get_text_size(font_title, title_text)
    draw.text((center_x - title_w//2, y), title_text, font=font_title, fill='#f7b32b')
    y += title_h + 10  # 10px spacing
    y += 20  # Move ticker and badge 20px lower

    # Ticker and badge (centered, badge to right or below if needed)
    ticker_text = trade.ticker
    font_value_large = ImageFont.truetype(font_path, 60)
    ticker_w, ticker_h = get_text_size(font_value_large, ticker_text)
    badge_text = trade.direction.capitalize()
    badge_color = (0, 212, 170, 255) if badge_text == 'Long' else (255, 107, 107, 255)
    font_badge = ImageFont.truetype(font_path, 44)
    badge_text_w, badge_text_h = get_text_size(font_badge, badge_text)
    badge_padding_x = 36  # horizontal padding inside badge
    badge_padding_y = 16  # vertical padding inside badge
    badge_w = badge_text_w + badge_padding_x
    badge_h = badge_text_h + badge_padding_y
    badge_gap = 20
    # Calculate the total width of ticker + gap + badge
    total_w = ticker_w + badge_gap + badge_w
    ticker_x = center_x - total_w // 2
    badge_x = ticker_x + ticker_w + badge_gap
    badge_y = y + (ticker_h - badge_h) // 2
    badge_fits = badge_x + badge_w < width - 20
    if badge_fits:
        # Draw ticker
        draw.text((ticker_x, y), ticker_text, font=font_value_large, fill='#fff')
        # Draw badge to right of ticker, perfectly centered
        badge = Image.new('RGBA', (badge_w, badge_h), (0,0,0,0))
        badge_draw = ImageDraw.Draw(badge)
        badge_draw.rounded_rectangle([(0,0),(badge_w,badge_h)], radius=badge_h//2, fill=badge_color)
        # Draw text centered in badge
        badge_draw.text(((badge_w-badge_text_w)//2, (badge_h-badge_text_h)//2), badge_text, font=font_badge, fill='#fff')
        card.paste(badge, (int(badge_x), int(badge_y)), badge)
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
        badge_draw.text(((badge_w-badge_text_w)//2, (badge_h-badge_text_h)//2), badge_text, font=font_badge, fill='#fff')
        card.paste(badge, (int(badge_x_center), int(badge_y)), badge)
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
    col_width = 220  # Increased width for more space
    total_cols_w = col_width * 2
    group_x = center_x - total_cols_w // 2
    entry_label = "Entry"
    exit_label = "Exit"
    entry_label_w, entry_label_h = get_text_size(font_label, entry_label)
    exit_label_w, exit_label_h = get_text_size(font_label, exit_label)
    entry_val = f"{trade.entry_price}"
    exit_val = f"{trade.exit_price if trade.exit_price is not None else '-'}"
    entry_val_w, entry_val_h = get_text_size(font_value, entry_val)
    exit_val_w, exit_val_h = get_text_size(font_value, exit_val)
    # Entry column
    entry_col_x = group_x
    # Exit column
    exit_col_x = group_x + col_width
    # Draw labels
    draw.text((entry_col_x + (col_width - entry_label_w)//2, price_y), entry_label, font=font_label, fill='#b0b0b0')
    draw.text((exit_col_x + (col_width - exit_label_w)//2, price_y), exit_label, font=font_label, fill='#b0b0b0')
    # Baseline alignment for values
    max_val_h = max(entry_val_h, exit_val_h)
    value_y_base = price_y + entry_label_h + 8 + max_val_h  # baseline for both values
    draw.text((entry_col_x + (col_width - entry_val_w)//2, value_y_base - entry_val_h), entry_val, font=font_value, fill='#fff')
    draw.text((exit_col_x + (col_width - exit_val_w)//2, value_y_base - exit_val_h), exit_val, font=font_value, fill='#fff')
    y = value_y_base + 32

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
def share_trade_png(trade_id):
    trade = Trade.query.get_or_404(trade_id)
    # Only allow if the trade's user has opted in to the leaderboard
    if not getattr(trade.trader, 'show_on_top_trades', False):
        flash('You are not authorized to share this trade.', 'danger')
        return redirect(url_for('main.index'))

    # Use project root for save_dir to avoid /app/app/ path issues
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    save_dir = os.path.join(project_root, 'var', 'data', 'trade_cards')
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, f"trade_{trade.id}.png")
    print(f"[DEBUG] Saving/serving trade card at: {save_path}")

    try:
        if not os.path.exists(save_path):
            # Generate the PNG
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
            title_text = "KINGLINE"
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
            # Calculate the total width of ticker + gap + badge
            total_w = ticker_w + badge_gap + badge_w
            ticker_x = center_x - total_w // 2
            badge_x = ticker_x + ticker_w + badge_gap
            badge_y = y + (ticker_h - badge_h) // 2
            badge_fits = badge_x + badge_w < width - 20
            if badge_fits:
                draw.text((ticker_x, y), ticker_text, font=font_value_large, fill='#fff')
                badge = Image.new('RGBA', (badge_w, badge_h), (0,0,0,0))
                badge_draw = ImageDraw.Draw(badge)
                badge_draw.rounded_rectangle([(0,0),(badge_w,badge_h)], radius=badge_h//2, fill=badge_color)
                badge_draw.text(((badge_w-badge_text_w)//2, (badge_h-badge_text_h)//2), badge_text, font=font_badge, fill='#fff')
                card.paste(badge, (int(badge_x), int(badge_y)), badge)
                y += max(ticker_h, badge_h) + 30
            else:
                draw.text((center_x - ticker_w//2, y), ticker_text, font=font_value_large, fill='#fff')
                y += ticker_h + 10
                badge_x_center = center_x - badge_w//2
                badge_y = y
                badge = Image.new('RGBA', (badge_w, badge_h), (0,0,0,0))
                badge_draw = ImageDraw.Draw(badge)
                badge_draw.rounded_rectangle([(0,0),(badge_w,badge_h)], radius=badge_h//2, fill=badge_color)
                badge_draw.text(((badge_w-badge_text_w)//2, (badge_h-badge_text_h)//2), badge_text, font=font_badge, fill='#fff')
                card.paste(badge, (int(badge_x_center), int(badge_y)), badge)
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
            col_width = 220  # Increased width for more space, matches shareable card
            total_cols_w = col_width * 2
            group_x = center_x - total_cols_w // 2
            entry_label = "Entry"
            exit_label = "Exit"
            entry_label_w, entry_label_h = get_text_size(font_label, entry_label)
            exit_label_w, exit_label_h = get_text_size(font_label, exit_label)
            entry_val = f"{trade.entry_price}"
            exit_val = f"{trade.exit_price if trade.exit_price is not None else '-'}"
            entry_val_w, entry_val_h = get_text_size(font_value, entry_val)
            exit_val_w, exit_val_h = get_text_size(font_value, exit_val)
            # Entry column
            entry_col_x = group_x
            # Exit column
            exit_col_x = group_x + col_width
            # Draw labels
            draw.text((entry_col_x + (col_width - entry_label_w)//2, price_y), entry_label, font=font_label, fill='#b0b0b0')
            draw.text((exit_col_x + (col_width - exit_label_w)//2, price_y), exit_label, font=font_label, fill='#b0b0b0')
            # Baseline alignment for values (match share_trade logic)
            max_val_h = max(entry_val_h, exit_val_h)
            value_y_base = price_y + entry_label_h + 8 + max_val_h  # baseline for both values
            draw.text((entry_col_x + (col_width - entry_val_w)//2, value_y_base - entry_val_h), entry_val, font=font_value, fill='#fff')
            draw.text((exit_col_x + (col_width - exit_val_w)//2, value_y_base - exit_val_h), exit_val, font=font_value, fill='#fff')
            y = value_y_base + 32
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
    except Exception as e:
        print(f"[ERROR] Could not generate or serve trade card PNG: {e}", file=sys.stderr)
        return f"Error generating trade card image: {e}", 500

# ---------------------- Tradovate Import ----------------------

@bp.route('/import_trades', methods=['GET'])
@login_required
def import_trades():
    """Show import trades page"""
    return render_template('import_trades.html', 
                         title='Import Trades')

@bp.route('/tradovate_credentials', methods=['GET', 'POST', 'DELETE'])
@login_required
def manage_tradovate_credentials():
    from app.models import TradovateCredentials
    
    if request.method == 'POST':
        # Update credentials
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Please provide both username and password.', 'danger')
            return redirect(url_for('main.manage_tradovate_credentials'))
        
        try:
            from app.tradovate_client import TradovateClient
            client = TradovateClient()
            auth_result = client.authenticate(username, password)
            
            # Update or create credentials
            credentials = TradovateCredentials.query.filter_by(user_id=current_user.id).first()
            if credentials:
                credentials.username = username
                credentials.access_token = auth_result['access_token']
                credentials.refresh_token = auth_result['refresh_token']
                credentials.token_expires_at = datetime.utcnow() + timedelta(seconds=auth_result['expires_in'])
                credentials.updated_at = datetime.utcnow()
            else:
                credentials = TradovateCredentials(
                    user_id=current_user.id,
                    username=username,
                    access_token=auth_result['access_token'],
                    refresh_token=auth_result['refresh_token'],
                    token_expires_at=datetime.utcnow() + timedelta(seconds=auth_result['expires_in'])
                )
                db.session.add(credentials)
            
            db.session.commit()
            flash('Tradovate credentials updated successfully.', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to update credentials: {str(e)}', 'danger')
        
        return redirect(url_for('main.manage_tradovate_credentials'))
    
    elif request.method == 'DELETE':
        # Delete credentials
        credentials = TradovateCredentials.query.filter_by(user_id=current_user.id).first()
        if credentials:
            db.session.delete(credentials)
            db.session.commit()
            flash('Tradovate credentials deleted successfully.', 'success')
        return jsonify({'success': True})
    
    # GET request - show credentials management page
    credentials = TradovateCredentials.query.filter_by(user_id=current_user.id).first()
    return render_template('tradovate_credentials.html', 
                         title='Tradovate Credentials',
                         credentials=credentials)

@bp.route('/import_csv', methods=['POST'])
@login_required
def import_csv():
    """Import trades from CSV file"""
    if 'csv_file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('main.import_trades'))
    
    file = request.files['csv_file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('main.import_trades'))
    
    if not file.filename.endswith('.csv'):
        flash('Please select a CSV file', 'error')
        return redirect(url_for('main.import_trades'))
    
    try:
        # Read CSV file
        import csv
        import io
        from datetime import datetime
        
        # Read the file content
        content = file.read().decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(content))
        
        # Get or create "Imported" strategy
        strategy = Strategy.query.filter_by(name='Imported', user_id=current_user.id).first()
        if not strategy:
            strategy = Strategy(name='Imported', user_id=current_user.id)
            db.session.add(strategy)
            db.session.commit()
        
        imported_count = 0
        skipped_count = 0
        
        # Check if this is a Tradovate Orders export (has B/S column)
        is_tradovate_orders = 'B/S' in csv_reader.fieldnames
        
        if is_tradovate_orders:
            # Handle Tradovate Orders export format
            imported_count, skipped_count = process_tradovate_orders(csv_reader, strategy, current_user)
        else:
            # Handle standard trade CSV format
            for row in csv_reader:
                try:
                    # Parse trade data from CSV
                    # This is a basic implementation - you may need to adjust based on your CSV format
                    symbol = row.get('Symbol', row.get('symbol', ''))
                    side = row.get('Side', row.get('side', ''))
                    quantity = row.get('Quantity', row.get('quantity', ''))
                    price = row.get('Price', row.get('price', ''))
                    date_str = row.get('Date', row.get('date', ''))
                    pnl = row.get('PnL', row.get('pnl', ''))
                    
                    if not all([symbol, side, quantity, price, date_str]):
                        continue
                    
                    # Parse date
                    try:
                        trade_date = datetime.strptime(date_str, '%Y-%m-%d')
                    except ValueError:
                        try:
                            trade_date = datetime.strptime(date_str, '%m/%d/%Y')
                        except ValueError:
                            continue
                    
                    # Check for duplicate trade
                    existing_trade = Trade.query.filter_by(
                        ticker=symbol,
                        entry_date=trade_date,
                        user_id=current_user.id
                    ).first()
                    
                    if existing_trade:
                        skipped_count += 1
                        continue
                    
                    # Create new trade
                    trade = Trade(
                        ticker=symbol,
                        direction='Long' if side.lower() in ['buy', 'long'] else 'Short',
                        position_size=float(quantity),
                        entry_price=float(price),
                        entry_date=trade_date,
                        strategy=strategy,
                        user_id=current_user.id,
                        notes=f"Imported from CSV - {file.filename}"
                    )
                    
                    if pnl:
                        try:
                            trade.pnl = float(pnl)
                        except ValueError:
                            pass
                    
                    db.session.add(trade)
                    imported_count += 1
                    
                except (ValueError, KeyError) as e:
                    skipped_count += 1
                    continue
        
        db.session.commit()
        
        if imported_count > 0:
            flash(f'Successfully imported {imported_count} trades. Skipped {skipped_count} duplicates/invalid entries.', 'success')
        else:
            flash('No valid trades found in CSV file', 'warning')
            
    except Exception as e:
        flash(f'Error importing CSV: {str(e)}', 'error')
    
    return redirect(url_for('main.import_trades'))

def process_tradovate_orders(csv_reader, strategy, current_user):
    """Process Tradovate Orders export format and convert to trades using FIFO ledger logic"""
    from collections import defaultdict
    from datetime import datetime

    # Group all filled orders by symbol
    orders_by_symbol = defaultdict(list)
    for row in csv_reader:
        try:
            if row.get('Status', '').strip() != 'Filled':
                continue
            symbol = row.get('Contract', '')
            side = row.get('B/S', '').strip()
            quantity = row.get('filledQty', '')
            price = row.get('avgPrice', '')
            date_str = row.get('Date', '')
            fill_time = row.get('Fill Time', '')
            if not all([symbol, side, quantity, price, date_str]):
                continue
            # Parse date and time
            try:
                trade_date = datetime.strptime(date_str, '%m/%d/%y')
            except ValueError:
                continue
            try:
                if fill_time:
                    time_part = fill_time.split(' ')[1] if ' ' in fill_time else fill_time
                    time_obj = datetime.strptime(time_part, '%H:%M:%S').time()
                    trade_date = trade_date.replace(hour=time_obj.hour, minute=time_obj.minute, second=time_obj.second)
            except:
                pass
            orders_by_symbol[symbol].append({
                'side': side,
                'quantity': float(quantity),
                'price': float(price),
                'datetime': trade_date,
                'order_id': row.get('orderId', '')
            })
        except Exception:
            continue

    imported_count = 0
    skipped_count = 0
    for symbol, orders in orders_by_symbol.items():
        # Sort all fills by time
        orders.sort(key=lambda x: x['datetime'])
        
        # Track running positions and trades
        long_position = 0  # Running count of long contracts
        short_position = 0  # Running count of short contracts
        long_entries = []  # List of buy orders for weighted average
        short_entries = []  # List of sell orders for weighted average
        completed_trades = []  # Trades that are fully closed
        
        for order in orders:
            side = order['side']
            qty = order['quantity']
            price = order['price']
            dt = order['datetime']
            oid = order['order_id']
            
            if side == 'Buy':
                if short_position > 0:
                    # Close short positions first
                    qty_to_close = min(qty, short_position)
                    
                    # Calculate weighted average entry price for short position
                    total_short_value = sum(entry['price'] * entry['qty'] for entry in short_entries)
                    total_short_qty = sum(entry['qty'] for entry in short_entries)
                    avg_short_entry = total_short_value / total_short_qty if total_short_qty > 0 else 0
                    
                    # Create completed short trade
                    # Apply contract multiplier for MNQ (point value = 2)
                    point_value = 2 if symbol.upper() == 'MNQU5' else 1
                    pnl = (avg_short_entry - price) * qty_to_close * point_value
                    notes = f"Imported from Tradovate Orders - Short: {', '.join([e['order_id'] for e in short_entries])}, Buy: {oid}"
                    
                    # Check for duplicate trade
                    existing_trade = Trade.query.filter_by(
                        ticker=symbol,
                        entry_date=short_entries[0]['time'],
                        exit_date=dt,
                        position_size=qty_to_close,
                        user_id=current_user.id
                    ).first()
                    if not existing_trade:
                        trade = Trade(
                            ticker=symbol,
                            direction='Short',
                            position_size=qty_to_close,
                            entry_price=avg_short_entry,
                            entry_date=short_entries[0]['time'],
                            exit_price=price,
                            exit_date=dt,
                            strategy=strategy,
                            user_id=current_user.id,
                            notes=notes,
                            pnl=pnl
                        )
                        db.session.add(trade)
                        imported_count += 1
                    else:
                        skipped_count += 1
                    
                    # Update short position
                    short_position -= qty_to_close
                    if short_position == 0:
                        short_entries = []  # Reset short entries
                    
                    # Remaining qty goes to long position
                    remaining_qty = qty - qty_to_close
                    if remaining_qty > 0:
                        long_position += remaining_qty
                        long_entries.append({'qty': remaining_qty, 'price': price, 'time': dt, 'order_id': oid})
                else:
                    # Add to long position
                    long_position += qty
                    long_entries.append({'qty': qty, 'price': price, 'time': dt, 'order_id': oid})
                    
            elif side == 'Sell':
                if long_position > 0:
                    # Close long positions first
                    qty_to_close = min(qty, long_position)
                    
                    # Calculate weighted average entry price for long position
                    total_long_value = sum(entry['price'] * entry['qty'] for entry in long_entries)
                    total_long_qty = sum(entry['qty'] for entry in long_entries)
                    avg_long_entry = total_long_value / total_long_qty if total_long_qty > 0 else 0
                    
                    # Create completed long trade
                    # Apply contract multiplier for MNQ (point value = 2)
                    point_value = 2 if symbol.upper() == 'MNQU5' else 1
                    pnl = (price - avg_long_entry) * qty_to_close * point_value
                    notes = f"Imported from Tradovate Orders - Long: {', '.join([e['order_id'] for e in long_entries])}, Sell: {oid}"
                    
                    # Check for duplicate trade
                    existing_trade = Trade.query.filter_by(
                        ticker=symbol,
                        entry_date=long_entries[0]['time'],
                        exit_date=dt,
                        position_size=qty_to_close,
                        user_id=current_user.id
                    ).first()
                    if not existing_trade:
                        trade = Trade(
                            ticker=symbol,
                            direction='Long',
                            position_size=qty_to_close,
                            entry_price=avg_long_entry,
                            entry_date=long_entries[0]['time'],
                            exit_price=price,
                            exit_date=dt,
                            strategy=strategy,
                            user_id=current_user.id,
                            notes=notes,
                            pnl=pnl
                        )
                        db.session.add(trade)
                        imported_count += 1
                    else:
                        skipped_count += 1
                    
                    # Update long position
                    long_position -= qty_to_close
                    if long_position == 0:
                        long_entries = []  # Reset long entries
                    
                    # Remaining qty goes to short position
                    remaining_qty = qty - qty_to_close
                    if remaining_qty > 0:
                        short_position += remaining_qty
                        short_entries.append({'qty': remaining_qty, 'price': price, 'time': dt, 'order_id': oid})
                else:
                    # Add to short position
                    short_position += qty
                    short_entries.append({'qty': qty, 'price': price, 'time': dt, 'order_id': oid})
    
    db.session.commit()
    return imported_count, skipped_count 