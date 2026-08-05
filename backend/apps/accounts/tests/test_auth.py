import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.fixture
def store(db):
    from apps.stores.models import Store

    return Store.objects.get(slug="skerries")


@pytest.fixture
def user(db, store):
    return User.objects.create_user(
        email="staff@supervalu.ie",
        password="test-pass-1234",
        first_name="Aoife",
        store=store,
    )


def test_create_user_uses_email_as_identifier(user):
    assert user.email == "staff@supervalu.ie"
    assert user.role == User.Role.STAFF
    assert user.is_manager is False
    assert user.check_password("test-pass-1234")


def test_superuser_gets_admin_role(db):
    admin = User.objects.create_superuser(email="admin@supervalu.ie", password="x" * 12)
    assert admin.is_superuser and admin.is_staff
    assert admin.role == User.Role.ADMIN
    assert admin.is_manager is True


def test_token_obtain_and_me(client, user):
    response = client.post(
        reverse("accounts:token-obtain-pair"),
        {"email": user.email, "password": "test-pass-1234"},
        content_type="application/json",
    )
    assert response.status_code == 200, response.content
    access = response.json()["access"]

    me = client.get(reverse("accounts:me"), headers={"authorization": f"Bearer {access}"})
    assert me.status_code == 200
    assert me.json()["email"] == user.email
    assert me.json()["store"]["slug"] == "skerries"


def test_me_requires_authentication(client, db):
    assert client.get(reverse("accounts:me")).status_code == 401
