# import os
# import time
# import uuid
# import datetime
# from pathlib import Path
# from sqlalchemy import text
# from celery import Celery, group
# # Modelos do app e config
# from app.core.config import settings
# from app.core.database import SessionLocal

# # Configura a instância do Celery do Orquestrador dentro do task_scanner[cite: 1.1.1]
# app = Celery('hunter_orchestrator', broker=settings.CELERY_BROKER_URL)

# def chunks(lst, n):
#     """Divide uma lista em pacotes de tamanho N."""
#     for i in range(0, len(lst), n):
#         yield lst[i:i + n]

# def orquestrar_processamento():
#     """
#     Lógica Principal (Orquestrador para processamento em lote da Polícia Científica)[cite: 2, 1.1.1]:
#     1. Lê as 3-4 Pastas Brutas locais.
#     2. Processa **uma pasta por vez estritamente sequencial**.
#     3. Escaneia a pasta, cria lotes de auditoria (SQLAlchemy), fatia caminhos em lotes de 5.000.
#     4. Submete lotes aos workers paralelos.
#     5. **Aguarda confirmação do Redis** de que o grupo de processamento de lotes da pasta anterior está concluído
#        antes de saltar automaticamente para a próxima pasta.
#     """
#     path_brutas_raiz = Path(settings.PATH_IMAGENS_BRUTAS)
    
#     if not path_brutas_raiz.exists():
#         print(f"[ERRO] PATH_IMAGENS_BRUTAS não encontrado: {path_brutas_raiz}")
#         return

#     #  LÊ AS PASTAS BASE (Pastas Sequenciais DATA/HORA/NOME)
#     # Mapeia fisicamente: Pasta A, Pasta B...
#     # Exigimos processar a Pasta A completamente antes da B.
#     pastas_bases_prio = sorted([f for f in path_brutas_raiz.iterdir() if f.is_dir()])
    
#     if not pastas_bases_prio:
#         print("[ORQUESTRADOR] Nenhuma pasta bruta encontrada. Sistema ocioso.")
#         return

#     print(f"[ORQUESTRADOR] {len(pastas_bases_prio)} Pastas encontradas para processamento estrito sequencial.")

#     for pasta_base in pastas_bases_prio:
#         print(f"--- [INICIANDO PASTA BASE]: {pasta_base.name} | Estritamente Sequencial ---")
        
#         # COLETA CAMINHOS ABSOLUTOS LOCAIS de todos os arquivos brutos suportados dentro desta pasta
#         imagens_brutas_caminhos = []
#         for extensao in ['*.jpg', '*.jpeg', '*.png']:
#             imagens_brutas_caminhos.extend([str(img.resolve()) for img in pasta_base.glob(extensao)])

#         total_imagens_base = len(imagens_brutas_caminhos)
#         if total_imagens_base == 0:
#             print(f"[ORQUESTRADOR] PULADO: Pasta base '{pasta_base.name}' está vazia.")
#             continue

#         print(f"[ORQUESTRADOR] Pasta base '{pasta_base.name}': {total_imagens_base} imagens encontradas. Chunks de 5k...")

#         # CHUNKS (Lotes de 5.000) [cite: 1.1.1]
#         lotes_5000 = list(chunks(imagens_brutas_caminhos, 5000))
#         num_lotes = len(lotes_5000)

#         # PREPARA DADOS DE SUBMISSÃO EM LOTE (Auditoria no Banco)
#         job_tasks_signatures = []
        
#         for index, lote_5k in enumerate(lotes_5000):
#             # Cria entrada de Auditoria no SQLAlchemy (lotes_processamento)
#             lote_uuid = uuid.uuid4()
            
#             data_lote = {
#                 "id_lote_audit": str(lote_uuid),
#                 "caminho_base": str(pasta_base), # Auditoria precisa do nome da Pasta Base (DATA/HORA/NOME)
#             }
            
#             # PERSISTE AUDITORIA NO POSTGRES (O estado será atualizado pelo Worker)
#             # inserções de auditoria no banco de dados são simples para PoC
#             # lógica de inserção...
#             db = SessionLocal()
#             print(f"[MONITOR DB] Inserindo entrada de auditoria para a Pasta Base '{pasta_base.name}' [Lote {index+1}/{num_lotes}] -> ID: {str(lote_uuid)}")
#             query_log = text(f"INSERT INTO lotes_processamento (id_lote, caminho_diretorio_base, status, data_inicio) VALUES ('{str(lote_uuid)}', '{str(pasta_base)}', 'AGUARDANDO_WORKER', '{datetime.datetime.now()}')")
#             db.execute(query_log)
#             db.commit()
#             db.close()

