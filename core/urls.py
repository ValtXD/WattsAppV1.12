from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),

    path('calcular/', views.calcular_consumo, name='calcular'),
    path('resultados/', views.resultados, name='resultados'),
    path('monitoramento/', views.monitoramento, name='monitoramento'),

    path('coleta/', views.coleta, name='coleta'),
    path('coleta-documentacao/', views.coleta_documentacao, name='coleta_documentacao'),
    path('resultado-documentacao/', views.resultado_documentacao, name='resultado_documentacao'),
    path('remover-aparelho/<int:aparelho_id>/', views.remover_aparelho, name='remover_aparelho'),

    path('salvar-dados/', views.salvar_dados, name='salvar_dados'),
    path('monitoramento-documentacao/', views.monitoramento_documentacao, name='monitoramento_documentacao'),
    path('remover-dado/<str:tipo>/<int:id>/', views.remover_dado, name='remover_dado'),

    path('contador-energia/', views.contador_energia, name='contador_energia'),
    path('resultados-contador/', views.resultados_contador, name='resultados_contador'),
    path('deletar-registro-contador/<int:id>/', views.deletar_registro_contador, name='deletar_registro_contador'),
    path('monitoramento-contador/', views.monitoramento_contador, name='monitoramento_contador'),
]