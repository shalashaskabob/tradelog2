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