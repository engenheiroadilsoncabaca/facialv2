import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Carrega .env da raiz do projeto
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')

class Settings(BaseSettings):
    # Configurações do App
    PROJECT_NAME: str = "ID-Hunter Biometria SESP-PR"
    ENVIRONMENT: str = "dev"

    # Configurações do Banco de Dados (PostgreSQL + PGVector)
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str
    
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Configurações do Redis (Broker)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    
    @property
    def CELERY_BROKER_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    # CAMINHOS FÍSICOS LOCAIS (Crucial para o fluxo de trabalho em disco local)
    PATH_IMAGENS_BRUTAS: str = Field(..., env="PATH_IMAGENS_BRUTAS")
    PATH_RECORTES_CROPS: str = Field(..., env="PATH_RECORTES_CROPS")

    model_config = SettingsConfigDict(env_file=dotenv_path, env_file_encoding='utf-8')

# Instância singleton das configurações
settings = Settings()