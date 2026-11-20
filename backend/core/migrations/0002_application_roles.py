from django.conf import settings
from django.db import migrations


ROLE_GROUPS = ('Safety Officer', 'Contracts Manager')


def create_roles_and_assign_demo_manager(apps, schema_editor):
    database = schema_editor.connection.alias
    Group = apps.get_model('auth', 'Group')
    user_app, user_model = settings.AUTH_USER_MODEL.split('.')
    User = apps.get_model(user_app, user_model)

    groups = {
        name: Group.objects.using(database).get_or_create(name=name)[0]
        for name in ROLE_GROUPS
    }
    demo_manager = (
        User.objects.using(database)
        .filter(username='demo-manager')
        .first()
    )
    if demo_manager:
        demo_manager.groups.add(groups['Contracts Manager'])


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(
            create_roles_and_assign_demo_manager,
            migrations.RunPython.noop,
        ),
    ]
