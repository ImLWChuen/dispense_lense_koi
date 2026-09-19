from sqlalchemy import create_engine, text
from app.core.config import get_database_url

engine = create_engine(get_database_url())
with engine.connect() as conn:
    conn.execute(text('DROP TABLE IF EXISTS alembic_version;'))
    conn.commit()
print("Dropped alembic_version")