#             # Cria assinaturas de Grupo paralelas
#             # Assinatura: função da tarefa celery, arg (lista de caminhos), kwarg (data_lote com ID de auditoria)
#             job_tasks_signatures.append(app.signature("hunter.processar_lote_5k", args=[lote_5k, data_lote]))

#         # SUBMETE GRUPO EM LOTE (Redis Broker)
#         print(f"[ORQUESTRADOR] Submetendo {num_lotes} Lotes (5.000 tarefas paralelas) ao Redis para a Pasta Base '{pasta_base.name}'...")
#         # group() submete múltiplas tarefas e retorna um objeto de resultado de grupo
#         group_job_result = group(job_tasks_signatures)()

#         # LÓGICA DE ESPERA ESTRITAMENTE SEQUENCIAL [cite: 1.1.1]
#         # Monitora o Resultado do Grupo do Celery para aguardar a conclusão de *todos* os 5.000 lotes dentro *desta* Pasta Base específica.
#         # NÃO processa a Pasta B ainda.
#         print(f"[ORQUESTRADOR] --- MONITORANDO: Aguardando confirmação dos workers para todos os {num_lotes} lotes de '{pasta_base.name}' ---")
        
#         completed_lotes_prev = 0
#         while not group_job_result.ready():
#             completed_lotes = group_job_result.completed_count()
#             if completed_lotes != completed_lotes_prev:
#                 completed_lotes_prev = completed_lotes
#                 print(f"[MONITOR] Pasta Base '{pasta_base.name}': {completed_lotes}/{num_lotes} lotes processados no grupo de lotes paralelo...")
            
#             time.sleep(10) # Polling do Redis: Pesquisa o estado a cada 10 segundos.
            
#         print(f"--- [PASTA BASE CONCLUÍDA]: '{pasta_base.name}' | PASSAGEM DE CHECKPOINT ESTRITAMENTE SEQUENCIAL ---")
#         # Agora saltando automaticamente para a próxima pasta em 'pastas_bases_prio'

#     print("[ORQUESTRADOR] Processamento automático de lotes de pastas estritamente sequencial concluído[cite: 1.1.1, 6].")

# if __name__ == "__main__":
#     # Ao executar task_scanner diretamente, orquestrar_processamento executa sequencialmente pasta por pasta, 
#     # mas os próprios lotes rodam em workers paralelos[cite: 1.1.1, 4].
#     orquestrar_processamento()

import os
import time
import uuid
import datetime
import logging
from pathlib import Path
# Importação do fixed text e tratamento de exceção para governança 
from sqlalchemy import text, exc
from celery import Celery, group
# Modelos do app e config locais físicos varridas locally fatiando lotes e aguardando confirmação
from app.core.config import settings
from app.core.database import SessionLocal


print(f"\n[DEBUG 1] Script task_scanner.py carregado básicos. Hora: {datetime.datetime.now()}")

# Incluindo result_backend apontando para o Redis (igual ao broker) para permitir monitoramento
print(f"[DEBUG 2] Configurando Celery Orquestrador com Broker: {settings.CELERY_BROKER_URL}")
app = Celery(
    'hunter_orchestrator',
    broker=settings.CELERY_BROKER_URL,
    result_backend=settings.CELERY_BROKER_URL # Usando Redis para resultados também
)

