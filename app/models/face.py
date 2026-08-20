from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.models.base import Base
import uuid

class EvidenciaFacial(Base):
    """
    Tabela principal para Triagem Biométrica N:N (PeríciaFace-PR).
    Persiste vetores, demográficos JSONB e caminhos de DISCO LOCAL[cite: 4].
    """
    __tablename__ = "evidencias_faciais"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Governança e Custódia (O hashing garante prevenção de duplicatas bit a bit e custódia)
    hash_sha256 = Column(String(64), nullable=False, unique=True, index=True)
    caminho_origem_bruta = Column(String(500), nullable=False) # Caminho bruto absoluto
    
    # REFERÊNCIA AO DISCO LOCAL (Substituindo MinIO)
    # Ex: /home/adilson/hunter_data/crops/PPL_ID_1/face_1.jpg
    caminho_local_crop = Column(String(500), nullable=False) 
    
    # Biometria (Saída ArcFace 512-D)
    embedding = Column(Vector(512), nullable=False)
    
    # Metadados Periciais (Incorporando os exemplos JSON fornecidos)
    # Ex: {"gender": "male", "ethnicity": "black", "birth_year": 2003, "device": "phone"}
    metadados_adicionais = Column(JSONB, nullable=True) 
    
    data_extracao = Column(DateTime(timezone=True), server_default=func.now())

    # Índice HNSW de Busca Ultrarrápida para Similaridade de Cosseno (buscas N:N)
    __table_args__ = (
        Index(
            'idx_evidencias_embedding_hnsw',
            embedding,
            postgresql_using='hnsw',
            postgresql_with={'m': 16, 'ef_construction': 64},
            postgresql_ops={'embedding': 'vector_cosine_ops'}
        ),
    )