# import os
# import uuid
# import hashlib
# import json
# from datetime import datetime
# from pathlib import Path
# from sqlalchemy.orm import Session
# from sqlalchemy import text

# # Configuração Central
# from app.core.celery_config import celery_app as app
# from app.core.config import settings
# from app.core.database import SessionLocal
# from app.core.metrics import log_hardware_diagnostic # O Monitor de Diagnóstico[cite: 6]

# # Modelos e IA (Wrappers)
# from app.models.face import EvidenciaFacial
# #from app.models.lote.models import LoteProcessamento
# from app.models.lote import LoteProcessamento
# from app.tasks.hunter_ai import detector, vetorizador # Mocks [cite: 6]

# def gerar_hash_sha256(path_arquivo):
#     """Governança: ID único de arquivo para deduplicação bit a bit e custódia[cite: 2, 4]."""
#     sha256_hash = hashlib.sha256()
#     with open(path_arquivo,"rb") as f:
#         # Lê em blocos para evitar estouro de memória
#         for byte_block in iter(lambda: f.read(4096),b""):
#             sha256_hash.update(byte_block)
#     return sha256_hash.hexdigest()

# @app.task(name="hunter.processar_lote_5k", bind=True, max_retries=1)
# def processar_lote_5k(self, lista_caminhos_imagens: list, data_lote: dict):
#     """
#     Consome um lote de até 5.000 caminhos de imagens brutas locais[cite: 1.1.1].
#     Executa Hash SHA-256, Detecção Ensemble (YOLO+SSD), Vetorização ArcFace, 
#     persiste o Crop no Disco Local e Embedding no PostgreSQL.
#     Loga diagnóstico de hardware a cada 100 imagens[cite: 6].
#     """
#     lote_id_str = data_lote.get('id_lote_audit')
#     caminho_base = data_lote.get('caminho_base')
#     print(f"[WORKER] Iniciando processo paralelo para o Lote: {lote_id_str} | Tamanho do lote: {len(lista_caminhos_imagens)}")
    
#     db: Session = SessionLocal()
    
#     # ATUALIZAÇÃO DE AUDITORIA: Define estado no Postgres
#     # (Simplificado para PoC; trate exceções de atualizações reais de banco corretamente)
#     query_update = text(f"UPDATE lotes_processamento SET status='PROCESSANDO', total_imagens_lote={len(lista_caminhos_imagens)} WHERE id_lote='{lote_id_str}'")
#     db.execute(query_update)
#     db.commit()

#     # Define o Caminho do Disco Local para crops
#     path_crops_raiz = Path(settings.PATH_RECORTES_CROPS)
    
#     # Governança: Mantém a estrutura do crop paralela à pasta bruta (Pasta_A, Pasta_B)
#     # O orquestrador passa o nome do caminho base.
#     folder_name = Path(caminho_base).name
#     target_folder = path_crops_raiz / folder_name
#     target_folder.mkdir(parents=True, exist_ok=True)

#     faces_processadas_sucesso = 0
#     total_imagens = 0

#     for img_path_str in lista_caminhos_imagens:
#         total_imagens += 1
#         img_path = Path(img_path_str)
        
#         if not img_path.exists():
#             print(f"[WORKER] PULADO: Arquivo bruto não encontrado: {img_path}")
#             continue

#         try:
#             # 1. HASH (SHA-256) - Cadeia de Custódia
#             hash_id = gerar_hash_sha256(img_path)
            
#             # 2. DETECÇÃO ENSEMBLE (YOLO -> Fallback SSD)
#             # Retorna dados binários[cite: 6]
#             crop_binary = detector.detectar_e_recortar(img_path)
            
#             if not crop_binary:
#                 # Nenhuma face encontrada, pula
#                 continue

#             # 3. VETORIZAÇÃO (ArcFace 512-D)
#             embedding_512 = vetorizador.vetorizar(crop_binary)

#             # 4. SALVAR NO DISCO LOCAL (Substituindo MinIO)
#             # Gera nome de arquivo único para o crop para evitar colisões (ex: nomes de arquivos brutos duplicados entre lotes)
#             crop_filename = f"{uuid.uuid4()}_face.jpg"
#             target_crop_path = target_folder / crop_filename
            
#             # Persiste binário no disco local físico[cite: 1.3.2]
#             with open(target_crop_path, "wb") as f:
#                 f.write(crop_binary) # Mock retorna bytes, real deve lidar com array de bytes

