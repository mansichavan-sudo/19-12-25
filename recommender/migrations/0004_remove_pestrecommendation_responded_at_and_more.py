from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('recommender', '0003_pestrecommendation_action_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='pestrecommendation',
            name='allowed_channels',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='pestrecommendation',
            name='canonical_customer_id',
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='pestrecommendation',
            name='consent_call',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='pestrecommendation',
            name='consent_email',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='pestrecommendation',
            name='consent_whatsapp',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='pestrecommendation',
            name='experiment_group',
            field=models.CharField(choices=[('A', 'A'), ('B', 'B'), ('C', 'C')], default='A', max_length=1),
        ),
        migrations.AddField(
            model_name='pestrecommendation',
            name='exposure_channel',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='pestrecommendation',
            name='exposure_id',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='pestrecommendation',
            name='is_active',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='pestrecommendation',
            name='shown_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='pestrecommendation',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
