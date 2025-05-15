# energy_manager/core/templatetags/math_filters.py
from django import template

register = template.Library()

@register.filter(name='mul')
def mul(value, arg):
    """Multiplica o valor pelo argumento"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter(name='div')
def div(value, arg):
    """Divide o valor pelo argumento"""
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter(name='sub')
def sub(value, arg):
    """Subtrai o argumento do valor"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0
    
@register.filter(name='dict_key')
def dict_key(d, key):
    """Acessa um valor de dicionário pela chave"""
    return d.get(key, 0)

@register.filter
def upper(value):
    return value.upper()
