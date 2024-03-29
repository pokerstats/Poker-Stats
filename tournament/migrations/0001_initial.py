# Generated by Django 3.2 on 2023-01-23 21:08

import django.contrib.postgres.fields
import django.core.validators
from django.db import migrations, models
import tournament.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='TournamentStructure',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=254)),
                ('buyin_amount', models.DecimalField(decimal_places=2, max_digits=9)),
                ('bounty_amount', models.DecimalField(decimal_places=2, max_digits=9)),
                ('payout_percentages', django.contrib.postgres.fields.ArrayField(base_field=models.DecimalField(decimal_places=0, default=0, max_digits=3, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)]), size=None, validators=[tournament.models.validate_percentages])),
                ('allow_rebuys', models.BooleanField(default=False)),
            ],
        ),
    ]
