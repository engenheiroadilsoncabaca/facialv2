import os
import time
import uuid
import datetime
import logging
from pathlib import Path
from sqlalchemy import text, exc
from celery import Celery, group

from app.core.config import settings
from app.core.database import SessionLocal

print(f"\n[ORQUESTRADOR] Script task_scanner.py carregado. Hora: {datetime.datetime.now()}")

app = Celery(
    'hunter_orchestrator',
    broker=settings.CELERY_BROKER_URL,
    result_backend=settings.CELERY_BROKER_URL
)

def chunks(lst, n):
    """Divide uma lista em pacotes de tamanho N."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def orquestrar_processamento():
    """
    Escaneia pastas locais de imagens brutas, fatiando os lotes e aguardando
    confirmação do Redis antes de passar para a próxima pasta sequencialmente.
    """
    print(f"[ORQUESTRADOR] Iniciando verificação de diretórios. Hora: {datetime.datetime.now()}")

    path_brutas_raiz = Path(settings.PATH_IMAGENS_BRUTAS)

    if not path_brutas_raiz.exists():
        print(f"[ERRO] PATH_IMAGENS_BRUTAS não encontrado: {path_brutas_raiz}")
        return
    
    pastas_bases_prio = sorted([f for f in path_brutas_raiz.iterdir() if f.is_dir()])

    if not pastas_bases_prio:
        print("[ORQUESTRADOR] Nenhuma pasta bruta encontrada. Sistema ocioso.")
        return

    print(f"[ORQUESTRADOR] {len(pastas_bases_prio)} Pasta(s) encontrada(s) para processamento estrito sequencial.")

    for pasta_base in pastas_bases_prio:
        print(f"\n--- [INICIANDO PASTA BASE]: {pasta_base.name} | Estritamente Sequencial ---")
        
        imagens_brutas_caminhos = []
        for extensao in ['*.jpg', '*.jpeg', '*.png']:
            imagens_brutas_caminhos.extend([str(img.resolve()) for img in pasta_base.glob(extensao)])

        total_imagens_base = len(imagens_brutas_caminhos)
        if total_imagens_base == 0:
            print(f"[ORQUESTRADOR] PULADO: Pasta base '{pasta_base.name}' está vazia.")
            continue

        print(f"[ORQUESTRADOR] Pasta base '{pasta_base.name}': {total_imagens_base} imagens encontradas. Chunks de 5k...")

        lotes_5000 = list(chunks(imagens_brutas_caminhos, 5000))
        num_lotes = len(lotes_5000)

        job_tasks_signatures = []

        for index, lote_5k in enumerate(lotes_5000):
            lote_uuid = uuid.uuid4()
            
            data_lote = {
                "id_lote_audit": str(lote_uuid),
                "caminho_base": str(pasta_base), 
            }
            
            print(f"[MONITOR DB] Registo de auditoria '{pasta_base.name}' [Lote {index+1}/{num_lotes}] -> ID: {str(lote_uuid)}")
            
            try:
                db = SessionLocal()
                query_log = text(f"INSERT INTO lotes_processamento (id_lote, caminho_diretorio_base, status, data_inicio) VALUES ('{str(lote_uuid)}', '{str(pasta_base)}', 'AGUARDANDO_WORKER', '{datetime.datetime.now()}')")
                db.execute(query_log)
                db.commit()
            except exc.SQLAlchemyError as e:
                print(f"[ERRO DB] Falha ao inserir log de auditoria: {e}")
                db.rollback()
                raise 
            finally:
                db.close()

            job_tasks_signatures.append(app.signature("hunter.processar_lote_5k", args=[lote_5k, data_lote]))

        print(f"[ORQUESTRADOR] Submetendo {num_lotes} Lotes ao Redis para '{pasta_base.name}'...")
        group_job_result = group(job_tasks_signatures)()

        print(f"[ORQUESTRADOR] Aguardando conclusão dos workers para '{pasta_base.name}'...")
        completed_lotes_prev = -1
     
        while not group_job_result.ready():
            completed_lotes = group_job_result.completed_count()
            if completed_lotes != completed_lotes_prev:
                completed_lotes_prev = completed_lotes
                print(f"[MONITOR] '{pasta_base.name}': {completed_lotes}/{num_lotes} lotes concluídos...")
            
            time.sleep(10) 
            
        print(f"--- [PASTA BASE CONCLUÍDA]: '{pasta_base.name}' ---")

    print("\n[ORQUESTRADOR] Processamento sequencial completo.")

if __name__ == "__main__":
    orquestrar_processamento()