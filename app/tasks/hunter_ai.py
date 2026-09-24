import cv2
import numpy as np
from insightface.app import FaceAnalysis
from app.core.config import settings

class RealBiometricEngine:
    """
    Engine Biométrica de Produção baseada em InsightFace (RetinaFace + ArcFace 512-D).
    Alterna dinamicamente entre GPU (CUDA) e CPU via .env.
    """
    def __init__(self):
        if settings.USE_GPU:
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            ctx_id = 0
            det_size = (640, 640)
            print("[HUNTER AI] Inicializando Engine Biométrica com suporte a GPU (CUDA)...")
        else:
            providers = ['CPUExecutionProvider']
            ctx_id = -1
            det_size = (320, 320)  # Resolução otimizada para alto throughput em CPU
            print("[HUNTER AI] Inicializando Engine Biométrica em modo CPU (320x320)...")

        self.app = FaceAnalysis(name='buffalo_l', providers=providers)
        self.app.prepare(ctx_id=ctx_id, det_size=det_size)

    def processar_imagem(self, path_imagem):
        img = cv2.imread(str(path_imagem))
        if img is None:
            return None, None, None

        faces = self.app.get(img)
        if not faces:
            return None, None, None

        # Seleciona a face principal (maior bounding box)
        face_principal = max(faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]))

        bbox = face_principal.bbox.astype(int)
        x1, y1, x2, y2 = max(0, bbox[0]), max(0, bbox[1]), max(0, bbox[2]), max(0, bbox[3])

        crop_img = img[y1:y2, x1:x2]
        if crop_img.size == 0:
            return None, None, None

        success, encoded_image = cv2.imencode('.jpg', crop_img)
        if not success:
            return None, None, None

        crop_bytes = encoded_image.tobytes()

        # Extrai vetor 512-D e normaliza
        embedding = face_principal.embedding
        embedding_norm = embedding / np.linalg.norm(embedding)
        embedding_list = embedding_norm.tolist()

        demografia = {
            "gender": "male" if face_principal.gender == 1 else "female",
            "age": int(face_principal.age),
            "det_score": float(face_principal.det_score)
        }

        return crop_bytes, embedding_list, demografia

biometric_engine = RealBiometricEngine()