from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from datetime import datetime, timedelta
import json
from django.http import JsonResponse
from .models import Ambiente, Aparelho, HistoricoConsumo, Estado, Bandeira, TarifaSocial
from django.db.models import Sum

import pytesseract  
from PIL import Image  
import re  

import base64
import io
import pdf2image
from django.core.files.base import ContentFile
from django.contrib import messages

from django.core.files.storage import FileSystemStorage
from django.conf import settings
from .utils.image_processing import extract_text_from_image
from .utils.image_processing import adaptative_preprocessing
from .utils.text_parser import parse_amazonas_energia_text
import os
import time

from pdf2image import convert_from_path
import tempfile

import pandas as pd
from docx import Document

from django.core.serializers.json import DjangoJSONEncoder
from .utils_doc import TARIFAS_ESTADOS, BANDEIRAS, calcular_consumo
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from django.contrib.auth.decorators import login_required
from .models import DadosContador, DadosAparelho, ConjuntoDados
import logging
from .models import RegistroContador
from decimal import Decimal
from django.urls import reverse

def home(request):
    return render(request, 'home.html')


def calcular_consumo(request):
    if request.method == 'POST':
        data_cadastro = request.POST.get('data_cadastro', timezone.now().date())
        bandeira_value = request.POST.get('bandeira')
        
        try:
            # Primeiro tenta buscar pelo ID (se o valor for numérico)
            if bandeira_value.isdigit():
                bandeira = Bandeira.objects.get(id=int(bandeira_value))
            else:
                # Se não for numérico, busca pela cor
                bandeira = Bandeira.objects.get(cor=bandeira_value)
                
            estado = Estado.objects.get(id=int(request.POST.get('estado')))
            
            aparelho = Aparelho.objects.create(
                nome=request.POST.get('nome'),
                potencia_watts=float(request.POST.get('potencia')),
                tempo_uso_diario_horas=float(request.POST.get('horas')),
                quantidade=int(request.POST.get('quantidade')),
                ambiente_id=int(request.POST.get('ambiente')),
                estado=estado,
                bandeira=bandeira,
                data_cadastro=data_cadastro
            )
            
            return redirect('core:resultados')
            
        except Bandeira.DoesNotExist:
            messages.error(request, "Bandeira selecionada não encontrada.")
            return redirect('core:calcular')
        except Estado.DoesNotExist:
            messages.error(request, "Estado selecionado não encontrado.")
            return redirect('core:calcular')
        except Exception as e:
            messages.error(request, f"Erro ao salvar: {str(e)}")
            return redirect('core:calcular')
    
    return render(request, 'calcular.html', {
        'ambientes': Ambiente.objects.all(),
        'estados': Estado.objects.filter(tarifa__isnull=False).select_related('tarifa'),
        'bandeiras': Bandeira.objects.all(),
        'aparelhos': Aparelho.objects.all().order_by('-data_cadastro'),
        'data_atual': timezone.now().date()
    })
def atualizar_historico_consumo(ambiente, data):
    """Atualiza o histórico de consumo para um ambiente e data específicos"""
    from decimal import Decimal
    
    aparelhos = Aparelho.objects.filter(ambiente=ambiente, data_cadastro=data)
    consumo_total = float(sum(a.consumo_diario_kwh() for a in aparelhos))  # Convertendo para float
    
    # Obter tarifa como float
    estado_padrao = Estado.objects.first()
    tarifa_normal = float(estado_padrao.tarifa.valor_kwh) if estado_padrao and estado_padrao.tarifa else 0.70
    
    # Calcular tarifa social como float
    tarifa_social = float(calcular_tarifa_social(consumo_total * 30))
    
    HistoricoConsumo.objects.update_or_create(
        data=data,
        ambiente=ambiente,
        defaults={
            'consumo_kwh': Decimal(str(consumo_total)),  # Armazena como Decimal
            'custo_normal': Decimal(str(consumo_total * tarifa_normal)),
            'custo_social': Decimal(str(consumo_total * tarifa_social))
        }
    )

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

def remover_aparelho(request, aparelho_id):
    aparelho = get_object_or_404(Aparelho, id=aparelho_id)
    data_cadastro = aparelho.data_cadastro
    ambiente = aparelho.ambiente
    aparelho.delete()
    
    atualizar_historico_consumo(ambiente, data_cadastro)
    return redirect('core:calcular')

