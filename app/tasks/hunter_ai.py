import numpy as np
import uuid

# --- MOCKS ---
# Estes são placeholders. Substitua pelas importações reais de YOLO, SSD, ArcFace[cite: 4, 6]

class MockDetectorYOLO_SSD:
    """Simula Detecção Ensemble de Faces (YOLO + SSD Fallback)."""
    
    def detectar_e_recortar(self, path_imagem):
        """
        Tenta detecção YOLO primeiro. Se Confiança < limiar, roda fallback SSD[cite: 6].
        """
        import random
        dice = random.random()
        
        if dice > 0.1:
            print(f"[YOLO] Face detectada em {path_imagem.name}")
            return b"fake_crop_binary_from_yolo"
        elif dice > 0.02:
            print(f"[SSD FALLBACK] Face detectada em {path_imagem.name}")
            return b"fake_crop_binary_from_ssd"
        else:
            print(f"[IA] Nenhuma face encontrada em {path_imagem.name}")
            return None

class MockArcFaceVetorizador:
    """Simula Vetorização de Faces (ArcFace 512-D)."""
    
    def vetorizar(self, crop_data: bytes):
        """Converte crop em vetor 512-D[cite: 4]."""
        # ArcFace sempre cospe vetor denso 512-D normalizado
        embedding = np.random.rand(512).astype(np.float32)
        return embedding.tolist()

# Instâncias Singleton dentro do contexto do processo do worker
detector = MockDetectorYOLO_SSD()
vetorizador = MockArcFaceVetorizador()