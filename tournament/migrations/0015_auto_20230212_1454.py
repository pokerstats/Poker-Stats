# Generated by Django 3.2 on 2023-02-12 22:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tournament', '0014_alter_tournamentplayerresult_placement'),
    ]

    operations = [
        migrations.AddField(
            model_name='tournamentelimination',
            name='is_backfill',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='tournamentrebuy',
            name='is_backfill',
            field=models.BooleanField(default=False),
        ),
    ]