def resultados(request):
    # Obter todas as datas distintas com aparelhos cadastrados
    datas_disponiveis = Aparelho.objects.dates('data_cadastro', 'day').order_by('-data_cadastro')
    
    # Data selecionada (padrão: mais recente)
    data_selecionada = request.GET.get('data')
    if not data_selecionada and datas_disponiveis:
        data_selecionada = datas_disponiveis[0].strftime('%Y-%m-%d')
    
    # Processar aparelhos da data selecionada
    if data_selecionada:
        try:
            # Converter a string da data para um objeto date
            from datetime import datetime
            data_obj = datetime.strptime(data_selecionada, '%Y-%m-%d').date()
            
            aparelhos_dia = Aparelho.objects.filter(
                data_cadastro=data_obj  # Filtro direto sem lookup 'date'
            ).select_related('ambiente', 'estado', 'bandeira')
            
            # Calcular totais
            consumo_total_dia = sum(a.consumo_diario_kwh() for a in aparelhos_dia)
            custo_total_normal = sum(a.custo_diario() for a in aparelhos_dia)
            custo_total_social = sum(a.custo_social_diario() for a in aparelhos_dia)
        except ValueError:
            # Se a data estiver em formato inválido
            aparelhos_dia = []
            consumo_total_dia = 0
            custo_total_normal = 0
            custo_total_social = 0
    else:
        aparelhos_dia = []
        consumo_total_dia = 0
        custo_total_normal = 0
        custo_total_social = 0
    
    return render(request, 'resultados.html', {
        'data_selecionada': data_selecionada,
        'aparelhos_dia': aparelhos_dia,
        'consumo_total_dia': consumo_total_dia,
        'custo_total_normal': custo_total_normal,
        'custo_total_social': custo_total_social,
        'datas_disponiveis': datas_disponiveis,
    })
def monitoramento(request):
    # Tratamento para requisições AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        periodo1 = request.GET.get('periodo1')
        periodo2 = request.GET.get('periodo2')
        
        if not periodo1 or not periodo2:
            return JsonResponse({'error': 'Selecione ambos os períodos'}, status=400)
        
        try:
            def get_periodo_data(data):
                registros = HistoricoConsumo.objects.filter(data=data).select_related('ambiente')
                return {
                    'ambientes': [r.ambiente.nome for r in registros],
                    'consumo': [float(r.consumo_kwh) for r in registros],
                    'custo_normal': [float(r.custo_normal) for r in registros],
                    'custo_social': [float(r.custo_social) for r in registros]
                }
            
            return JsonResponse({
                'periodo1': get_periodo_data(periodo1),
                'periodo2': get_periodo_data(periodo2)
            })
        
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    # Dados para renderização normal
    ambientes_atual = []
    consumos_atual = []
    custos_normal_atual = []
    custos_social_atual = []
    
    for ambiente in Ambiente.objects.all():
        consumo = sum(
            a.consumo_diario_kwh() 
            for a in Aparelho.objects.filter(ambiente=ambiente)
        )
        if consumo > 0:
            ambientes_atual.append(ambiente.nome)
            consumos_atual.append(float(consumo))
            custos_normal_atual.append(float(consumo * 0.70))  # Usando fallback
            custos_social_atual.append(float(consumo * 0.50))   # Usando fallback
    
    datas_disponiveis = HistoricoConsumo.objects.dates('data', 'day').order_by('-data')
    
    # Tenta pegar os dois períodos mais recentes como padrão
    periodo1_default = datas_disponiveis[0].strftime('%Y-%m-%d') if datas_disponiveis else None
    periodo2_default = datas_disponiveis[1].strftime('%Y-%m/%d') if len(datas_disponiveis) > 1 else None
    
    periodo1 = request.GET.get('periodo1', periodo1_default)
    periodo2 = request.GET.get('periodo2', periodo2_default)
    
    return render(request, 'monitoramento.html', {
        'ambientes_json': json.dumps(ambientes_atual),
        'consumos_json': json.dumps(consumos_atual),
        'custos_normal_json': json.dumps(custos_normal_atual),
        'custos_social_json': json.dumps(custos_social_atual),
        'datas_disponiveis': datas_disponiveis,
        'periodo1': periodo1,
        'periodo2': periodo2
    })

