# Generated by Django 3.2 on 2025-05-10
from django.db import migrations

def set_int_id(apps, schema_editor):
    Manga = apps.get_model('manga', 'Manga')
    for i, manga in enumerate(Manga.objects.all().order_by('created_at'), start=1):
        manga.int_id = i
        manga.save(update_fields=['int_id'])

class Migration(migrations.Migration):
    dependencies = [
        ('manga', '0012_fix_manga_ids_to_int'),
    ]

    operations = [
        migrations.RunPython(set_int_id),
    ]
