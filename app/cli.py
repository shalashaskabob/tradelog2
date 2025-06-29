import click
from app import db
from app.models import User

def register_commands(app):
    @app.cli.command('reset-password')
    @click.argument('username')
    @click.argument('password')
    def reset_password_command(username, password):
        """Resets a user's password."""
        user = User.query.filter_by(username=username).first()
        if user is None:
            click.echo(f"Error: User '{username}' not found.")
            return
        
        user.set_password(password)
        db.session.commit()
        click.echo(f"Password for user '{username}' has been successfully reset.")

    @app.cli.command('list-users')
    def list_users_command():
        """Lists all registered users."""
        users = User.query.all()
        if not users:
            click.echo("No users found in the database.")
            return
        
        click.echo(f"Found {len(users)} registered user(s):")
        click.echo("-" * 50)
        for user in users:
            trade_count = user.trades.count()
            click.echo(f"ID: {user.id} | Username: {user.username} | Trades: {trade_count}")
        click.echo("-" * 50)

    @app.cli.command('count-users')
    def count_users_command():
        """Counts the total number of registered users."""
        count = User.query.count()
        click.echo(f"Total registered users: {count}")

    @app.cli.command('make-admin')
    @click.argument('username')
    def make_admin_command(username):
        """Makes a user an admin."""
        user = User.query.filter_by(username=username).first()
        if user is None:
            click.echo(f"Error: User '{username}' not found.")
            return
        
        user.is_admin = True
        db.session.commit()
        click.echo(f"User '{username}' is now an admin.")

    @app.cli.command('remove-admin')
    @click.argument('username')
    def remove_admin_command(username):
        """Removes admin privileges from a user."""
        user = User.query.filter_by(username=username).first()
        if user is None:
            click.echo(f"Error: User '{username}' not found.")
            return
        
        user.is_admin = False
        db.session.commit()
        click.echo(f"Admin privileges removed from user '{username}'.")

    @app.cli.command('delete-user')
    @click.argument('username')
    def delete_user_command(username):
        """Deletes a user and all their trades and strategies."""
        user = User.query.filter_by(username=username).first()
        if user is None:
            click.echo(f"Error: User '{username}' not found.")
            return
        # Delete user's trades
        num_trades = user.trades.count()
        for trade in user.trades:
            db.session.delete(trade)
        # Delete user's strategies
        num_strategies = user.strategies.count()
        for strategy in user.strategies:
            db.session.delete(strategy)
        db.session.delete(user)
        db.session.commit()
        click.echo(f"User '{username}' deleted. {num_trades} trades and {num_strategies} strategies removed.") 