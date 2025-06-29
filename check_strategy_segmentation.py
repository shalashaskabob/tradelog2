#!/usr/bin/env python3
"""
Script to check for orphaned strategies and verify proper user data segmentation.
Run this on Render to check your production database.
"""

import os
import sys
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User, Strategy, Trade

app = create_app()

def check_strategy_segmentation():
    """Check for orphaned strategies and verify user data segmentation."""
    
    with app.app_context():
        print("=== Strategy Segmentation Check ===\n")
        print(f"Check performed at: {datetime.now()}\n")
        
        # 1. Check for strategies with NULL or missing user_id
        print("1. Checking for orphaned strategies (NULL user_id):")
        orphaned_strategies = Strategy.query.filter_by(user_id=None).all()
        if orphaned_strategies:
            print(f"   WARNING: Found {len(orphaned_strategies)} strategies with NULL user_id:")
            for strategy in orphaned_strategies:
                print(f"   - Strategy ID {strategy.id}: '{strategy.name}'")
        else:
            print("   ✓ No orphaned strategies found")
        
        # 2. Check for strategies with user_id=1 (common fallback)
        print("\n2. Checking for strategies with user_id=1 (potential fallback):")
        fallback_strategies = Strategy.query.filter_by(user_id=1).all()
        if fallback_strategies:
            print(f"   Found {len(fallback_strategies)} strategies with user_id=1:")
            for strategy in fallback_strategies:
                print(f"   - Strategy ID {strategy.id}: '{strategy.name}'")
        else:
            print("   ✓ No fallback strategies found")
        
        # 3. List all users and their strategies
        print("\n3. User strategy breakdown:")
        users = User.query.all()
        for user in users:
            strategies = Strategy.query.filter_by(user_id=user.id).all()
            print(f"   User '{user.username}' (ID: {user.id}): {len(strategies)} strategies")
            for strategy in strategies:
                print(f"     - '{strategy.name}' (ID: {strategy.id})")
        
        # 4. Check for duplicate strategy names across users
        print("\n4. Checking for duplicate strategy names across users:")
        # Get all strategy names and their user_ids
        strategy_data = db.session.query(Strategy.name, Strategy.user_id).all()
        name_to_users = {}
        for name, user_id in strategy_data:
            if name not in name_to_users:
                name_to_users[name] = []
            name_to_users[name].append(user_id)
        
        duplicates = {name: user_ids for name, user_ids in name_to_users.items() if len(user_ids) > 1}
        if duplicates:
            print("   Found duplicate strategy names across users:")
            for name, user_ids in duplicates.items():
                print(f"   - '{name}' used by users: {user_ids}")
        else:
            print("   ✓ No duplicate strategy names across users")
        
        # 5. Check for trades linked to orphaned strategies
        print("\n5. Checking for trades linked to orphaned strategies:")
        orphaned_trades = db.session.query(Trade).join(Strategy).filter(Strategy.user_id.is_(None)).all()
        if orphaned_trades:
            print(f"   WARNING: Found {len(orphaned_trades)} trades linked to orphaned strategies:")
            for trade in orphaned_trades:
                print(f"   - Trade ID {trade.id}: {trade.ticker} (Strategy: '{trade.strategy.name}')")
        else:
            print("   ✓ No trades linked to orphaned strategies")
        
        # 6. Check for trades with mismatched user_id and strategy.user_id
        print("\n6. Checking for user-strategy mismatches in trades:")
        mismatched_trades = db.session.query(Trade).join(Strategy).filter(
            Trade.user_id != Strategy.user_id
        ).all()
        if mismatched_trades:
            print(f"   WARNING: Found {len(mismatched_trades)} trades with mismatched user/strategy:")
            for trade in mismatched_trades:
                print(f"   - Trade ID {trade.id}: User {trade.user_id}, Strategy User {trade.strategy.user_id}")
        else:
            print("   ✓ No user-strategy mismatches found")
        
        # 7. Summary statistics
        print("\n=== Summary ===")
        total_strategies = Strategy.query.count()
        total_users = User.query.count()
        total_trades = Trade.query.count()
        
        print(f"Total users: {total_users}")
        print(f"Total strategies: {total_strategies}")
        print(f"Total trades: {total_trades}")
        
        if orphaned_strategies or orphaned_trades or mismatched_trades:
            print("\n⚠️  ISSUES FOUND: Data segmentation problems detected!")
            print("   Consider running a cleanup script to fix these issues.")
        else:
            print("\n✓ All checks passed! User data is properly segmented.")

if __name__ == '__main__':
    try:
        check_strategy_segmentation()
    except Exception as e:
        print(f"Error running check: {e}")
        print("Make sure you're running this on Render with the correct environment.") 