def coleta(request):
    if request.method == 'POST' and request.FILES.get('fatura'):
        try:
            start_time = time.time()
            uploaded_file = request.FILES['fatura']
            file_ext = os.path.splitext(uploaded_file.name)[1].lower()
            
            # Configure Poppler path for Windows
            POPPLER_PATH = r'C:\poppler\poppler-24.08.0\Library\bin'  # Update this if you installed elsewhere
            
            # Save uploaded file temporarily
            temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, uploaded_file.name)
            
            with open(temp_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            
            # Process PDF
            if file_ext == '.pdf':
                try:
                    images = convert_from_path(
                        temp_path,
                        dpi=300,
                        poppler_path=POPPLER_PATH
                    )
                    texto_extraido = ""
                    
                    for i, image in enumerate(images):
                        img_path = os.path.join(temp_dir, f'page_{i+1}.jpg')
                        image.save(img_path, 'JPEG')
                        
                        # Process each page with your existing OCR function
                        page_text = extract_text_from_image(img_path, '--psm 6 -l por')
                        texto_extraido += f"\n--- Página {i+1} ---\n{page_text}\n"
                        
                        # Clean up page image
                        os.remove(img_path)
                    
                    is_pdf = True
                    num_pages = len(images)
                    
                except Exception as e:
                    raise Exception(f"Erro ao processar PDF: {str(e)}. Verifique se o Poppler está instalado corretamente.")
            
            # Process images (existing code)
            elif file_ext in ('.jpg', '.jpeg', '.png'):
                texto_extraido = extract_text_from_image(temp_path)
                is_pdf = False
                num_pages = 1
            
            else:
                raise ValueError("Formato de arquivo não suportado")
            
            # Clean up
            os.remove(temp_path)
            
            return render(request, 'coleta.html', {
                'texto_extraido': texto_extraido,
                'process_time': time.time() - start_time,
                'is_pdf': is_pdf,
                'num_pages': num_pages,
                'success': True
            })
            
        except Exception as e:
            return render(request, 'coleta.html', {
                'erro': str(e),
                'debug_info': f"Tipo de arquivo: {file_ext}" if 'file_ext' in locals() else ""
            })
    
    return render(request, 'coleta.html')

def post_process_data(data):
    """Padroniza os dados extraídos"""
    # Formata valores monetários
    for field in data['tarifas']:
        if isinstance(data['tarifas'][field], (int, float)):
            data['tarifas'][field] = f"R$ {data['tarifas'][field]:.2f}".replace('.', ',')
    
    # Ordena detalhes de tarifas
    if data['tarifas']['detalhes']:
        data['tarifas']['detalhes'].sort(
            key=lambda x: float(x['valor']) if 'valor' in x and isinstance(x['valor'], (int, float)) else 0,
            reverse=True
        )
    
    return data


def coleta_documentacao(request):
    context = {
        'tarifas_estados': TARIFAS_ESTADOS,
        'BANDEIRAS': BANDEIRAS,
        'erro': None,
        'success': False
    }

    if request.method == 'POST' and request.FILES.get('documento'):
        try:
            uploaded_file = request.FILES['documento']
            file_name = uploaded_file.name.lower()
            
            # Save temporary file
            fs = FileSystemStorage()
            filename = fs.save(uploaded_file.name, uploaded_file)
            file_path = fs.path(filename)
            
            try:
                if file_name.endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(file_path, engine='openpyxl')
                    
                    # Appliance template (original unchanged)
                    if 'Aparelho' in df.columns or 'Potência (W)' in df.columns:
                        dados_processados = {
                            'tipo': 'aparelhos',
                            'aparelhos': [
                                {
                                    'nome': str(row['Aparelho']),
                                    'potencia': float(row['Potência (W)']),
                                    'horas': float(row['Horas por dia'])
                                }
                                for _, row in df.iterrows()
                            ]
                        }
                        context['file_type'] = 'excel_appliances'
                    
                    # Meter reading template (original unchanged)
                    elif 'Data' in df.columns:
                        errors = []
                        validated_rows = []
                        
                        for idx, row in df.iterrows():
                            try:
                                date_str = str(row['Data'])
                                
                                try:
                                    if '-' in date_str:
                                        date_part = date_str.split()[0] if ' ' in date_str else date_str
                                        date_obj = datetime.strptime(date_part, '%Y-%m-%d')
                                        date_str = date_obj.strftime('%d/%m/%Y')
                                    else:
                                        try:
                                            day, month, year = map(int, date_str.split('/'))
                                            date_obj = datetime(year, month, day)
                                            date_str = f"{day:02d}/{month:02d}/{year}"
                                        except ValueError:
                                            month, day, year = map(int, date_str.split('/'))
                                            date_obj = datetime(year, month, day)
                                            date_str = f"{day:02d}/{month:02d}/{year}"
                                        
                                        if not (1 <= day <= 31 and 1 <= month <= 12):
                                            raise ValueError("Data inválida")
                                        
                                except ValueError as e:
                                    raise ValueError(f"Formato de data inválido: {date_str}") from e
                                
                                if 'Leitura do mês(kWh)' in df.columns:
                                    try:
                                        leitura = float(row['Leitura do mês(kWh)'])
                                        validated_rows.append({
                                            'date_obj': date_obj,
                                            'date_str': date_str,
                                            'leitura': leitura,
                                            'type': 'monthly'
                                        })
                                    except (ValueError, TypeError):
                                        raise ValueError(f"Leitura inválida na linha {idx+2}")
                                
                                elif 'Leitura Inicial (kWh)' in df.columns and 'Leitura Final (kWh)' in df.columns:
                                    try:
                                        inicial = float(row['Leitura Inicial (kWh)'])
                                        final = float(row['Leitura Final (kWh)'])
                                        validated_rows.append({
                                            'date_obj': date_obj,
                                            'date_str': date_str,
                                            'inicial': inicial,
                                            'final': final,
                                            'type': 'daily'
                                        })
                                    except (ValueError, TypeError):
                                        raise ValueError(f"Leitura inválida na linha {idx+2}")
                                
                                else:
                                    raise ValueError("Formato de leitura não reconhecido")
                            
                            except ValueError as e:
                                errors.append(f"Linha {idx+2}: {str(e)}")
                        
                        if errors:
                            raise ValueError("\n".join(errors))
                        
                        if not validated_rows:
                            raise ValueError("Nenhum dado válido encontrado")
                        
                        validated_rows.sort(key=lambda x: x['date_obj'])
                        
                        leituras = []
                        acumulado = 0
                        
                        for i, row in enumerate(validated_rows):
                            if row['type'] == 'monthly':
                                if i == 0:
                                    consumo = 0
                                else:
                                    consumo = row['leitura'] - validated_rows[i-1]['leitura']
                                
                                leituras.append({
                                    'data': row['date_str'],
                                    'inicial': validated_rows[i-1]['leitura'] if i > 0 else row['leitura'],
                                    'final': row['leitura'],
                                    'consumo': consumo,
                                    'acumulado': (acumulado := acumulado + consumo)
                                })
                            
                            elif row['type'] == 'daily':
                                consumo = row['final'] - row['inicial']
                                leituras.append({
                                    'data': row['date_str'],
                                    'inicial': row['inicial'],
                                    'final': row['final'],
                                    'consumo': consumo,
                                    'acumulado': (acumulado := acumulado + consumo)
                                })
                        
                        dados_processados = {
                            'tipo': 'contador',
                            'leituras': leituras,
                            'periodo': f"{leituras[0]['data']} a {leituras[-1]['data']}",
                            'total': acumulado
                        }
                        context['file_type'] = 'excel_meter'
                    
                    else:
                        raise ValueError("Formato de planilha não reconhecido")
                
                elif file_name.endswith(('.docx', '.doc')):
                    doc = Document(file_path)
                    tables_data = []
                    
                    for table in doc.tables:
                        headers = [cell.text.strip() for cell in table.rows[0].cells]
                        rows = []
                        for row in table.rows[1:]:
                            row_data = [cell.text.strip() for cell in row.cells]
                            if len(row_data) == len(headers):
                                rows.append(row_data)
                        
                        if headers and rows:
                            tables_data.append({
                                'headers': headers,
                                'rows': rows
                            })
                    
                    # NEW FORMAT ADDITION (con 2x mensal.docx)
                    if (tables_data and len(tables_data[0]['headers']) == 2 and
                        'Data' in tables_data[0]['headers'][0] and 
                        'Leitura Final (kWh)' in tables_data[0]['headers'][1]):
                        
                        errors = []
                        validated_rows = []
                        
                        for i, row in enumerate(tables_data[0]['rows'], start=1):
                            try:
                                date_str = row[0]
                                day, month, year = map(int, date_str.split('/'))
                                date_obj = datetime(year, month, day)
                                date_str = f"{day:02d}/{month:02d}/{year}"
                                
                                leitura = float(row[1])
                                
                                validated_rows.append({
                                    'date_obj': date_obj,
                                    'date_str': date_str,
                                    'leitura': leitura,
                                    'type': 'monthly_final'
                                })
                                
                            except (ValueError, IndexError) as e:
                                errors.append(f"Linha {i+1}: {str(e)}")
                        
                        if not errors:
                            validated_rows.sort(key=lambda x: x['date_obj'])
                            
                            leituras = []
                            acumulado = 0
                            
                            for i, row in enumerate(validated_rows):
                                if i == 0:
                                    consumo = 0
                                else:
                                    consumo = row['leitura'] - validated_rows[i-1]['leitura']
                                
                                acumulado += consumo
                                
                                leituras.append({
                                    'data': row['date_str'],
                                    'inicial': validated_rows[i-1]['leitura'] if i > 0 else row['leitura'],
                                    'final': row['leitura'],
                                    'consumo': consumo,
                                    'acumulado': acumulado
                                })
                            
                            dados_processados = {
                                'tipo': 'contador',
                                'leituras': leituras,
                                'periodo': f"{leituras[0]['data']} a {leituras[-1]['data']}",
                                'total': acumulado,
                                'dias_medicao': len(leituras)
                            }
                            context['file_type'] = 'word_meter_final'
                            context['success'] = True
                            request.session['dados_processados'] = dados_processados
                            return redirect('core:resultado_documentacao')
                    
                    # ORIGINAL WORD PROCESSING (unchanged)
                    if tables_data and ('Aparelho' in tables_data[0]['headers'] or 'Potência (W)' in tables_data[0]['headers']):
                        dados_processados = {
                            'tipo': 'aparelhos',
                            'aparelhos': [
                                {
                                    'nome': str(row[0]),
                                    'potencia': float(row[1]),
                                    'horas': float(row[2])
                                }
                                for row in tables_data[0]['rows']
                            ]
                        }
                        context['file_type'] = 'word_appliances'
                    
                    elif tables_data and 'Data' in tables_data[0]['headers']:
                        errors = []
                        validated_rows = []
                        
                        for i, row in enumerate(tables_data[0]['rows'], start=2):
                            try:
                                date_str = row[0]
                                try:
                                    day, month, year = map(int, date_str.split('/'))
                                    date_obj = datetime(year, month, day)
                                    date_str = f"{day:02d}/{month:02d}/{year}"
                                    
                                    if not (1 <= day <= 31 and 1 <= month <= 12):
                                        raise ValueError("Data inválida")
                                    
                                except ValueError:
                                    month, day, year = map(int, date_str.split('/'))
                                    date_obj = datetime(year, month, day)
                                    date_str = f"{day:02d}/{month:02d}/{year}"
                                
                                if 'Leitura Final (kWh)' in tables_data[0]['headers']:
                                    inicial = float(row[1])
                                    final = float(row[2])
                                    validated_rows.append({
                                        'date_obj': date_obj,
                                        'date_str': date_str,
                                        'inicial': inicial,
                                        'final': final,
                                        'type': 'daily'
                                    })
                                else:
                                    leitura = float(row[1])
                                    validated_rows.append({
                                        'date_obj': date_obj,
                                        'date_str': date_str,
                                        'leitura': leitura,
                                        'type': 'monthly'
                                    })
                            
                            except (ValueError, IndexError) as e:
                                errors.append(f"Linha {i}: {str(e)}")
                        
                        if errors:
                            raise ValueError("\n".join(errors))
                        
                        if not validated_rows:
                            raise ValueError("Nenhum dado válido encontrado")
                        
                        validated_rows.sort(key=lambda x: x['date_obj'])
                        
                        leituras = []
                        acumulado = 0
                        
                        for i, row in enumerate(validated_rows):
                            if row['type'] == 'monthly':
                                if i == 0:
                                    consumo = 0
                                else:
                                    consumo = row['leitura'] - validated_rows[i-1]['leitura']
                                
                                leituras.append({
                                    'data': row['date_str'],
                                    'inicial': validated_rows[i-1]['leitura'] if i > 0 else row['leitura'],
                                    'final': row['leitura'],
                                    'consumo': consumo,
                                    'acumulado': (acumulado := acumulado + consumo)
                                })
                            
                            elif row['type'] == 'daily':
                                consumo = row['final'] - row['inicial']
                                leituras.append({
                                    'data': row['date_str'],
                                    'inicial': row['inicial'],
                                    'final': row['final'],
                                    'consumo': consumo,
                                    'acumulado': (acumulado := acumulado + consumo)
                                })
                        
                        dados_processados = {
                            'tipo': 'contador',
                            'leituras': leituras,
                            'periodo': f"{leituras[0]['data']} a {leituras[-1]['data']}",
                            'total': acumulado
                        }
                        context['file_type'] = 'word_meter'
                    
                    else:
                        raise ValueError("Formato de documento não reconhecido")
                
                else:
                    raise ValueError("Formato de arquivo não suportado. Use Excel (.xlsx, .xls) ou Word (.docx)")
                
                context['success'] = True
                request.session['dados_processados'] = dados_processados
            
            except Exception as e:
                raise ValueError(f"Erro ao processar arquivo: {str(e)}")
            
            finally:
                if os.path.exists(file_path):
                    os.remove(file_path)
            
            if context['success']:
                return redirect('core:resultado_documentacao')
        
        except Exception as e:
            context['erro'] = str(e)
            context['debug_info'] = {
                'file_name': uploaded_file.name,
                'file_type': uploaded_file.content_type,
                'upload_time': timezone.now().strftime('%d/%m/%Y %H:%M:%S')
            }
    
    return render(request, 'coleta_documentacao.html', context)

def resultado_documentacao(request):
    context = {
        'tarifas_estados': TARIFAS_ESTADOS,
        'BANDEIRAS': BANDEIRAS,
        'resultados': None,
        'erro': None,
        'dados_origem': None,
        'documento_processado': False,
    }

    dados_processados = request.session.get('dados_processados')
    if not dados_processados:
        return render(request, 'resultado_documentacao.html', context)

    context['documento_processado'] = True

    try:
        # Process energy meter data
        if dados_processados.get('tipo') == 'contador':
            leituras = sorted(dados_processados['leituras'], key=lambda x: x['data'])
            
            for i, leitura in enumerate(leituras):
                leitura['consumo_diario'] = float(leitura['final']) - float(leitura['inicial'])
                leitura['consumo_acumulado'] = leitura['consumo_diario'] + (
                    leituras[i-1]['consumo_acumulado'] if i > 0 else 0
                )

            context['dados_origem'] = {
                'tipo': 'Medidor de Energia',
                'periodo': f"{leituras[0]['data']} a {leituras[-1]['data']}",
                'leituras': leituras,
                'consumo_total': leituras[-1]['consumo_acumulado'] if leituras else 0,
                'dias_medicao': len(leituras),
            }

        # Process appliance data
        elif dados_processados.get('tipo') == 'aparelhos':
            for aparelho in dados_processados['aparelhos']:
                aparelho['consumo_diario'] = (float(aparelho['potencia']) * float(aparelho['horas'])) / 1000

            consumo_diario = sum(a['consumo_diario'] for a in dados_processados['aparelhos'])
            consumo_mensal = consumo_diario * 30  # Monthly estimate for social tariff

            context['dados_origem'] = {
                'tipo': 'Lista de Aparelhos',
                'itens': dados_processados['aparelhos'],
                'consumo_total_diario': consumo_diario,
                'consumo_mensal_estimado': consumo_mensal,
                'quantidade_aparelhos': len(dados_processados['aparelhos']),
            }

        # Tariff calculation
        if request.method == 'POST':
            estado = request.POST.get('estado')
            bandeira = request.POST.get('bandeira', 'verde')
            tarifa_social = request.POST.get('tarifa_social') == 'on'

            if not estado:
                raise ValueError("Selecione um estado")

            tarifa = TARIFAS_ESTADOS.get(estado)
            if tarifa is None:
                raise ValueError("Tarifa não encontrada para o estado selecionado")

            # Get correct consumption based on type and tariff selection
            if dados_processados['tipo'] == 'aparelhos':
                consumo = context['dados_origem']['consumo_mensal_estimado'] if tarifa_social else context['dados_origem']['consumo_total_diario']
                periodo = 'mensal' if tarifa_social else 'diário'
            else:
                consumo = context['dados_origem']['consumo_total']
                periodo = 'período medido'

            custo_energia = consumo * tarifa
            custo_bandeira = consumo * BANDEIRAS.get(bandeira, 0)

            # Social tariff calculation
            if tarifa_social:
                if consumo <= 30:
                    desconto = 0.65
                elif consumo <= 100:
                    desconto = 0.40
                elif consumo <= 220:
                    desconto = 0.10
                else:
                    desconto = 0
                
                custo_com_desconto = custo_energia * (1 - desconto)
                total = custo_com_desconto + custo_bandeira

                context['resultados'] = {
                    'consumo_kwh': round(consumo, 2),
                    'periodo': periodo,
                    'estado': estado,
                    'tarifa': round(tarifa, 5),
                    'custo_energia': round(custo_energia, 2),
                    'desconto': f"{desconto * 100:.0f}%",
                    'custo_energia_com_desconto': round(custo_com_desconto, 2),
                    'bandeira': bandeira.upper(),
                    'custo_bandeira': round(custo_bandeira, 2),
                    'total': round(total, 2),
                    'tarifa_social_aplicada': True
                }
            else:
                context['resultados'] = {
                    'consumo_kwh': round(consumo, 2),
                    'periodo': periodo,
                    'estado': estado,
                    'tarifa': round(tarifa, 5),
                    'custo_energia': round(custo_energia, 2),
                    'desconto': "0%",
                    'bandeira': bandeira.upper(),
                    'custo_bandeira': round(custo_bandeira, 2),
                    'total': round(custo_energia + custo_bandeira, 2),
                    'tarifa_social_aplicada': False
                }

    except Exception as e:
        context['erro'] = str(e)

    return render(request, 'resultado_documentacao.html', context)

def salvar_dados(request):
    if request.method == 'POST':
        dados = request.session.get('dados_processados')
        
        try:
            conjunto = ConjuntoDados.objects.create(
                nome=f"Conjunto {timezone.now().strftime('%d/%m/%Y %H:%M')}",
                tipo='CONTADOR' if dados['tipo'] == 'contador' else 'APARELHO'
            )
            
            if dados['tipo'] == 'contador':
                for leitura in dados['leituras']:
                    # Calcular consumo_diario se não existir
                    consumo_d = leitura.get('consumo_diario', 
                                         float(leitura['final']) - float(leitura['inicial']))
                    
                    DadosContador.objects.create(
                        conjunto=conjunto,
                        periodo=leitura['data'],
                        data_medicao=datetime.strptime(leitura['data'], '%d/%m/%Y').date(),
                        leitura_inicial=float(leitura['inicial']),
                        leitura_final=float(leitura['final']),
                        consumo_diario=consumo_d,
                        consumo_acumulado=float(leitura.get('consumo_acumulado', consumo_d))
                    )
            elif dados['tipo'] == 'aparelhos':
                for aparelho in dados['aparelhos']:
                    DadosAparelho.objects.create(
                        conjunto=conjunto,
                        nome=aparelho['nome'],
                        potencia=float(aparelho['potencia']),
                        horas_uso=float(aparelho['horas']),
                        consumo_diario=float(aparelho.get('consumo_diario', 
                                                        (float(aparelho['potencia']) * float(aparelho['horas']) / 1000))
                    )
                )
            messages.success(request, "Dados salvos com sucesso!")
            return redirect('core:monitoramento_documentacao')
        
        except Exception as e:
            messages.error(request, f"Erro ao salvar: {str(e)}")
            return redirect('core:resultado_documentacao')

def remover_dado(request, tipo, id):
    try:
        if tipo == 'contador':
            dado = DadosContador.objects.get(id=id)
            dado.delete()
            messages.success(request, "Dados do medidor removidos!")
        elif tipo == 'aparelho':
            dado = DadosAparelho.objects.get(id=id)
            dado.delete()
            messages.success(request, "Aparelho removido!")
    except Exception as e:
        messages.error(request, f"Erro ao remover: {str(e)}")
    
    return redirect('core:monitoramento_documentacao')

logger = logging.getLogger(__name__)


def monitoramento_documentacao(request):
    if request.GET.get('ajax') == '1':
        try:
            conjunto_id = request.GET.get('conjunto_id')
            if not conjunto_id:
                return JsonResponse({'error': 'ID do conjunto não fornecido'}, status=400)
                
            conjunto = ConjuntoDados.objects.get(id=conjunto_id)
            
            if conjunto.tipo == 'CONTADOR':
                dados = conjunto.contadores.all().order_by('data_medicao')
                if not dados.exists():
                    return JsonResponse({'error': 'Nenhum dado de contador encontrado'}, status=404)
                    
                data = {
                    'tipo': 'contador',
                    'labels': [d.data_medicao.strftime('%d/%m/%Y') for d in dados],
                    'datasets': [{
                        'label': 'Consumo Acumulado (kWh)',
                        'data': [float(d.consumo_acumulado) for d in dados]
                    }]
                }
            else:
                dados = conjunto.aparelhos.all()
                if not dados.exists():
                    return JsonResponse({'error': 'Nenhum dado de aparelho encontrado'}, status=404)
                    
                data = {
                    'tipo': 'aparelho',
                    'labels': [d.nome for d in dados],
                    'datasets': [{
                        'label': 'Consumo Diário (kWh)',
                        'data': [float(d.consumo_diario) for d in dados]
                    }]
                }
            
            return JsonResponse(data, encoder=DjangoJSONEncoder)
            
        except ConjuntoDados.DoesNotExist:
            return JsonResponse({'error': 'Conjunto não encontrado'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    conjuntos = ConjuntoDados.objects.all()
    return render(request, 'monitoramento_documentacao.html', {'conjuntos': conjuntos})

def contador_energia(request):
    # Tarifas por estado 
    tarifas_estados = {
        "Pará": 0.938,
        "Mato Grosso do Sul": 0.870,
        "Rio de Janeiro": 0.870,
        "Alagoas": 0.863,
        "Amazonas": 0.857,
        "Mato Grosso": 0.847,
        "Piauí": 0.829,
        "Tocantins": 0.823,
        "Bahia": 0.821,
        "Amapá": 0.808,
        "Minas Gerais": 0.796,
        "Acre": 0.791,
        "Goiás": 0.745,
        "Pernambuco": 0.744,
        "Distrito Federal": 0.743,
        "Rondônia": 0.727,
        "Ceará": 0.722,
        "Rio Grande do Norte": 0.722,
        "Maranhão": 0.711,
        "Rio Grande do Sul": 0.701,
        "Espírito Santo": 0.682,
        "São Paulo": 0.671,
        "Sergipe": 0.666,
        "Roraima": 0.661,
        "Paraná": 0.629,
        "Santa Catarina": 0.618,
        "Paraíba": 0.588,
    }

    # Bandeiras tarifárias (fonte: bandeiras.txt)
    bandeiras = {
        "verde": 0.0,
        "amarela": 0.01885,
        "vermelha1": 0.04463,
        "vermelha2": 0.07877,
    }

    # Descontos da Tarifa Social (fonte: tarifa_social_energia_tsee.docx)
    tarifa_social = {
        "30": 0.65,  # 65% de desconto para até 30 kWh
        "100": 0.40, # 40% para 31-100 kWh
        "220": 0.10, # 10% para 101-220 kWh
        "0": 0.0,    # Sem desconto
    }

    resultado = None

    if request.method == 'POST':
        if 'calcular' in request.POST:
            estado = request.POST.get('estado')
            bandeira = request.POST.get('bandeira')
            tarifa_social_key = request.POST.get('tarifa_social')
            consumo = float(request.POST.get('consumo', 0))

            # Cálculos
            tarifa_base = tarifas_estados.get(estado, 0)
            acrescimo = bandeiras.get(bandeira, 0)
            desconto = tarifa_social.get(tarifa_social_key, 0)
            
            total = consumo * (tarifa_base + acrescimo) * (1 - desconto)

            resultado = {
                'consumo': consumo,
                'total': total,
                'estado': estado,
                'bandeira': bandeira,
                'tarifa_base': tarifa_base,
                'acrescimo_bandeira': acrescimo,
                'desconto_tarifa_social': f"{desconto * 100:.0f}%"
            }

        elif 'salvar' in request.POST:
            # Recebe os dados do formulário oculto
            consumo = request.POST.get('consumo')
            total = request.POST.get('total')
            estado = request.POST.get('estado')
            bandeira = request.POST.get('bandeira')
            
            if consumo and total:
                request.session['dados_calculo'] = {
                    'consumo': float(consumo),
                    'total': float(total),
                    'estado': estado,
                    'bandeira': bandeira,
                    'data': timezone.now().strftime("%d/%m/%Y %H:%M")
                }
                return redirect('core:resultados_contador')

    return render(request, 'contador_energia.html', {
        'tarifas_estados': tarifas_estados,
        'resultado': resultado
    })

def resultados_contador(request):
    dados_calculo = request.session.get('dados_calculo')
    registros = RegistroContador.objects.all().order_by('-data_registro')

    if request.method == 'POST' and 'confirmar' in request.POST:
        if dados_calculo:
            RegistroContador.objects.create(
                consumo_kwh=dados_calculo['consumo'],
                total_pagar=dados_calculo['total'],
                estado=dados_calculo['estado']
            )
            del request.session['dados_calculo']
            return redirect('core:resultados_contador')

    return render(request, 'resultados_contador.html', {
        'dados_calculo': dados_calculo,
        'registros': registros,
        'mostrar_aviso': not dados_calculo and not registros.exists()
    })

def deletar_registro_contador(request, id):
    if request.method == 'POST':
        try:
            registro = RegistroContador.objects.get(id=id)
            registro.delete()
            return JsonResponse({'status': 'success'})
        except RegistroContador.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Registro não encontrado'}, status=404)
    return JsonResponse({'status': 'error'}, status=400)

def monitoramento_contador(request):
    # Dados para o gráfico
    dados = RegistroContador.objects.values('estado').annotate(
        total_consumo=Sum('consumo_kwh'),
        total_pago=Sum('total_pagar')
    ).order_by('estado')
    
    # Se requisição AJAX para dados do gráfico
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        estados = [item['estado'] for item in dados]
        consumos = [float(item['total_consumo']) for item in dados]
        totais = [float(item['total_pago']) for item in dados]
        
        return JsonResponse({
            'estados': estados,
            'consumos': consumos,
            'totais': totais
        })
    
    return render(request, 'monitoramento_contador.html', {'dados': dados})