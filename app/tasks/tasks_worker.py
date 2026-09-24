# import os
# import uuid
# import hashlib
# from datetime import datetime
# from pathlib import Path
# from sqlalchemy.orm import Session
# from sqlalchemy import text

# from app.core.celery_config import celery_app as app
# from app.core.config import settings
# from app.core.database import SessionLocal
# from app.core.metrics import log_hardware_diagnostic

# from app.models.face import EvidenciaFacial
# from app.tasks.hunter_ai import biometric_engine

# def gerar_hash_sha256(path_arquivo):
#     """Calcula o hash SHA-256 do ficheiro para custódia e desduplicação."""
#     sha256_hash = hashlib.sha256()
#     with open(path_arquivo, "rb") as f:
#         for byte_block in iter(lambda: f.read(4096), b""):
#             sha256_hash.update(byte_block)
#     return sha256_hash.hexdigest()

# def buscar_ou_criar_individuo(db: Session, embedding_list: list, limite_distancia=0.45):
#     """
#     Realiza a pesquisa vetorial N:1 no pgvector para agrupar fotos do mesmo indivíduo.
#     Utiliza CAST explícito para evitar conflitos de sintaxe com o SQLAlchemy no Windows.
#     """
#     embedding_str = f"[{','.join(map(str, embedding_list))}]"
    
#     query = text("""
#         SELECT id, (embedding <=> CAST(:emb AS vector)) AS distancia 
#         FROM evidencias_faciais 
#         WHERE (embedding <=> CAST(:emb AS vector)) < :limite
#         ORDER BY distancia ASC 
#         LIMIT 1;
#     """)
    
#     resultado = db.execute(query, {"emb": embedding_str, "limite": limite_distancia}).fetchone()
    
#     if resultado:
#         return str(resultado[0]), True  # Reincidente encontrado
#     return str(uuid.uuid4()), False    # Nova identidade

# @app.task(name="hunter.processar_lote_5k", bind=True, max_retries=1)
# def processar_lote_5k(self, lista_caminhos_imagens: list, data_lote: dict):
#     lote_id_str = data_lote.get('id_lote_audit')
#     caminho_base = data_lote.get('caminho_base')
#     print(f"[WORKER] Processando Lote: {lote_id_str} | Total de imagens: {len(lista_caminhos_imagens)}")
    
#     db: Session = SessionLocal()
    
#     query_update = text(f"UPDATE lotes_processamento SET status='PROCESSANDO', total_imagens_lote={len(lista_caminhos_imagens)} WHERE id_lote='{lote_id_str}'")
#     db.execute(query_update)
#     db.commit()

#     path_crops_raiz = Path(settings.PATH_RECORTES_CROPS)
#     faces_processadas_sucesso = 0
#     total_imagens = 0

#     for img_path_str in lista_caminhos_imagens:
#         total_imagens += 1
#         img_path = Path(img_path_str)
        
#         if not img_path.exists():
#             print(f"[WORKER] PULADO: Arquivo não encontrado: {img_path}")
#             continue

#         try:
#             # 1. Hashing SHA-256 (Cadeia de Custódia)
#             hash_id = gerar_hash_sha256(img_path)
            
#             # 2. Extração Biométrica via InsightFace
#             crop_binary, embedding_512, demografia_real = biometric_engine.processar_imagem(img_path)
            
#             if not crop_binary or not embedding_512:
#                 continue

#             # 3. Pesquisa de Reincidência na Base de Dados Vetorial
#             individuo_id, eh_reincidente = buscar_ou_criar_individuo(db, embedding_512)

#             # 4. Criação da Pasta e Escrita Física do Crop
#             target_folder = path_crops_raiz / individuo_id
#             target_folder.mkdir(parents=True, exist_ok=True)
            
#             crop_filename = f"{hash_id[:10]}_face.jpg"
#             target_crop_path = target_folder / crop_filename
            
#             with open(target_crop_path, "wb") as f:
#                 f.write(crop_binary)

#             # 5. Registo do Evento na Tabela de Evidências
#             metadados_completos = {
#                 "lote_origem_audit": lote_id_str,
#                 "status_triagem": "reincidente" if eh_reincidente else "novo_cadastro",
#                 "individuo_id": individuo_id,
#                 **demografia_real
#             }

#             nova_face = EvidenciaFacial(
#                 hash_sha256=hash_id,
#                 caminho_origem_bruta=str(img_path),
#                 caminho_local_crop=str(target_crop_path),
#                 embedding=embedding_512,
#                 metadados_adicionais=metadados_completos,
#                 data_extracao=datetime.now()
#             )
#             db.add(nova_face)
#             faces_processadas_sucesso += 1

#             if total_imagens % 100 == 0:
#                 print(f"[WORKER] Progresso Lote {lote_id_str}: {total_imagens}/{len(lista_caminhos_imagens)}")
#                 log_hardware_diagnostic()

#         except Exception as e:
#             print(f"[ERRO] Falha ao processar {img_path.name}: {e}")
#             db.rollback()

#     print(f"[WORKER] Finalizado Lote: {lote_id_str} | Faces salvas: {faces_processadas_sucesso}")
    
#     query_final = text(f"UPDATE lotes_processamento SET status='CONCLUIDO', faces_extraidas={faces_processadas_sucesso}, data_fim='{datetime.now()}' WHERE id_lote='{lote_id_str}'")
#     db.execute(query_final)

#     db.commit()
#     db.close()
    
