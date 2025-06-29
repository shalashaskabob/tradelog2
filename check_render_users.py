#!/usr/bin/env python3
"""
Safe script to check user registrations on Render.
This script is READ-ONLY and will not modify your database.
Run this on your Render instance.
"""

import os
from app import create_app, db
from app.models import User, Trade

def check_render_users():
    app = create_app()
    
    with app.app_context():
        print("=== User Registration Report ===")
        print(f"Database location: {app.config['SQLALCHEMY_DATABASE_URI']}")
        print()
        
        # Count total users
        total_users = User.query.count()
        print(f"Total registered users: {total_users}")
        
        if total_users > 0:
            print("\n=== User Details ===")
            print("-" * 70)
            print(f"{'ID':<5} {'Username':<20} {'Trade Count':<12} {'Status':<10}")
            print("-" * 70)
            
            users = User.query.all()
            for user in users:
                trade_count = user.trades.count()
                status = "Active" if trade_count > 0 else "Inactive"
                print(f"{user.id:<5} {user.username:<20} {trade_count:<12} {status:<10}")
            
            print("-" * 70)
            
            # Additional statistics
            active_users = User.query.join(Trade).distinct().count()
            inactive_users = total_users - active_users
            
            print(f"\n=== Summary ===")
            print(f"Active users (with trades): {active_users}")
            print(f"Inactive users (no trades): {inactive_users}")
            print(f"Activity rate: {(active_users/total_users)*100:.1f}%")
            
            # Most active users
            if active_users > 0:
                print(f"\n=== Top 5 Most Active Users ===")
                active_user_list = [(user.username, user.trades.count()) for user in users if user.trades.count() > 0]
                active_user_list.sort(key=lambda x: x[1], reverse=True)
                for i, (username, count) in enumerate(active_user_list[:5], 1):
                    print(f"{i}. {username}: {count} trades")
        else:
            print("No users found in the database.")
        
        print("\n=== Database Info ===")
        print(f"Database file exists: {os.path.exists('/var/data/app.db')}")
        if os.path.exists('/var/data/app.db'):
            size = os.path.getsize('/var/data/app.db')
            print(f"Database size: {size:,} bytes ({size/1024/1024:.2f} MB)")

if __name__ == '__main__':
    check_render_users() 