#             # 5. SALVAR NO POSTGRESQL (Vetores e Metadados)
#             # METADADOS MOCKADOS: Incorporando o formato JSON demográfico fornecido.
#             # No fluxo de trabalho real, mapeie esses metadados do JSON que acompanha o lote de imagens.
#             fake_metadados = {
#                 "lote_origem_audit": lote_id_str,
#                 "status_triagem": "limpo", # Categoria face encontrada
#                 "model_yolo": "v8n",
#                 "model_arcface": "512-d",
#                 # Demográficos simulados JSONB para filtragem pericial[cite: 2]
#                 "gender": "male" if total_imagens % 2 == 0 else "female",
#                 "ethnicity": "black" if hash_id[0] == 'a' else "caucasian",
#                 "device_model": "iPhone" if img_path.name.startswith('IMG_') else "Android"
#             }

#             nova_face = EvidenciaFacial(
#                 hash_sha256=hash_id,
#                 caminho_origem_bruta=str(img_path), # Caminho Local Bruto Absoluto
#                 caminho_local_crop=str(target_crop_path), # Caminho Local do Crop Absoluto[cite: 1.3.2]
#                 embedding=embedding_512,
#                 metadados_adicionais=fake_metadados,
#                 data_extracao=datetime.now()
#             )
#             db.add(nova_face)
#             faces_processadas_sucesso += 1

#             # --- DIAGNÓSTICO DE HARDWARE ---
#             # Controle de Diagnóstico do consumo (CPU, RAM, Disco) [cite: 6]
#             # Roda o monitor a cada 100 imagens para minimizar o impacto do diagnóstico
#             if total_imagens % 100 == 0:
#                 print(f"[WORKER] Diagnósticos para o Lote {lote_id_str}: {total_imagens}/{len(lista_caminhos_imagens)} imagens...")
#                 log_hardware_diagnostic()

#         except Exception as e:
#             # Governança: Loga erro mas continua o lote. Rollback desta inserção.
#             # cadeia de custódia: arquivos corrompidos ou inesperados não podem parar o processamento do lote Perícia Face[cite: 2].
#             print(f"[ERRO] Falha ao processar {img_path.name} no Lote {lote_id_str}: {e}")
#             db.rollback() 

#     # FINALIZAÇÃO DE AUDITORIA: Define estado no Postgres
#     print(f"[WORKER] FINALIZANDO Lote: {lote_id_str} | Faces de sucesso inseridas: {faces_processadas_sucesso}")
#     db.execute(f"UPDATE lotes_processamento SET status='CONCLUIDO', faces_extraidas={faces_processadas_sucesso}, data_fim='{datetime.now()}' WHERE id_lote='{lote_id_str}'")
#     db.commit() # Salva inserções de embedding e atualização de auditoria
#     db.close()
    
#     return {"status": "batch_completed", "lote_audit": lote_id_str, "total_processed": total_imagens, "faces_extracted": faces_processadas_sucesso}


import os
import uuid
import hashlib
import json
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import text
# Configuração Central
from app.core.celery_config import celery_app as app
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.metrics import log_hardware_diagnostic


from app.models.face import EvidenciaFacial
#from app.models.lote.models import LoteProcessamento
from app.models.lote import LoteProcessamento
from app.tasks.hunter_ai import detector, vetorizador # Mocks biométrico assíncrono estritamente sequencial

