from django.contrib import admin
from .models import (
    Ambiente, 
    Tarifa, 
    Aparelho, 
    HistoricoConsumo,
    Estado,
    Bandeira,
    TarifaSocial
)

admin.site.register(Ambiente)
admin.site.register(Aparelho)
admin.site.register(HistoricoConsumo)

@admin.register(Estado)
class EstadoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'sigla')
    search_fields = ('nome', 'sigla')

@admin.register(Tarifa)
class TarifaAdmin(admin.ModelAdmin):
    list_display = ('estado', 'valor_kwh', 'atualizado_em')
    list_filter = ('atualizado_em',)
    search_fields = ('estado__nome',)
    ordering = ('estado__nome',)

@admin.register(Bandeira)
class BandeiraAdmin(admin.ModelAdmin):
    list_display = ('get_cor_display', 'valor_adicional', 'descricao_curta')
    ordering = ('valor_adicional',)
    
    def descricao_curta(self, obj):
        return obj.descricao[:50] + '...' if len(obj.descricao) > 50 else obj.descricao
    descricao_curta.short_description = 'Descrição'

@admin.register(TarifaSocial)
class TarifaSocialAdmin(admin.ModelAdmin):
    list_display = ('faixa_consumo', 'desconto_percentual', 'descricao_curta')
    ordering = ('desconto_percentual',)
    
    def descricao_curta(self, obj):
        return obj.descricao[:50] + '...' if len(obj.descricao) > 50 else obj.descricao
    descricao_curta.short_description = 'Descrição'

