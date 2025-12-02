#!/usr/bin/env python
"""
Comando de gerenciamento Django para carregar dados do JSON.
Este arquivo deve ser colocado em: p_v_App/management/commands/load_json_data.py

Para usar:
    python manage.py load_json_data
    python manage.py load_json_data --file caminho/para/arquivo.json
    python manage.py load_json_data --clear  # Limpa dados antes de carregar
"""

import json
import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from p_v_App.models import Category, Products, Sales, salesItems, Pedido, PedidoItem, Estoque


class Command(BaseCommand):
    help = 'Carrega dados de um arquivo JSON no banco de dados'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='data.json',
            help='Caminho para o arquivo JSON (padrão: data.json)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Limpa todas as tabelas antes de carregar os dados'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Executa sem salvar no banco (apenas mostra o que seria feito)'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        clear_data = options['clear']
        dry_run = options['dry_run']

        if not os.path.exists(file_path):
            raise CommandError(f'Arquivo não encontrado: {file_path}')

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    'MODO DRY-RUN: Nenhum dado será salvo no banco')
            )

        if clear_data:
            self.clear_all_data(dry_run)

        self.load_json_data(file_path, dry_run)

    def clear_all_data(self, dry_run=False):
        """Limpa todos os dados das tabelas."""
        self.stdout.write('Limpando dados existentes...')

        if not dry_run:
            # Ordem importante devido às chaves estrangeiras
            salesItems.objects.all().delete()
            PedidoItem.objects.all().delete()
            Estoque.objects.all().delete()
            Sales.objects.all().delete()
            Pedido.objects.all().delete()
            Products.objects.all().delete()
            Category.objects.all().delete()
            # Não deletar usuários por segurança

        self.stdout.write(
            self.style.SUCCESS('Dados limpos com sucesso!')
        )

    def load_json_data(self, file_path, dry_run=False):
        """Carrega dados do arquivo JSON."""
        self.stdout.write(f'Carregando dados de {file_path}...')

        try:
            # Tentar ler com UTF-8 primeiro
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except UnicodeDecodeError:
            self.stdout.write(
                'Erro de codificação UTF-8. Tentando com latin-1...')
            with open(file_path, 'r', encoding='latin-1') as f:
                data = json.load(f)

        self.stdout.write(f'Total de objetos encontrados: {len(data)}')

        # Contadores
        stats = {
            'auth.user': 0,
            'p_v_App.category': 0,
            'p_v_App.products': 0,
            'p_v_App.sales': 0,
            'p_v_App.salesitems': 0,
            'p_v_App.pedido': 0,
            'p_v_App.pedidoitem': 0,
            'p_v_App.estoque': 0,
            'errors': 0,
            'skipped': 0
        }

        for i, obj in enumerate(data):
            model_name = obj.get('model')
            pk = obj.get('pk')
            fields = obj.get('fields', {})

            try:
                if model_name == 'auth.user':
                    self.load_user(pk, fields, dry_run)
                    stats['auth.user'] += 1

                elif model_name == 'p_v_App.category':
                    self.load_category(pk, fields, dry_run)
                    stats['p_v_App.category'] += 1

                elif model_name == 'p_v_App.products':
                    self.load_product(pk, fields, dry_run)
                    stats['p_v_App.products'] += 1

                elif model_name == 'p_v_App.sales':
                    self.load_sale(pk, fields, dry_run)
                    stats['p_v_App.sales'] += 1

                elif model_name == 'p_v_App.salesitems':
                    self.load_sales_item(pk, fields, dry_run)
                    stats['p_v_App.salesitems'] += 1

                elif model_name == 'p_v_App.pedido':
                    self.load_pedido(pk, fields, dry_run)
                    stats['p_v_App.pedido'] += 1

                elif model_name == 'p_v_App.pedidoitem':
                    self.load_pedido_item(pk, fields, dry_run)
                    stats['p_v_App.pedidoitem'] += 1

                elif model_name == 'p_v_App.estoque':
                    self.load_estoque(pk, fields, dry_run)
                    stats['p_v_App.estoque'] += 1

                else:
                    self.stdout.write(f'Modelo não reconhecido: {model_name}')
                    stats['skipped'] += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Erro ao processar objeto {i+1} (modelo: {model_name}, pk: {pk}): {e}'
                    )
                )
                stats['errors'] += 1
                continue

            # Mostrar progresso
            if (i + 1) % 100 == 0:
                self.stdout.write(
                    f'Processados {i + 1}/{len(data)} objetos...')

        # Estatísticas finais
        self.stdout.write('\n=== ESTATÍSTICAS FINAIS ===')
        for key, value in stats.items():
            if value > 0:
                self.stdout.write(f'{key}: {value}')

        self.stdout.write(
            self.style.SUCCESS('Carregamento concluído!')
        )

    def parse_date_field(self, date_string):
        """Converte string de data para objeto datetime."""
        if not date_string:
            return timezone.now()

        try:
            return parse_datetime(date_string)
        except:
            return timezone.now()

    def load_user(self, pk, fields, dry_run=False):
        """Carrega usuário."""
        if dry_run:
            self.stdout.write(
                f'[DRY-RUN] Criaria usuário: {fields.get("username", "")}')
            return

        user, created = User.objects.get_or_create(
            pk=pk,
            defaults={
                'username': fields.get('username', ''),
                'first_name': fields.get('first_name', ''),
                'last_name': fields.get('last_name', ''),
                'email': fields.get('email', ''),
                'is_staff': fields.get('is_staff', False),
                'is_active': fields.get('is_active', True),
                'is_superuser': fields.get('is_superuser', False),
                'date_joined': self.parse_date_field(fields.get('date_joined')),
                'last_login': self.parse_date_field(fields.get('last_login')),
                'password': fields.get('password', ''),
            }
        )

    def load_category(self, pk, fields, dry_run=False):
        """Carrega categoria."""
        if dry_run:
            self.stdout.write(
                f'[DRY-RUN] Criaria categoria: {fields.get("name", "")}')
            return

        category, created = Category.objects.get_or_create(
            pk=pk,
            defaults={
                'name': fields.get('name', ''),
                'description': fields.get('description', ''),
                'status': fields.get('status', 1),
                'date_added': self.parse_date_field(fields.get('date_added')),
                'date_updated': self.parse_date_field(fields.get('date_updated')),
            }
        )

    def load_product(self, pk, fields, dry_run=False):
        """Carrega produto."""
        if dry_run:
            self.stdout.write(
                f'[DRY-RUN] Criaria produto: {fields.get("name", "")}')
            return

        category_id = fields.get('category_id')
        try:
            category = Category.objects.get(pk=category_id)
        except Category.DoesNotExist:
            raise CommandError(
                f'Categoria {category_id} não encontrada para produto {pk}')

        product, created = Products.objects.get_or_create(
            pk=pk,
            defaults={
                'code': fields.get('code', ''),
                'category_id': category,
                'name': fields.get('name', ''),
                'description': fields.get('description', ''),
                'price': fields.get('price', 0),
                'status': fields.get('status', 1),
                'custo': fields.get('custo', 0),
                'date_added': self.parse_date_field(fields.get('date_added')),
                'date_updated': self.parse_date_field(fields.get('date_updated')),
            }
        )

    def load_sale(self, pk, fields, dry_run=False):
        """Carrega venda."""
        if dry_run:
            self.stdout.write(
                f'[DRY-RUN] Criaria venda: {fields.get("code", "")}')
            return

        sale, created = Sales.objects.get_or_create(
            pk=pk,
            defaults={
                'customer_name': fields.get('customer_name', ''),
                'code': fields.get('code', ''),
                'sub_total': fields.get('sub_total', 0),
                'grand_total': fields.get('grand_total', 0),
                'tax_amount': fields.get('tax_amount', 0),
                'tax': fields.get('tax', 0),
                'tendered_amount': fields.get('tendered_amount', 0),
                'amount_change': fields.get('amount_change', 0),
                'forma_pagamento': fields.get('forma_pagamento', 'PIX'),
                'endereco_entrega': fields.get('endereco_entrega', ''),
                'type': fields.get('type', 'venda'),
                'status': fields.get('status', ''),
                'date_added': self.parse_date_field(fields.get('date_added')),
                'date_updated': self.parse_date_field(fields.get('date_updated')),
            }
        )

    def load_sales_item(self, pk, fields, dry_run=False):
        """Carrega item de venda."""
        if dry_run:
            self.stdout.write(f'[DRY-RUN] Criaria item de venda: {pk}')
            return

        sale_id = fields.get('sale_id')
        try:
            sale = Sales.objects.get(pk=sale_id)
        except Sales.DoesNotExist:
            raise CommandError(
                f'Venda {sale_id} não encontrada para item {pk}')

        product_id = fields.get('product_id')
        try:
            product = Products.objects.get(pk=product_id)
        except Products.DoesNotExist:
            raise CommandError(
                f'Produto {product_id} não encontrado para item {pk}')

        sales_item, created = salesItems.objects.get_or_create(
            pk=pk,
            defaults={
                'sale_id': sale,
                'product_id': product,
                'price': fields.get('price', 0),
                'qty': fields.get('qty', 0),
                'total': fields.get('total', 0),
            }
        )

    def load_pedido(self, pk, fields, dry_run=False):
        """Carrega pedido."""
        if dry_run:
            self.stdout.write(
                f'[DRY-RUN] Criaria pedido: {fields.get("code", "")}')
            return

        pedido, created = Pedido.objects.get_or_create(
            pk=pk,
            defaults={
                'customer_name': fields.get('customer_name', ''),
                'code': fields.get('code', ''),
                'sub_total': fields.get('sub_total', 0),
                'tax': fields.get('tax', 0),
                'tax_amount': fields.get('tax_amount', 0),
                'grand_total': fields.get('grand_total', 0),
                'tendered_amount': fields.get('tendered_amount', 0),
                'amount_change': fields.get('amount_change', 0),
                'forma_pagamento': fields.get('forma_pagamento', 'PIX'),
                'endereco_entrega': fields.get('endereco_entrega', ''),
                'taxa_entrega': fields.get('taxa_entrega', 0),
                'status': fields.get('status', 'pendente'),
                'date_added': self.parse_date_field(fields.get('date_added')),
                'date_updated': self.parse_date_field(fields.get('date_updated')),
            }
        )

    def load_pedido_item(self, pk, fields, dry_run=False):
        """Carrega item de pedido."""
        if dry_run:
            self.stdout.write(f'[DRY-RUN] Criaria item de pedido: {pk}')
            return

        pedido_id = fields.get('pedido')
        try:
            pedido = Pedido.objects.get(pk=pedido_id)
        except Pedido.DoesNotExist:
            raise CommandError(
                f'Pedido {pedido_id} não encontrado para item {pk}')

        product_id = fields.get('product')
        try:
            product = Products.objects.get(pk=product_id)
        except Products.DoesNotExist:
            raise CommandError(
                f'Produto {product_id} não encontrado para item {pk}')

        pedido_item, created = PedidoItem.objects.get_or_create(
            pk=pk,
            defaults={
                'pedido': pedido,
                'product': product,
                'price': fields.get('price', 0),
                'qty': fields.get('qty', 0),
                'taxa_entrega': fields.get('taxa_entrega', 0),
                'total': fields.get('total', 0),
            }
        )

    def load_estoque(self, pk, fields, dry_run=False):
        """Carrega estoque."""
        if dry_run:
            self.stdout.write(f'[DRY-RUN] Criaria estoque: {pk}')
            return

        produto_id = fields.get('produto')
        try:
            produto = Products.objects.get(pk=produto_id)
        except Products.DoesNotExist:
            raise CommandError(
                f'Produto {produto_id} não encontrado para estoque {pk}')

        categoria_id = fields.get('categoria')
        try:
            categoria = Category.objects.get(pk=categoria_id)
        except Category.DoesNotExist:
            raise CommandError(
                f'Categoria {categoria_id} não encontrada para estoque {pk}')

        descricao = None
        descricao_id = fields.get('descricao')
        if descricao_id:
            try:
                descricao = Products.objects.get(pk=descricao_id)
            except Products.DoesNotExist:
                pass

        estoque, created = Estoque.objects.get_or_create(
            pk=pk,
            defaults={
                'produto': produto,
                'quantidade': fields.get('quantidade', 0),
                'categoria': categoria,
                'validade': fields.get('validade', 0),
                'descricao': descricao,
                'data_validade': fields.get('data_validade'),
                'preco': fields.get('preco', 0),
                'custo': fields.get('custo', 0),
                'status': fields.get('status', 1),
            }
        )
