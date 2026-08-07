from django.db import migrations
from django.utils.text import slugify

# Departments became per-store in this migration. Every department that already
# existed is opened in every active branch, which is the state the group runs
# in — an admin archives the handful a given store does not have. New
# departments get the same treatment in `DepartmentSerializer.create`.


def open_in_every_store(apps, schema_editor):
    Department = apps.get_model("departments", "Department")
    StoreDepartment = apps.get_model("departments", "StoreDepartment")
    Store = apps.get_model("stores", "Store")

    stores = list(Store.objects.filter(is_active=True))
    for department in Department.objects.all():
        for store in stores:
            StoreDepartment.objects.get_or_create(
                department=department,
                store=store,
                defaults={"slug": slugify(f"{department.slug}-at-{store.slug}")},
            )


def close_them_again(apps, schema_editor):
    # Anything with staff assigned is PROTECTed and will refuse to go, which is
    # the point — reversing this should not quietly orphan anybody.
    StoreDepartment = apps.get_model("departments", "StoreDepartment")
    StoreDepartment.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("departments", "0003_remove_department_manager_storedepartment"),
        ("stores", "0002_seed_stores"),
    ]

    operations = [migrations.RunPython(open_in_every_store, close_them_again)]