#     return {"status": "batch_completed", "lote_audit": lote_id_str, "total_processed": total_imagens, "faces_extracted": faces_processadas_sucesso}

import os
import uuid
import hashlib
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.celery_config import celery_app as app
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.metrics import log_hardware_diagnostic

from app.models.face import EvidenciaFacial
from app.tasks.hunter_ai import biometric_engine

def gerar_hash_sha256(path_arquivo):
    """Calcula o hash SHA-256 do arquivo para custódia e desduplicação."""
    sha256_hash = hashlib.sha256()
    with open(path_arquivo, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def buscar_ou_criar_individuo(db: Session, embedding_list: list, limite_distancia=0.45):
    """
    Realiza busca vetorial N:1 no pgvector para agrupar fotos do mesmo indivíduo.
    Utiliza CAST explícito para evitar conflitos de sintaxe com o SQLAlchemy no Windows.
    """
    embedding_str = f"[{','.join(map(str, embedding_list))}]"
    
    query = text("""
        SELECT id, (embedding <=> CAST(:emb AS vector)) AS distancia 
        FROM evidencias_faciais 
        WHERE (embedding <=> CAST(:emb AS vector)) < :limite
        ORDER BY distancia ASC 
        LIMIT 1;
    """)
    
    resultado = db.execute(query, {"emb": embedding_str, "limite": limite_distancia}).fetchone()
    
    if resultado:
        return str(resultado[0]), True  # Reincidente encontrado
    return str(uuid.uuid4()), False    # Nova identidade

@app.task(name="hunter.processar_lote_5k", bind=True, max_retries=1)
def processar_lote_5k(self, lista_caminhos_imagens: list, data_lote: dict):
    lote_id_str = data_lote.get('id_lote_audit')
    caminho_base = data_lote.get('caminho_base')
    
    # Extrai o nome da pasta de origem (ex: 2024_pasta1, 2025_pasta2)
    nome_pasta_origem = Path(caminho_base).name if caminho_base else "geral"
    
    print(f"[WORKER] Processando Lote: {lote_id_str} | Origem: {nome_pasta_origem} | Imagens: {len(lista_caminhos_imagens)}")
    
    db: Session = SessionLocal()
    
    query_update = text(f"UPDATE lotes_processamento SET status='PROCESSANDO', total_imagens_lote={len(lista_caminhos_imagens)} WHERE id_lote='{lote_id_str}'")
    db.execute(query_update)
    db.commit()

    # Estrutura do destino: PATH_RECORTES_CROPS / <nome_pasta_origem> / <individuo_id>
    path_crops_raiz = Path(settings.PATH_RECORTES_CROPS) / nome_pasta_origem
    faces_processadas_sucesso = 0
    total_imagens = 0

    for img_path_str in lista_caminhos_imagens:
        total_imagens += 1
        img_path = Path(img_path_str)
        
        if not img_path.exists():
            print(f"[WORKER] PULADO: Arquivo não encontrado: {img_path}")
            continue

        try:
            # 1. Hashing SHA-256 (Cadeia de Custódia)
            hash_id = gerar_hash_sha256(img_path)
            
            # 2. Extração Biométrica
            crop_binary, embedding_512, demografia_real = biometric_engine.processar_imagem(img_path)
            
            if not crop_binary or not embedding_512:
                continue

            # 3. Pesquisa de Reincidência na Base de Dados Vetorial
            individuo_id, eh_reincidente = buscar_ou_criar_individuo(db, embedding_512)

            # 4. Criação da Pasta por Origem + Indivíduo e Escrita Física do Crop
            target_folder = path_crops_raiz / individuo_id
            target_folder.mkdir(parents=True, exist_ok=True)
            
            crop_filename = f"{hash_id[:10]}_face.jpg"
            target_crop_path = target_folder / crop_filename
            
            with open(target_crop_path, "wb") as f:
                f.write(crop_binary)

            # 5. Registro na Tabela de Evidências
            metadados_completos = {
                "lote_origem_audit": lote_id_str,
                "pasta_origem": nome_pasta_origem,
                "status_triagem": "reincidente" if eh_reincidente else "novo_cadastro",
                "individuo_id": individuo_id,
                **demografia_real
            }

            nova_face = EvidenciaFacial(
                hash_sha256=hash_id,
                caminho_origem_bruta=str(img_path),
                caminho_local_crop=str(target_crop_path),
                embedding=embedding_512,
                metadados_adicionais=metadados_completos,
                data_extracao=datetime.now()
            )
            db.add(nova_face)
            faces_processadas_sucesso += 1

            if total_imagens % 100 == 0:
                print(f"[WORKER] Progresso Lote {lote_id_str}: {total_imagens}/{len(lista_caminhos_imagens)}")
                log_hardware_diagnostic()

        except Exception as e:
            print(f"[ERRO] Falha ao processar {img_path.name}: {e}")
            db.rollback()

    print(f"[WORKER] Finalizado Lote: {lote_id_str} | Faces salvas em {nome_pasta_origem}: {faces_processadas_sucesso}")
    
    query_final = text(f"UPDATE lotes_processamento SET status='CONCLUIDO', faces_extraidas={faces_processadas_sucesso}, data_fim='{datetime.now()}' WHERE id_lote='{lote_id_str}'")
    db.execute(query_final)

    db.commit()
    db.close()
    
    return {"status": "batch_completed", "lote_audit": lote_id_str, "total_processed": total_imagens, "faces_extracted": faces_processadas_sucesso}