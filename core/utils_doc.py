# energy_manager/core/utils_doc.py

TARIFAS_ESTADOS = {
    'Acre': 0.791,
    'Alagoas': 0.863,
    'Amapá': 0.808,
    'Amazonas': 0.857,
    'Bahia': 0.821,
    'Ceará': 0.722,
    'Distrito Federal': 0.743,
    'Espírito Santo': 0.682,
    'Goiás': 0.745,
    'Maranhão': 0.711,
    'Mato Grosso': 0.847,
    'Mato Grosso do Sul': 0.870,
    'Minas Gerais': 0.796,
    'Pará': 0.938,
    'Paraíba': 0.588,
    'Paraná': 0.629,
    'Pernambuco': 0.744,
    'Piauí': 0.829,
    'Rio de Janeiro': 0.870,
    'Rio Grande do Norte': 0.722,
    'Rio Grande do Sul': 0.701,
    'Rondônia': 0.727,
    'Roraima': 0.661,
    'Santa Catarina': 0.618,
    'São Paulo': 0.671,
    'Sergipe': 0.666,
    'Tocantins': 0.823
}

BANDEIRAS = {
    'verde': 0.00,       # R$ 0,00 por kWh
    'amarela': 0.01885,  # R$ 0,01885 por kWh
    'vermelha1': 0.04463, # R$ 0,04463 por kWh
    'vermelha2': 0.07877  # R$ 0,07877 por kWh
}

FAIXAS_TARIFA_SOCIAL = [
    {'limite': 30, 'desconto': 0.65},   # Até 30 kWh - 65% de desconto
    {'limite': 100, 'desconto': 0.40},  # 31 a 100 kWh - 40% de desconto
    {'limite': 220, 'desconto': 0.10},  # 101 a 220 kWh - 10% de desconto
    {'limite': float('inf'), 'desconto': 0.00}  # Acima de 220 kWh - sem desconto
]

def calcular_desconto_tarifa_social(consumo_kwh):
    """Calcula o desconto da tarifa social com base no consumo"""
    for faixa in FAIXAS_TARIFA_SOCIAL:
        if consumo_kwh <= faixa['limite']:
            return faixa['desconto']
    return 0.00

def calcular_consumo(dados, estado, aplicar_tarifa_social=False, bandeira='verde'):
    """
    Calcula o consumo energético e custos com base nos dados fornecidos
    
    Args:
        dados (dict): Dados processados do documento (aparelhos ou contador)
        estado (str): Estado para obter a tarifa
        aplicar_tarifa_social (bool): Se aplica desconto da tarifa social
        bandeira (str): Bandeira tarifária vigente
    
    Returns:
        dict: Resultados do cálculo formatados
    """
    # Validação inicial
    if not dados or 'tipo' not in dados:
        raise ValueError("Dados inválidos ou tipo de documento não especificado")

    # 1. Cálculo do consumo baseado no tipo de documento
    try:
        if dados['tipo'] == 'aparelhos':
            consumo_kwh = sum(
                (item['potencia'] * item['horas']) / 1000  # kWh por dia
                for item in dados['aparelhos']
            ) * 30  # Projeção mensal
            
        elif dados['tipo'] == 'contador':
            leituras = sorted(dados['leituras'], key=lambda x: x['data'])
            consumo_kwh = leituras[-1]['final'] - leituras[0]['inicial']
            
        else:
            raise ValueError(f"Tipo de documento não suportado: {dados['tipo']}")

        if consumo_kwh <= 0:
            raise ValueError("Consumo calculado deve ser maior que zero")

    except KeyError as e:
        raise ValueError(f"Campo obrigatório faltando: {str(e)}")
    except Exception as e:
        raise ValueError(f"Erro no cálculo do consumo: {str(e)}")

    # 2. Obter tarifa do estado
    tarifa = TARIFAS_ESTADOS.get(estado)
    if tarifa is None:
        raise ValueError(f"Tarifa não encontrada para o estado: {estado}")

    # 3. Aplicar tarifa social se necessário
    desconto = calcular_desconto_tarifa_social(consumo_kwh) if aplicar_tarifa_social else 0.00

    # 4. Calcular custos
    try:
        # Valor base da energia
        custo_energia = consumo_kwh * tarifa
        
        # Aplicar desconto da tarifa social
        custo_energia_com_desconto = custo_energia * (1 - desconto)
        
        # Custo da bandeira tarifária
        taxa_bandeira = BANDEIRAS.get(bandeira, 0)
        custo_bandeira = consumo_kwh * taxa_bandeira
        
        # Valor total
        total = custo_energia_com_desconto + custo_bandeira

    except Exception as e:
        raise ValueError(f"Erro no cálculo dos custos: {str(e)}")

    # 5. Formatando resultados
    return {
        'tipo_documento': dados['tipo'],
        'consumo_kwh': round(consumo_kwh, 2),
        'tarifa_estado': tarifa,
        'desconto_tarifa_social': f"{desconto * 100:.0f}%" if desconto > 0 else "0%",
        'custo_energia_sem_desconto': round(custo_energia, 2),
        'custo_energia_com_desconto': round(custo_energia_com_desconto, 2),
        'bandeira': bandeira.upper(),
        'taxa_bandeira': taxa_bandeira,
        'custo_bandeira': round(custo_bandeira, 2),
        'valor_total': round(total, 2),
        'estado': estado
    }