def chunks(lst, n):
    """Divide uma lista em pacotes de tamanho N."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def orquestrar_processamento():
    """
    Lógica Principal do Orquestrador (Polícia Científica do Paraná)[cite: 2, 1.1.1, image_3.png, 6]:
    Escaneia pastas locais de imagens brutas, fatiando os lotes e aguardando confirmação do Redis antes de pular para a próxima pasta automaticamente
    """

    print(f"[DEBUG 3] Iniciando função orquestrar_processamento(). Hora: {datetime.datetime.now()}")

    path_brutas_raiz = Path(settings.PATH_IMAGENS_BRUTAS)
    
    print(f"[DEBUG 4] PATH_IMAGENS_BRUTAS lido do .env locais físicos: {path_brutas_raiz}")

    if not path_brutas_raiz.exists():
        print(f"[ERRO] PATH_IMAGENS_BRUTAS não encontrado: {path_brutas_raiz}")
      
        print(f"[DEBUG 5] Encerrando orquestrador porque o caminho não existe.")
        return
    
    # Mapeia fisicamente as pastas brutas locais, exigindo processar a Pasta A completamente antes da B.
    pastas_bases_prio = sorted([f for f in path_brutas_raiz.iterdir() if f.is_dir()])
    
    print(f"[DEBUG 6] Pastas encontradas no diretório bruta: {pastas_bases_prio}")

    if not pastas_bases_prio:
        print("[ORQUESTRADOR] Nenhuma pasta bruta encontrada. Sistema ocioso.")
        return

    print(f"[ORQUESTRADOR] {len(pastas_bases_prio)} Pastas encontradas para processamento estrito sequencial.")

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
        
        print(f"[DEBUG 7] Fatiamento em {num_lotes} chunks de 5k. Hora: {datetime.datetime.now()}")

        for index, lote_5k in enumerate(lotes_5000):
          
            lote_uuid = uuid.uuid4()
            
            data_lote = {
                "id_lote_audit": str(lote_uuid),
                "caminho_base": str(pasta_base), 
            }
            
            print(f"[MONITOR DB] Inserindo entrada de auditoria para '{pasta_base.name}' [Lote {index+1}/{num_lotes}] -> ID: {str(lote_uuid)}")
            
            # Lógica de inserção de auditoria no banco de dados com tratamento de erro e fixed text()
            try:
                db = SessionLocal()
              
                query_log = text(f"INSERT INTO lotes_processamento (id_lote, caminho_diretorio_base, status, data_inicio) VALUES ('{str(lote_uuid)}', '{str(pasta_base)}', 'AGUARDANDO_WORKER', '{datetime.datetime.now()}')")
                db.execute(query_log)
                db.commit()
            except exc.SQLAlchemyError as e:
                print(f"[ERRO DB] Falha ao inserir log de auditoria forense: {e}")
                db.rollback()
                # Interrompe o orquestrador se falhar a governança biométrica local
                raise 
            finally:
                db.close()

            job_tasks_signatures.append(app.signature("hunter.processar_lote_5k", args=[lote_5k, data_lote]))

     
        print(f"[DEBUG 8] Lotes de auditoria forense criados. Submetendo grupo ao Redis. Hora: {datetime.datetime.now()}")

        # SUBMETE GRUPO EM LOTE (broker_connection_retry_on_startup to True 
        print(f"[ORQUESTRADOR] Submetendo {num_lotes} Lotes paralelos do Redis para '{pasta_base.name}'...")
        # group() submete múltiplas tarefas e retorna um objeto de resultado de grupo
        group_job_result = group(job_tasks_signatures)()

     
        print(f"[ORQUESTRADOR] --- MONITORANDO: Aguardando workers para {num_lotes} lotes de '{pasta_base.name}' ---")
        
        completed_lotes_prev = -1 # Inicializa para garantir a primeira impressão do monitor
     
        while not group_job_result.ready():
          
            completed_lotes = group_job_result.completed_count()
            if completed_lotes != completed_lotes_prev:
                completed_lotes_prev = completed_lotes
                print(f"[MONITOR] '{pasta_base.name}': {completed_lotes}/{num_lotes} lotes paralelos processados no grupo de lotes paralelo...")
            
            # loop locally 
            time.sleep(10) 
            
        print(f"--- [PASTA BASE CONCLUÍDA]: '{pasta_base.name}' | CHECKPOINT ESTRITAMENTE SEQUENCIAL ---")

    print("\n[ORQUESTRADOR] Processamento automático forense batch estritamente sequencial concluído[cite: 1.1.1, image_3.png, 6].")
    
    print(f"[DEBUG 9] Fim da função orquestrar_processamento(). Hora: {datetime.datetime.now()}")

print(f"[DEBUG 10] Fora da função, verificando __name__ == '__main__'. __name__ é: {__name__}")

if __name__ == "__main__":
   
    print(f"[DEBUG 11] Entrando no bloco __name__ == '__main__', chamando orquestrar_processamento().")
   
    orquestrar_processamento()
else:

    print(f"[DEBUG 12] Script não executado diretamente (importado como módulo). __name__ é: {__name__}")