import django.db.models.deletion
from django.db import migrations, models


def repoint_to_store_departments(apps, schema_editor):
    """Move each assignment from the department kind to its branch instance.

    `department_id` stays an integer column throughout; only the table it points
    at changes, so rewriting the ids here means the FK constraint that
    `AlterField` rebuilds next already has valid rows to check. Anyone whose
    store has no instance of their department loses the assignment rather than
    blocking the migration — a manager re-picks it on /team.
    """
    User = apps.get_model("accounts", "User")
    StoreDepartment = apps.get_model("departments", "StoreDepartment")

    by_pair = {
        (row.department_id, row.store_id): row.pk for row in StoreDepartment.objects.all()
    }
    for user in User.objects.exclude(department_id=None).only("id", "department_id", "store_id"):
        User.objects.filter(pk=user.pk).update(
            department_id=by_pair.get((user.department_id, user.store_id))
        )


def repoint_to_department_kinds(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    StoreDepartment = apps.get_model("departments", "StoreDepartment")

    kind_by_instance = {row.pk: row.department_id for row in StoreDepartment.objects.all()}
    for user in User.objects.exclude(department_id=None).only("id", "department_id"):
        User.objects.filter(pk=user.pk).update(
            department_id=kind_by_instance.get(user.department_id)
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_user_department"),
        ("departments", "0004_open_departments_in_every_store"),
    ]

    operations = [
        migrations.RunPython(repoint_to_store_departments, repoint_to_department_kinds),
        migrations.AlterField(
            model_name="user",
            name="department",
            field=models.ForeignKey(
                blank=True,
                help_text="Department they work in, at their store. Implies the store.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="members",
                to="departments.storedepartment",
            ),
        ),
    ]
