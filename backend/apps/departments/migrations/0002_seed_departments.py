from django.db import migrations

# A starting set so the first colleague can be filed under something. Names line
# up with the docket category columns in `apps.dockets.constants` where the two
# overlap. Admins add, rename and archive from /departments after this.
DEPARTMENTS = [
    {"slug": "grocery", "name": "Grocery", "code": "GROC"},
    {"slug": "fresh-produce", "name": "Fresh Produce", "code": "PROD"},
    {"slug": "butchery", "name": "Butchery", "code": "MEAT"},
    {"slug": "deli", "name": "Deli", "code": "DELI"},
    {"slug": "bakery", "name": "Bakery", "code": "BAKE"},
    {"slug": "off-licence", "name": "Off-Licence", "code": "OFFL"},
    {"slug": "chilled-provisions", "name": "Chilled & Provisions", "code": "CHIL"},
    {"slug": "frozen", "name": "Frozen", "code": "FROZ"},
    {"slug": "non-food", "name": "Non Food", "code": "NONF"},
    {"slug": "checkouts", "name": "Checkouts", "code": "TILL"},
    {"slug": "warehouse", "name": "Warehouse", "code": "WHSE"},
    {"slug": "store-management", "name": "Store Management", "code": "MGMT"},
]


def seed_departments(apps, schema_editor):
    Department = apps.get_model("departments", "Department")
    for entry in DEPARTMENTS:
        Department.objects.update_or_create(slug=entry["slug"], defaults=entry)


def unseed_departments(apps, schema_editor):
    Department = apps.get_model("departments", "Department")
    Department.objects.filter(slug__in=[entry["slug"] for entry in DEPARTMENTS]).delete()


class Migration(migrations.Migration):
    dependencies = [("departments", "0001_initial")]

    operations = [migrations.RunPython(seed_departments, unseed_departments)]
