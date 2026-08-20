from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.models.base import Base
import uuid

class LoteProcessamento(Base):
    """Auditoria e Estado do processamento em lote assíncrono (lotes de 5.000 chunks)."""
    __tablename__ = "lotes_processamento"

    id_lote = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Mapeado do Orquestrador: Pasta Base (DATA/HORA/NOME)
    caminho_diretorio_base = Column(String(500), nullable=False) 
    
    # Métricas do lote fatiadas do Orquestrador
    total_imagens_lote = Column(Integer, nullable=False, default=0)
    faces_extraidas = Column(Integer, nullable=False, default=0)
    
    # Estados de processamento: PROCESSANDO, CONCLUIDO, FALHA
    status = Column(String(50), nullable=False, default="PROCESSANDO") 
    
    data_inicio = Column(DateTime(timezone=True), server_default=func.now())
    data_fim = Column(DateTime(timezone=True), nullable=True)