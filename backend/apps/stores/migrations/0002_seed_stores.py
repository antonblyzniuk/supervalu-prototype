from django.db import migrations

# The three Moriarty Group branches. Codes are the SuperValu store numbers used
# by the legacy portal, kept so imported data still lines up.
STORES = [
    {"code": "374", "slug": "balbriggan", "name": "Balbriggan"},
    {"code": "356", "slug": "palmerstown", "name": "Palmerstown"},
    {"code": "424", "slug": "skerries", "name": "Skerries"},
]


def seed_stores(apps, schema_editor):
    Store = apps.get_model("stores", "Store")
    for entry in STORES:
        Store.objects.update_or_create(slug=entry["slug"], defaults=entry)


def unseed_stores(apps, schema_editor):
    Store = apps.get_model("stores", "Store")
    Store.objects.filter(slug__in=[s["slug"] for s in STORES]).delete()


class Migration(migrations.Migration):
    dependencies = [("stores", "0001_initial")]

    operations = [migrations.RunPython(seed_stores, unseed_stores)]
