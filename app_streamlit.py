import streamlit as st
import os
import cv2
import numpy as np
import pandas as pd
import warnings
import time
from pathlib import Path
from sqlalchemy import text

from app.core.config import settings
from app.core.database import SessionLocal
from app.tasks.hunter_ai import biometric_engine

warnings.filterwarnings('ignore', category=FutureWarning)

st.set_page_config(layout="wide", page_title="Facial-Científica | Central SESP-PR", page_icon="🔬")

st.markdown("""
    <style>
    .main { background-color: #0b0f19; color: #f8fafc; }
    .stApp { background-color: #0b0f19; color: #f8fafc; }
    p, span, label, div { color: #cbd5e1; }
    .stMarkdown p { color: #cbd5e1 !important; font-size: 0.95rem; }
    
    [data-testid="stSidebar"],
    [data-testid="stSidebar"] p, 
    [data-testid="stSidebar"] span, 
    [data-testid="stSidebar"] label, 
    [data-testid="stSidebar"] div,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 { 
        color: #000000 !important; 
    }

    .pericia-header {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        padding: 24px 32px;
        border-radius: 8px;
        border-left: 4px solid #3b82f6;
        margin-bottom: 24px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }
    .pericia-title {
        color: #f8fafc !important;
        font-size: 1.75rem;
        font-weight: 600;
        margin: 0 0 8px 0;
        letter-spacing: -0.025em;
    }
    .pericia-subtitle {
        color: #94a3b8 !important;
        font-size: 0.95rem;
        margin: 0;
    }
    .metric-card-clean, .metric-card-alert {
        background-color: #1e293b;
        padding: 16px;
        border-radius: 8px;
        text-align: center;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
        border: 1px solid #334155;
    }
    .metric-card-clean { border-top: 3px solid #3b82f6; }
    .metric-card-alert { border-top: 3px solid #ef4444; }
    .metric-val {
        font-size: 1.75rem;
        font-weight: 700;
        margin: 0;
        line-height: 1.2;
    }
    .metric-lbl {
        font-size: 0.75rem;
        color: #94a3b8 !important;
        margin: 8px 0 0 0;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
    }
    .badge-lote, .badge-reincidente {
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.75rem;
        letter-spacing: 0.025em;
    }
    .badge-lote { background-color: #3b82f6; color: #ffffff !important; }
    .badge-reincidente { background-color: #ef4444; color: #ffffff !important; }
    </style>
""", unsafe_allow_html=True)

def obter_estatisticas_banco():
    db = SessionLocal()
    try:
        total_lotes = db.execute(text("SELECT COUNT(*) FROM lotes_processamento;")).scalar() or 0
        lotes_concluidos = db.execute(text("SELECT COUNT(*) FROM lotes_processamento WHERE status='CONCLUIDO';")).scalar() or 0
        total_evidencias = db.execute(text("SELECT COUNT(*) FROM evidencias_faciais;")).scalar() or 0
        
        # Agrupamento de indivíduos únicos a partir dos metadados JSONB
        total_individuos = db.execute(text("SELECT COUNT(DISTINCT metadados_adicionais->>'individuo_id') FROM evidencias_faciais;")).scalar() or 0
        reincidentes = db.execute(text("SELECT COUNT(*) FROM (SELECT metadados_adicionais->>'individuo_id' FROM evidencias_faciais GROUP BY metadados_adicionais->>'individuo_id' HAVING COUNT(*) > 1) sub;")).scalar() or 0
        
        return {
            "total_lotes": total_lotes,
            "lotes_concluidos": lotes_concluidos,
            "total_evidencias": total_evidencias,
            "total_individuos": total_individuos,
            "reincidentes": reincidentes
        }
    finally:
        db.close()

def buscar_similaridade_referencia(vetor_query, limite_distancia=0.45):
    db = SessionLocal()
    try:
        embedding_str = f"[{','.join(map(str, vetor_query))}]"
        query = text("""
            SELECT 
                metadados_adicionais->>'individuo_id' as ind_id,
                metadados_adicionais->>'pasta_origem' as origem,
                caminho_local_crop,
                caminho_origem_bruta,
                data_extracao,
                (embedding <=> CAST(:emb AS vector)) AS distancia
            FROM evidencias_faciais
            WHERE (embedding <=> CAST(:emb AS vector)) < :limite
            ORDER BY distancia ASC;
        """)
        resultados = db.execute(query, {"emb": embedding_str, "limite": limite_distancia}).fetchall()
        return resultados
    finally:
        db.close()

