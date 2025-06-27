import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    
    # Check if running on Render
    if os.environ.get('RENDER'):
        # Use the persistent disk path for the database
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
            'sqlite:///' + os.path.join('/var/data', 'app.db')
    else:
        # Use a local path for development
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
            'sqlite:///' + os.path.join(basedir, 'instance', 'app.db')
            
    SQLALCHEMY_TRACK_MODIFICATIONS = False 