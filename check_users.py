#!/usr/bin/env python3
"""
Simple script to check user registration statistics.
Run this from the project root directory.
"""

from app import create_app, db
from app.models import User, Trade

def check_users():
    app = create_app()
    
    with app.app_context():
        # Count total users
        total_users = User.query.count()
        print(f"Total registered users: {total_users}")
        
        if total_users > 0:
            print("\nUser details:")
            print("-" * 60)
            users = User.query.all()
            for user in users:
                trade_count = user.trades.count()
                print(f"ID: {user.id:3d} | Username: {user.username:15s} | Trades: {trade_count:3d}")
            print("-" * 60)
            
            # Additional statistics
            active_users = User.query.join(Trade).distinct().count()
            inactive_users = total_users - active_users
            print(f"\nActive users (with trades): {active_users}")
            print(f"Inactive users (no trades): {inactive_users}")
        else:
            print("No users found in the database.")

if __name__ == '__main__':
    check_users() 