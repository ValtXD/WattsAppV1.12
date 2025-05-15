# core/utils.py
def calcular_tarifa_social(consumo_mensal):
    """Calcula a tarifa social baseada no consumo mensal"""
    try:
        if consumo_mensal <= 30:
            desconto = 0.65
        elif consumo_mensal <= 100:
            desconto = 0.40
        elif consumo_mensal <= 220:
            desconto = 0.10
        else:
            desconto = 0
        
        # Tarifa base do estado de São Paulo como referência
        tarifa_base = 0.67123
        return tarifa_base * (1 - desconto)
    except Exception:
        return 0.50  # Fallback