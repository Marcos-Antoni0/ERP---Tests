from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('p_v_App', '0014_alter_pedidopayment_company'),
    ]

    operations = [
        migrations.AddField(
            model_name='sales',
            name='venda_a_prazo',
            field=models.BooleanField(
                default=False,
                help_text='Indica se a venda foi concluída com saldo a receber (débito).',
            ),
        ),
    ]
