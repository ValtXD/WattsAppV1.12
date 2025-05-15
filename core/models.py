from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from .utils_ap import calcular_tarifa_social

User = get_user_model()

class Ambiente(models.Model):
    nome = models.CharField(max_length=100)

    def __str__(self):
        return self.nome

class Estado(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    sigla = models.CharField(max_length=2, unique=True)
    
    def __str__(self):
        return f"{self.nome} ({self.sigla})"

class Tarifa(models.Model):
    estado = models.OneToOneField(Estado, on_delete=models.CASCADE)
    valor_kwh = models.DecimalField(max_digits=6, decimal_places=5)
    atualizado_em = models.DateField(auto_now=True)
    
    def __str__(self):
        return f"Tarifa {self.estado} - R$ {self.valor_kwh}/kWh"
    
class Bandeira(models.Model):
    CORES = (
        ('verde', 'Verde'),
        ('amarela', 'Amarela'),
        ('vermelha1', 'Vermelha - Patamar 1'),
        ('vermelha2', 'Vermelha - Patamar 2'),
    )
    
    cor = models.CharField(max_length=10, choices=CORES, unique=True)
    valor_adicional = models.DecimalField(max_digits=6, decimal_places=5)
    descricao = models.TextField()
    
    def __str__(self):
        return f"{self.get_cor_display()} (R$ {self.valor_adicional}/kWh)"

class TarifaSocial(models.Model):
    faixa_consumo = models.CharField(max_length=50)
    desconto_percentual = models.DecimalField(max_digits=4, decimal_places=2)
    descricao = models.TextField(blank=True)
    
    def __str__(self):
        return f"Tarifa Social - {self.faixa_consumo} ({self.desconto_percentual}% de desconto)"

class Aparelho(models.Model):
    nome = models.CharField(max_length=100)
    potencia_watts = models.FloatField()
    tempo_uso_diario_horas = models.FloatField()
    quantidade = models.IntegerField()
    ambiente = models.ForeignKey(Ambiente, on_delete=models.CASCADE)
    estado = models.ForeignKey(Estado, on_delete=models.CASCADE)
    bandeira = models.ForeignKey(Bandeira, on_delete=models.CASCADE)
    data_cadastro = models.DateField(default=timezone.now)

    def consumo_diario_kwh(self):
        return (self.potencia_watts * self.tempo_uso_diario_horas * self.quantidade) / 1000

    def custo_diario(self):
        tarifa_total = float(self.estado.tarifa.valor_kwh) + float(self.bandeira.valor_adicional)
        return self.consumo_diario_kwh() * tarifa_total

    def custo_social_diario(self):
        tarifa_social = calcular_tarifa_social(self.consumo_diario_kwh() * 30)
        return self.consumo_diario_kwh() * tarifa_social

    def __str__(self):
        return self.nome

class HistoricoConsumo(models.Model):
    data = models.DateField()
    ambiente = models.ForeignKey(Ambiente, on_delete=models.CASCADE)
    consumo_kwh = models.FloatField()
    custo_normal = models.FloatField()
    custo_social = models.FloatField()

    class Meta:
        ordering = ['-data']
        unique_together = ('data', 'ambiente')  # Garante um único registro por ambiente por dia

    def __str__(self):
        return f"{self.data} - {self.ambiente.nome}"

    @classmethod
    def registrar_consumo(cls, data, ambiente, consumo_kwh, custo_normal, custo_social):
        cls.objects.update_or_create(
            data=data,
            ambiente=ambiente,
            defaults={
                'consumo_kwh': consumo_kwh,
                'custo_normal': custo_normal,
                'custo_social': custo_social
            }
        )
"""////////////////////////////////////////////////////////////////////////////////////////////////////////////////////"""
class ConjuntoDados(models.Model):
    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=10, choices=[('CONTADOR', 'Contador'), ('APARELHO', 'Aparelho')])
    data_criacao = models.DateTimeField(auto_now_add=True, null=True, blank=True)     
    
    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()})"

class DadosContador(models.Model):
    conjunto = models.ForeignKey(ConjuntoDados, on_delete=models.CASCADE, related_name='contadores')
    periodo = models.CharField(max_length=100)
    data_medicao = models.DateField()
    leitura_inicial = models.FloatField()
    leitura_final = models.FloatField()
    consumo_diario = models.FloatField()
    consumo_acumulado = models.FloatField()
    data_registro = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.conjunto.nome} - {self.data_medicao}"

class DadosAparelho(models.Model):
    conjunto = models.ForeignKey(ConjuntoDados, on_delete=models.CASCADE, related_name='aparelhos')
    nome = models.CharField(max_length=100)
    potencia = models.FloatField()
    horas_uso = models.FloatField()
    consumo_diario = models.FloatField()
    data_registro = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.conjunto.nome} - {self.nome}" 
    

class RegistroContador(models.Model):
    data_registro = models.DateTimeField(default=timezone.now)
    consumo_kwh = models.FloatField()
    total_pagar = models.FloatField()
    estado = models.CharField(max_length=50, blank=True, null=True)  # Opcional

    def __str__(self):
        return f"Consumo: {self.consumo_kwh}kWh (R$ {self.total_pagar})"

    class Meta:
        verbose_name = "Registro do Contador"
        verbose_name_plural = "Registros do Contador"