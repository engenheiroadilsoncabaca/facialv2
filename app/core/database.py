from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

# Engine conectada ao localhost (Redirecionada pelo Docker)
engine = create_engine(settings.SQLALCHEMY_DATABASE_URI, pool_pre_ping=True)

# Fábrica de Sessões
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Auxiliar de injeção de dependência
def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()