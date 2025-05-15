import re
from datetime import datetime

def clean_monetary_value(value):
    """Limpeza robusta de valores monetários"""
    if not value:
        return None
    try:
        # Remove todos os pontos e substitui vírgula por ponto
        cleaned = value.replace('R$', '').strip()
        cleaned = cleaned.replace('.', '').replace(',', '.')
        # Remove caracteres não numéricos exceto ponto
        cleaned = re.sub(r'[^\d.]', '', cleaned)
        return float(cleaned)
    except:
        return None

def parse_amazonas_energia_text(text):
    """Parser otimizado para faturas"""
    data = {
        'cliente': {
            'nome': None,
            'endereco': None,
            'documento': None,
            'uc': None,
            'rota': None
        },
        'fatura': {
            'numero': None,
            'emissao': None,
            'vencimento': None,
            'valor_total': None,
            'codigo_barras': None,
            'chave_acesso': None
        },
        'medicao': {
            'medidor': None,
            'leitura_atual': None,
            'leitura_anterior': None,
            'consumo_kwh': None,
            'dias_consumo': None,
            'constante': None,
            'proxima_leitura': None
        },
        'tarifas': {
            'valor_energia': None,
            'valor_cosip': None,
            'tarifa_ponta': None,
            'tarifa_fora_ponta': None,
            'icms': None,
            'total': None,
            'detalhes': []
        }
    }

    # Padrões otimizados com fallbacks
    patterns = {
        # Cliente
        'cliente.nome': r'(?:Cliente:\s*|NOME[:\s]*)([^\n]+)(?=\n|$)',
        'cliente.endereco': r'(?:Endereço[:\s]*|R\.\s*)([^\n]+?)(?=\n|CEP|$)',
        'cliente.uc': r'(?:UC[:\s]*|Unidade\s*Consumidora[:\s]*)([A-Z0-9-]+)',
        
        # Fatura
        'fatura.numero': r'(?:N°?\s*Fatura[:\s]*|NOTA\s*FISCAL\s*N°?\s*)([0-9]+)',
        'fatura.emissao': r'(?:Emissão[:\s]*|DATA\s*DE\s*EMISSÃO[:\s]*)(\d{2}/\d{2}/\d{4})',
        'fatura.valor_total': r'(?:VALOR\s*A\s*PAGAR|TOTAL\s*DA\s*FATURA)[:\s]*R\$\s*([\d.,]+)',
        
        # Medição
        'medicao.medidor': r'(?:Medidor[:\s]*|N°?\s*Medidor[:\s]*)(\d+)',
        'medicao.consumo_kwh': r'(?:CONSUMO\s*\(kWh\)|Energia\s*Ativa)[:\s]*(\d+)',
        
        # Tarifas (padrões flexíveis)
        'tarifas.valor_energia': r'(?:ENERGIA\s*(?:EL[ÉE]TRICA)?|Consumo\s*de\s*energia)[^\d]*R\$\s*([\d.,]+)',
        'tarifas.valor_cosip': r'(?:COSIP|Contrib\.\s*Ilum)[^\d]*R\$\s*([\d.,]+)',
        'tarifas.tarifa_ponta': r'(?:TARIFA\s*PONTA|Ponta\s*\(\w+\))[^\d]*R\$\s*([\d.,]+)',
        'tarifas.tarifa_fora_ponta': r'(?:TARIFA\s*FORA\s*PONTA|Fora\s*Ponta\s*\(\w+\))[^\d]*R\$\s*([\d.,]+)',
        'tarifas.icms': r'(?:ICMS|Imposto)[^\d]*R\$\s*([\d.,]+)',
        'tarifas.total': r'(?:TOTAL\s*(?:A\s*PAGAR)?|VALOR\s*FINAL)[^\d]*R\$\s*([\d.,]+)'
    }

    # Extração básica com regex
    for field, pattern in patterns.items():
        try:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                value = match.group(1).strip()
                section, key = field.split('.')
                
                if 'valor' in key or 'total' in key or 'tarifa' in key:
                    cleaned_value = clean_monetary_value(value)
                    if cleaned_value:
                        data[section][key] = cleaned_value
                else:
                    data[section][key] = value
        except:
            continue

    # Extração detalhada de tarifas
    tarifa_patterns = [
        (r'(.*?)\s*R\$\s*([\d.,]+)', 'item', 'valor'),
        (r'(.*?)\s+(\d+)\s*kWh\s*R\$\s*([\d.,]+)', 'item', 'kwh', 'valor')
    ]
    
    for pattern in tarifa_patterns:
        matches = re.finditer(pattern[0], text, re.IGNORECASE)
        for match in matches:
            detail = {}
            for i, group in enumerate(pattern[1:]):
                if i+1 < len(match.groups()):
                    value = match.group(i+1).strip()
                    if group == 'valor':
                        value = clean_monetary_value(value)
                    detail[group] = value
            
            if detail:
                data['tarifas']['detalhes'].append(detail)

    return data