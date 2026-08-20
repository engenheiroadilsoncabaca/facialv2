# PeríciaFace-PR: Pipeline de Identificação Facial Pericial em Lote

> **Status:** Ambiente de Desenvolvimento Estabilizado (Windows/Gevent Pool)
> **Natureza:** Strategic/Restricted (SESP-PR)
> **Repositório:** Privado

## 1. Visão Geral

O **PeríciaFace-PR** é um sistema de governança biométrica local batch e processamento assíncrono desenvolvido para a SESP-PR. Ele foi projetado para lidar com o processamento automatizado de grandes volumes de imagens brutas locais, realizando detecção facial, extração de embeddings (vetorização) e garantindo a cadeia de custódia e auditoria forense de todo o processo.

O sistema utiliza arquitetura de filas para processamento paralelo biométrico assíncrono estritamente sequencial, estabilizado no ambiente Windows através do uso de pool `gevent` para gerenciar eficientemente as operações de I/O (disco e banco de dados).

## 2. Arquitetura do Sistema

O sistema adota uma arquitetura baseada em tarefas assíncronas (Master-Worker) para processamento paralelo:

```ascii
                      +-------------------+
                      |   task_scanner.py | (Orquestrador)
                      | (Varre pastas)    |
                      +--------+----------+
                               | (1. Cria Entrada de Auditoria no Postgres)
                               | (2. Submete Tasks ao Redis)
                               v
                      +--------+----------+
                      |      Redis        | (Broker de Mensagens)
                      +--------+----------+
                               |
                               | (3. Consome Tasks)
                               v
+------------------+  +--------+----------+  +------------------+
|   Worker 1 (gevent)|  | Worker 2 (gevent)|  | Worker N (gevent)| (Workers Assíncronos)
| (IA & Disco)     |  | (IA & Disco)     |  | (IA & Disco)     |
+--------+----------+  +--------+----------+  +--------+----------+
         |                    |                    |
         | (4. Grava Face)    | (4. Grava Face)    | (4. Grava Face)
         +--------------------+--------------------+
         |                    |
         v                    v
+--------+----------+  +--------+----------+
|   Disco Local    |  |    PostgreSQL     | (Backend de Dados & Auditoria)
| (Crops/.jpg)     |  | (Embeddings &     |
|                  |  | Metadados/Status) |
+-------------------+  +------------------+