# Função auxiliar para processamento de documentos
def processar_dados_aparelhos(dados_aparelhos):
    """Valida e estrutura dados de aparelhos elétricos"""
    campos_obrigatorios = ['nome', 'potencia', 'horas']
    resultados = []
    
    for item in dados_aparelhos:
        if not all(campo in item for campo in campos_obrigatorios):
            raise ValueError("Dados de aparelho incompletos")
        
        try:
            resultados.append({
                'nome': str(item['nome']),
                'potencia': float(item['potencia']),
                'horas': float(item['horas'])
            })
        except (ValueError, TypeError) as e:
            raise ValueError(f"Erro ao converter dados do aparelho: {str(e)}")
    
    return {'tipo': 'aparelhos', 'aparelhos': resultados}

def processar_dados_contador(dados_contador):
    """Valida e estrutura dados do contador de energia"""
    campos_obrigatorios = ['data', 'inicial', 'final']
    resultados = []
    
    for item in dados_contador:
        if not all(campo in item for campo in campos_obrigatorios):
            raise ValueError("Dados do contador incompletos")
        
        try:
            resultados.append({
                'data': str(item['data']),
                'inicial': float(item['inicial']),
                'final': float(item['final'])
            })
        except (ValueError, TypeError) as e:
            raise ValueError(f"Erro ao converter dados do contador: {str(e)}")
    
    return {'tipo': 'contador', 'leituras': resultados}

def processar_excel(uploaded_file):
    """Processa arquivos Excel baseado nos templates fornecidos"""
    df = pd.read_excel(uploaded_file)
    
    if 'Aparelho' in df.columns:  # Template de aparelhos
        return {
            'tipo': 'aparelhos',
            'aparelhos': [
                {
                    'nome': row['Aparelho'],
                    'potencia': float(row['Potência (W)']),
                    'horas': float(row['Horas por dia'])
                }
                for _, row in df.iterrows()
            ]
        }
    elif 'Data' in df.columns:  # Template de contador
        return {
            'tipo': 'contador',
            'leituras': [
                {
                    'data': str(row['Data']),
                    'inicial': float(row['Leitura Inicial (kWh)']),
                    'final': float(row['Leitura Final (kWh)'])
                }
                for _, row in df.iterrows()
            ]
        }
    else:
        raise ValueError("Formato de Excel não reconhecido")

def processar_word(uploaded_file):
    """Processa arquivos Word baseado nos templates fornecidos"""
    doc = Document(uploaded_file)
    tables = doc.tables
    
    if len(tables) == 0:
        raise ValueError("Nenhuma tabela encontrada no documento Word")
    
    # Verifica qual template é (aparelhos ou contador)
    first_row = tables[0].rows[0].cells
    first_row_text = [cell.text.strip() for cell in first_row]
    
    if 'Aparelho' in first_row_text:
        # Template de aparelhos
        aparelhos = []
        for row in tables[0].rows[1:]:
            cells = row.cells
            if len(cells) >= 3:
                aparelhos.append({
                    'nome': cells[0].text.strip(),
                    'potencia': float(cells[1].text.strip()),
                    'horas': float(cells[2].text.strip())
                })
        return {'tipo': 'aparelhos', 'aparelhos': aparelhos}
    
    elif 'Data' in first_row_text:
        # Template de contador
        leituras = []
        for row in tables[0].rows[1:]:
            cells = row.cells
            if len(cells) >= 3:
                leituras.append({
                    'data': cells[0].text.strip(),
                    'inicial': float(cells[1].text.strip()),
                    'final': float(cells[2].text.strip())
                })
        return {'tipo': 'contador', 'leituras': leituras}
    
    else:
        raise ValueError("Formato de Word não reconhecido")