@st.fragment(run_every="3s")
def monitorar_progresso_fragment():
    stats = obter_estatisticas_banco()
    
    col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)
    with col_s1:
        st.markdown(f'<div class="metric-card-clean"><p class="metric-val" style="color:#3b82f6;">{stats["total_lotes"]}</p><p class="metric-lbl">Total Lotes</p></div>', unsafe_allow_html=True)
    with col_s2:
        st.markdown(f'<div class="metric-card-clean"><p class="metric-val" style="color:#10b981;">{stats["lotes_concluidos"]}</p><p class="metric-lbl">Lotes Finalizados</p></div>', unsafe_allow_html=True)
    with col_s3:
        st.markdown(f'<div class="metric-card-clean"><p class="metric-val" style="color:#f59e0b;">{stats["total_evidencias"]}</p><p class="metric-lbl">Faces Extraídas</p></div>', unsafe_allow_html=True)
    with col_s4:
        st.markdown(f'<div class="metric-card-alert"><p class="metric-val" style="color:#ef4444;">{stats["total_individuos"]}</p><p class="metric-lbl">Cadastros Únicos</p></div>', unsafe_allow_html=True)
    with col_s5:
        st.markdown(f'<div class="metric-card-clean"><p class="metric-val" style="color:#3b82f6;">{stats["reincidentes"]}</p><p class="metric-lbl">Reincidentes</p></div>', unsafe_allow_html=True)

