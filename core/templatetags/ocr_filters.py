from django import template

register = template.Library()

@register.filter(name='replace_underscores')
def replace_underscores(value):
    """Substitui underscores por espaços para exibição"""
    return value.replace('_', ' ') if value else value

@register.filter(name='format_currency')
def format_currency(value):
    """Formata valores monetários para exibição"""
    try:
        if value and isinstance(value, str):
            if '.' in value:
                return f"R$ {float(value):.2f}".replace('.', ',')
            return f"R$ {value},00"
        return value
    except:
        return value

@register.filter(name='format_date')
def format_date(value):
    """Formata datas para o padrão brasileiro"""
    if value and len(value) == 10 and value[2] == '/' and value[5] == '/':
        return value  # Já está formatado
    return value  # Mantém original se não for reconhecido

@register.filter
def split(value, arg):
    """Divide a string usando o argumento como separador"""
    return value.split(arg)