import psutil
import logging
import os
import datetime
from app.core.config import settings

# Configuração do arquivo de log de diagnóstico
log_path = os.path.join(settings.PATH_RECORTES_CROPS, 'hunter_hardware_diag.log')
logging.basicConfig(filename=log_path, level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def log_hardware_diagnostic():
    """
    Registra um instantâneo instantâneo do uso de CPU, RAM e Disco Local.
    Necessário para governança e prevenção de falhas do sistema durante o lote 5k.
    """
    try:
        # RAM do Sistema
        mem = psutil.virtual_memory()
        ram_uso_percent = mem.percent
        ram_disponivel_gb = mem.available / (1024**3)

        # Uso da CPU (Média em todos os núcleos)
        cpu_uso_percent = psutil.cpu_percent(interval=None)

        # Uso do Disco Local (HD/SSD onde os crops são armazenados)
        disk = psutil.disk_usage(settings.PATH_RECORTES_CROPS)
        disco_uso_percent = disk.percent
        disco_livre_gb = disk.free / (1024**3)

        # Processo Python Atual (Memory rss/leaks)
        process = psutil.Process(os.getpid())
        python_ram_rss_mb = process.memory_info().rss / (1024**2)

        # Input de log
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = (
            f"DIAG [{timestamp}] | CPU: {cpu_uso_percent}% | "
            f"RAM Sistema: {ram_uso_percent}% ({ram_disponivel_gb:.2f}GB Livre) | "
            f"RAM Python: {python_ram_rss_mb:.2f}MB | "
            f"Disco: {disco_uso_percent}% ({disco_livre_gb:.2f}GB Livre)"
        )
        
        logging.info(msg)
        print(msg) # Útil durante o log de execução

        # Alertas de limiar crítico
        if ram_uso_percent > 90:
            logging.warning(" CRÍTICO: Uso de RAM do Sistema acima de 90%!")

    except Exception as e:
        logging.error(f"Falha ao coletar diagnóstico de hardware: {e}")