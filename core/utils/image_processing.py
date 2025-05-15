import cv2
import numpy as np
import pytesseract
from PIL import Image
import io

import re
import os
from django.conf import settings

def auto_rotate_image(image):
    """Correção automática de orientação da imagem"""
    try:
        osd = pytesseract.image_to_osd(image)
        angle = int(re.search(r'Rotate: (\d+)', osd).group(1))
        if angle != 0:
            (h, w) = image.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(image, M, (w, h), 
                                   flags=cv2.INTER_CUBIC, 
                                   borderMode=cv2.BORDER_REPLICATE)
            return rotated
    except:
        pass
    return image

def adaptative_preprocessing(image_content):
    """Pré-processamento adaptativo baseado na qualidade da imagem"""
    try:
        # Converter conteúdo da imagem para array numpy
        nparr = np.frombuffer(image_content, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Verificar orientação e corrigir se necessário
        img = auto_rotate_image(img)
        
        # Redimensionar mantendo proporção (mínimo 1000px no menor lado)
        height, width = img.shape[:2]
        if min(height, width) < 1000:
            scale = 1000 / min(height, width)
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        
        # Converter para escala de cinza
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Detecção automática do melhor pré-processamento
        if is_low_contrast(gray):
            # Imagem com baixo contraste
            processed = enhance_low_contrast(gray)
        elif has_shadows(gray):
            # Imagem com sombras
            processed = remove_shadows(gray)
        else:
            # Processamento padrão para imagens boas
            processed = standard_enhancement(gray)
        
        return processed
    
    except Exception as e:
        raise RuntimeError(f"Erro no pré-processamento adaptativo: {str(e)}")

def is_low_contrast(image, threshold=30):
    """Detecta se a imagem tem baixo contraste"""
    return cv2.Laplacian(image, cv2.CV_64F).var() < threshold

def has_shadows(image):
    """Detecta se a imagem tem sombras significativas"""
    _, thresh = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return np.mean(thresh) < 100

def standard_enhancement(image):
    """Melhoria padrão para imagens de boa qualidade"""
    # Equalização de histograma adaptativo
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(image)
    
    # Suavização para reduzir ruído
    denoised = cv2.fastNlMeansDenoising(enhanced, None, 20, 7, 21)
    
    # Binarização adaptativa
    thresh = cv2.adaptiveThreshold(
        denoised, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )
    
    return thresh

def enhance_low_contrast(image):
    """Melhoria especial para imagens de baixo contraste"""
    # Equalização de histograma mais agressiva
    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(image)
    
    # Realce de bordas
    edges = cv2.Canny(enhanced, 50, 150)
    
    # Combinação com a imagem original
    result = cv2.addWeighted(enhanced, 0.7, edges, 0.3, 0)
    
    return result

def remove_shadows(image):
    """Remoção de sombras em imagens"""
    # Dilatação para encontrar fundo
    dilated = cv2.dilate(image, np.ones((7, 7), np.uint8))
    
    # Filtro de mediana para suavizar
    bg = cv2.medianBlur(dilated, 21)
    
    # Subtrair o fundo
    diff = 255 - cv2.absdiff(image, bg)
    
    # Normalizar o histograma
    norm = cv2.normalize(diff, None, alpha=0, beta=255, 
                        norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8UC1)
    
    return norm

def auto_rotate_image(image):
    """Correção automática de orientação usando OCR"""
    try:
        # Tentar detectar orientação com OCR
        osd = pytesseract.image_to_osd(image)
        angle = int(re.search('Rotate: (\d+)', osd).group(1))
        
        if angle != 0:
            # Rotacionar a imagem
            (h, w) = image.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(image, M, (w, h), 
                                   flags=cv2.INTER_CUBIC, 
                                   borderMode=cv2.BORDER_REPLICATE)
            return rotated
    except:
        pass
    
    return image

def extract_with_roi(image_path, roi_config):
    """
    Extrai texto de regiões específicas da fatura
    roi_config = {
        'nome_cliente': {'x': 100, 'y': 200, 'w': 300, 'h': 50},
        'numero_medidor': {'x': 400, 'y': 300, 'w': 200, 'h': 40},
        ...
    }
    """
    img = cv2.imread(image_path)
    results = {}
    
    for field, coords in roi_config.items():
        try:
            # Extrair ROI
            x, y, w, h = coords['x'], coords['y'], coords['w'], coords['h']
            roi = img[y:y+h, x:x+w]
            
            # Pré-processamento
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
            
            # OCR
            text = pytesseract.image_to_string(thresh, config='--psm 6 -l por')
            results[field] = text.strip()
        except:
            results[field] = None
    
    return results

def enhance_for_ocr(image):
    """Pipeline completo de pré-processamento"""
    # Correção de orientação
    image = auto_rotate_image(image)
    
    # Redimensionamento
    height, width = image.shape[:2]
    if min(height, width) < 1000:
        scale = 1000 / min(height, width)
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    
    # Conversão para escala de cinza
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Detecção do melhor pré-processamento
    if is_low_contrast(gray):
        processed = enhance_low_contrast(gray)
    elif has_shadows(gray):
        processed = remove_shadows(gray)
    else:
        processed = standard_enhancement(gray)
    
    return processed

def extract_text_from_image(image_path, config='--psm 6 -l por'):
    """Extrai texto com pré-processamento adaptativo"""
    try:
        if hasattr(settings, 'PYTESSERACT_CMD'):
            pytesseract.pytesseract.tesseract_cmd = settings.PYTESSERACT_CMD
        
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError("Não foi possível carregar a imagem")
        
        # Pré-processamento geral
        processed_img = enhance_for_ocr(img)
        
        # Configuração especial para valores monetários
        if 'tarifa' in image_path.lower() or 'valor' in image_path.lower():
            money_config = config + ' -c tessedit_char_whitelist=0123456789,R$., '
            text = pytesseract.image_to_string(processed_img, config=money_config)
        else:
            text = pytesseract.image_to_string(processed_img, config=config)
        
        return text
    
    except Exception as e:
        raise RuntimeError(f"Erro na extração de texto: {str(e)}")

def extract_tarifa_section(image_path):
    """Extrai especificamente a seção de tarifas"""
    img = cv2.imread(image_path)
    height, width = img.shape[:2]
    
    # ROI padrão para seção de tarifas (ajustar conforme necessário)
    roi = img[int(height*0.5):int(height*0.8), int(width*0.1):int(width*0.9)]
    
    # Pré-processamento especial para tabelas
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 15, 10
    )
    
    # Remoção de ruídos
    kernel = np.ones((2, 2), np.uint8)
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
    # OCR com configuração para tabelas
    text = pytesseract.image_to_string(
        cleaned,
        config='--psm 6 -l por --oem 1'
    )
    
    return text