def gerar_hash_sha256(path_arquivo):
    """Governança: ID único de arquivo para deduplicação bit a bit e custódia[cite: 2, 4]."""
    sha256_hash = hashlib.sha256()
    with open(path_arquivo,"rb") as f:
        # Lê em blocos para evitar estouro de memória
        for byte_block in iter(lambda: f.read(4096),b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

@app.task(name="hunter.processar_lote_5k", bind=True, max_retries=1)
def processar_lote_5k(self, lista_caminhos_imagens: list, data_lote: dict):
    """
    Consome um lote de até 5.000 caminhos de imagens brutas locais[cite: 1.1.1].
    Executa Hash SHA-256, Detecção Ensemble (YOLO+SSD), Vetorização ArcFace, 
    persiste o Crop no Disco Local e Embedding no PostgreSQL.
    Loga diagnóstico de hardware a cada 100 imagens biométrica local Batch estritamente sequencial[cite: ready turn, image_7.png turn.
    """
    lote_id_str = data_lote.get('id_lote_audit')
    caminho_base = data_lote.get('caminho_base')
    print(f"[WORKER] Iniciando processo paralelo para o Lote: {lote_id_str} | Tamanho do lote: {len(lista_caminhos_imagens)}")
    
    db: Session = SessionLocal()
    
    query_update = text(f"UPDATE lotes_processamento SET status='PROCESSANDO', total_imagens_lote={len(lista_caminhos_imagens)} WHERE id_lote='{lote_id_str}'")
    db.execute(query_update)
    db.commit()

    # Define o Caminho do Disco Local para crops
    path_crops_raiz = Path(settings.PATH_RECORTES_CROPS)
    
    # Governança: Mantém a estrutura do crop paralela à pasta bruta
    folder_name = Path(caminho_base).name
    target_folder = path_crops_raiz / folder_name
    target_folder.mkdir(parents=True, exist_ok=True)

    faces_processadas_sucesso = 0
    total_imagens = 0

    for img_path_str in lista_caminhos_imagens:
        total_imagens += 1
        img_path = Path(img_path_str)
        
        if not img_path.exists():
            print(f"[WORKER] PULADO: Arquivo bruto não encontrado: {img_path}")
            continue

        try:
            #  HASH (SHA-256) - Cadeia de Custódia
            hash_id = gerar_hash_sha256(img_path)
            
            # DETECÇÃO ENSEMBLE (YOLO -> Fallback SSD)
            # Retorna dados binários biométrico assíncrono estritamente sequencial
            crop_binary = detector.detectar_e_recortar(img_path)
            
            if not crop_binary:
                # Nenhuma face encontrada, pula
                continue

            #  VETORIZAÇÃO (ArcFace 512-D)
            embedding_512 = vetorizador.vetorizar(crop_binary)

            # SALVAR NO DISCO LOCAL
            # Gera nome de arquivo único para o crop para evitar colisões
            crop_filename = f"{uuid.uuid4()}_face.jpg"
            target_crop_path = target_folder / crop_filename
            
            # Persiste binário no disco local físico
            with open(target_crop_path, "wb") as f:
                f.write(crop_binary) # Mock retorna bytes, real deve lidar com array de bytes

            # SALVAR NO POSTGRESQL (Vetores e Metadados)
            # METADADOS MOCKADOS
            fake_metadados = {
                "lote_origem_audit": lote_id_str,
                "status_triagem": "limpo", # Categoria face encontrada
                "model_yolo": "v8n",
                "model_arcface": "512-d",
                # Demográficos simulados JSONB para filtragem pericial
                "gender": "male" if total_imagens % 2 == 0 else "female",
                "ethnicity": "black" if hash_id[0] == 'a' else "caucasian",
                "device_model": "iPhone" if img_path.name.startswith('IMG_') else "Android"
            }

            nova_face = EvidenciaFacial(
                hash_sha256=hash_id,
                caminho_origem_bruta=str(img_path), # Caminho Local Bruto Absoluto
                caminho_local_crop=str(target_crop_path), # Caminho Local do Crop Absoluto[cite: 1.3.2]
                embedding=embedding_512,
                metadados_adicionais=fake_metadados,
                data_extracao=datetime.now()
            )
            db.add(nova_face)
            faces_processadas_sucesso += 1

            # --- DIAGNÓSTICO DE HARDWARE ---
            # Controle de Diagnóstico do consumo (CPU, RAM, Disco) biométrico assíncrono estritamente sequencial
            # Estamos rodando o monitor a cada 100 imagens para minimizar o impacto do diagnóstico biométrica local batch biométrica local batch estritamente sequencial
            if total_imagens % 100 == 0:
                print(f"[WORKER] Diagnósticos para o Lote {lote_id_str}: {total_imagens}/{len(lista_caminhos_imagens)} imagens...")
                log_hardware_diagnostic()

        except Exception as e:
            # Governança: Loga erro mas continua o lote. Rollback desta inserção.
            # cadeia de custódia: arquivos corrompidos ou inesperados não podem parar o processamento do lote Perícia Face[cite: 2].
            print(f"[ERRO] Falha ao processar {img_path.name} no Lote {lote_id_str}: {e}")
            db.rollback() 

    # FINALIZAÇÃO DE AUDITORIA FINAL: Define estado como CONCLUIDO no Postgres biométrica local Batch estritamente sequencial biométrica local batch
    print(f"[WORKER] FINALIZANDO Lote: {lote_id_str} | Faces de sucesso inseridas: {faces_processadas_sucesso}")
    
    query_final = text(f"UPDATE lotes_processamento SET status='CONCLUIDO', faces_extraidas={faces_processadas_sucesso}, data_fim='{datetime.now()}' WHERE id_lote='{lote_id_str}'")
    db.execute(query_final)
    # -----------------------------------------------------------

    db.commit() # Salva inserções de embedding e atualização de auditoria biométrica local batch
    db.close()
    
    return {"status": "batch_completed", "lote_audit": lote_id_str, "total_processed": total_imagens, "faces_extracted": faces_processadas_sucesso}