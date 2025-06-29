from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    # 1. Create new table with correct schema
    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS strategy_new (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            user_id INTEGER NOT NULL,
            CONSTRAINT _user_strategy_uc UNIQUE (name, user_id)
        );
    """))
    # 2. Copy data (assign user_id=1 if missing)
    db.session.execute(text("""
        INSERT INTO strategy_new (id, name, user_id)
        SELECT id, name, COALESCE(user_id, 1) FROM strategy;
    """))
    # 3. Drop old table
    db.session.execute(text("DROP TABLE strategy;"))
    # 4. Rename new table
    db.session.execute(text("ALTER TABLE strategy_new RENAME TO strategy;"))
    db.session.commit()
    print("Strategy table fixed!") 