def carregar_painel():
    st.markdown("""
        <div class="pericia-header">
            <h1 class="pericia-title">Facial-Científica | Painel Unificado SESP-PR (V2)</h1>
            <p class="pericia-subtitle">Varredura distribuída, extração biométrica ArcFace 512-D e identificação de reincidentes.</p>
        </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("### ⚙️ Calibração Forense")
    tolerancia_match = st.sidebar.slider("Tolerância de Match (Cosseno)", 0.30, 0.60, 0.45, 0.01)
    st.sidebar.markdown("---")
    st.sidebar.info(f"**Modo de Execução:** {'GPU (CUDA)' if settings.USE_GPU else 'CPU Multi-Core'}")

    aba1, aba2, aba3 = st.tabs([
        "🔬 Processamento e Monitoramento",
        "📂 Auditoria de Reincidentes",
        "🔎 Busca Biométrica por Imagem"
    ])

    with aba1:
        st.subheader("Processamento de Evidências em Lote")
        st.caption("Acompanhamento das filas do Redis e gravações no PostgreSQL pgvector.")
        
        st.text_input("Diretório de Origem (Entradas Brutas):", value=settings.PATH_IMAGENS_BRUTAS, disabled=True)
        st.text_input("Diretório de Destino (Crops Organizados):", value=settings.PATH_RECORTES_CROPS, disabled=True)

        st.write("")
        monitorar_progresso_fragment()

    with aba2:
        st.subheader("Auditoria de Identidades e Reincidências")
        pasta_crops_audit = Path(settings.PATH_RECORTES_CROPS)
        
        if os.path.exists(pasta_crops_audit):
            with st.spinner("Compilando e indexando registros armazenados em disco..."):
                # Varre a estrutura: PATH_CROPS / <origem> / <individuo_id> / <crop.jpg>
                dados_suspeitos = []
                pastas_origem = [d for d in pasta_crops_audit.iterdir() if d.is_dir()]
                
                mapa_individuos = {}
                for p_origem in pastas_origem:
                    pastas_ind = [d for d in p_origem.iterdir() if d.is_dir()]
                    for p_ind in pastas_ind:
                        ind_id = p_ind.name
                        fotos = list(p_ind.glob("*.jpg")) + list(p_ind.glob("*.png"))
                        
                        if ind_id not in mapa_individuos:
                            mapa_individuos[ind_id] = {"fotos": [], "origens": set()}
                        
                        mapa_individuos[ind_id]["fotos"].extend(fotos)
                        mapa_individuos[ind_id]["origens"].add(p_origem.name)

                reincidentes_count = 0
                for ind_id, info in mapa_individuos.items():
                    qtd_fotos = len(info["fotos"])
                    eh_reincidente = qtd_fotos > 1 or len(info["origens"]) > 1
                    if eh_reincidente:
                        reincidentes_count += 1
                    
                    dados_suspeitos.append({
                        "id": ind_id,
                        "fotos": info["fotos"],
                        "qtd_fotos": qtd_fotos,
                        "origens": list(info["origens"]),
                        "reincidente": eh_reincidente
                    })

            col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
            with col_kpi1: st.markdown(f'<div class="metric-card-clean"><p class="metric-val" style="color:#3b82f6;">{len(mapa_individuos)}</p><p class="metric-lbl">Total Indivíduos</p></div>', unsafe_allow_html=True)
            with col_kpi2: st.markdown(f'<div class="metric-card-alert"><p class="metric-val" style="color:#ef4444;">{reincidentes_count}</p><p class="metric-lbl">Reincidentes</p></div>', unsafe_allow_html=True)
            with col_kpi3: st.markdown(f'<div class="metric-card-clean"><p class="metric-val" style="color:#10b981;">{sum(len(v["fotos"]) for v in mapa_individuos.values())}</p><p class="metric-lbl">Total Evidências Crops</p></div>', unsafe_allow_html=True)

            st.write("")
            col_filtro1, col_filtro2 = st.columns([1.2, 2])
            with col_filtro1:
                filtro_modo = st.radio("Critério de Exibição:", ["Apenas Reincidentes", "Todos os Registros"], horizontal=True, key="filtro_auditoria")
            with col_filtro2:
                termo_busca = st.text_input("Filtrar por ID do Indivíduo ou Lote:", value="", key="busca_auditoria").strip().lower()

            st.write("")
            
            dados_filtrados = []
            for item in dados_suspeitos:
                if filtro_modo == "Apenas Reincidentes" and not item["reincidente"]: continue
                if termo_busca and not (termo_busca in item["id"].lower() or any(termo_busca in o.lower() for l in item["origens"] for o in [l])): continue
                dados_filtrados.append(item)
            
            LIMITE_EXIBICAO = 50
            for item in dados_filtrados[:LIMITE_EXIBICAO]:
                status_badge = '<span class="badge-reincidente">REINCIDENTE</span>' if item["reincidente"] else '<span class="badge-lote">REGISTRO ÚNICO</span>'
                with st.expander(f"Indivíduo: {item['id']} | {item['qtd_fotos']} evidência(s)", expanded=False):
                    st.markdown(f"{status_badge} &nbsp; <span style='color:#94a3b8; font-size:0.85rem;'><b>Lotes de Origem:</b> {', '.join(item['origens'])}</span>", unsafe_allow_html=True)
                    st.write("")
                    cols = st.columns(min(len(item["fotos"]), 7))
                    for idx, foto_path in enumerate(item["fotos"][:14]):
                        with cols[idx % 7]:
                            if os.path.exists(foto_path):
                                st.image(str(foto_path), width=100)

    with aba3:
        st.subheader("Busca Biométrica de Referência (1:N)")
        c1, c2 = st.columns([1.2, 1])
        
        with c1:
            uploaded_file = st.file_uploader("Selecionar Arquivo para Consulta:", type=["jpg", "jpeg", "png"], key="up_ref")
            img_bgr = None
            if uploaded_file is not None:
                imagem_bytes_upload = uploaded_file.read()
                nparr = np.frombuffer(imagem_bytes_upload, np.uint8)
                img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        with c2:
            if img_bgr is not None:
                st.image(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB), width=180, caption="Imagem de Referência")

        if st.button("Executar Pesquisa Vetorial", type="primary", key="btn_ref"):
            if img_bgr is None:
                st.error("Forneça uma imagem válida.")
            else:
                with st.spinner("Extraindo vetor ArcFace 512-D e consultando o banco pgvector..."):
                    crop_binary, embedding_512, _ = biometric_engine.processar_imagem(uploaded_file.name)
                    
                    if not embedding_512:
                        # Se for um upload direto via array do OpenCV
                        faces = biometric_engine.app.get(img_bgr)
                        if faces:
                            face_p = max(faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]))
                            emb = face_p.embedding / np.linalg.norm(face_p.embedding)
                            embedding_512 = emb.tolist()

                    if not embedding_512:
                        st.warning("Não foi possível isolar características faciais na imagem.")
                    else:
                        resultados = buscar_similaridade_referencia(embedding_512, limite_distancia=tolerancia_match)
                        
                        if not resultados:
                            st.info("Nenhuma correspondência histórica encontrada no banco de dados.")
                        else:
                            st.success(f"{len(resultados)} correspondência(s) encontrada(s)!")
                            
                            df_res = []
                            for r in resultados:
                                df_res.append({
                                    "Indivíduo ID": r.ind_id,
                                    "Origem Lote": r.origem,
                                    "Distância Cosseno": round(float(r.distancia), 4),
                                    "Data Extração": r.data_extracao,
                                    "Caminho Crop": r.caminho_local_crop
                                })
                            
                            st.dataframe(pd.DataFrame(df_res))
                            
                            st.write("#### Galeria de Correspondências")
                            cols_match = st.columns(min(len(resultados), 5))
                            for idx_m, r in enumerate(resultados[:5]):
                                with cols_match[idx_m]:
                                    if os.path.exists(r.caminho_local_crop):
                                        st.image(r.caminho_local_crop, width=120, caption=f"Dist: {r.distancia:.4f}")

if __name__ == "__main__":
    carregar_painel()