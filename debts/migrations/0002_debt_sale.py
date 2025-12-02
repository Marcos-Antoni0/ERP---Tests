from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('p_v_App', '0015_sales_venda_a_prazo'),
        ('debts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='debt',
            name='sale',
            field=models.ForeignKey(
                blank=True,
                help_text='Venda de origem para rastreabilidade do débito.',
                null=True,
                on_delete=models.SET_NULL,
                related_name='linked_debts',
                to='p_v_App.sales',
            ),
        ),
    ]
