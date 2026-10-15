import factory
from django.contrib.auth import get_user_model

from app.apps.accounts.models import Profile

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@gmail.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")

    # UserFactory(password="...") задаёт свой пароль, по умолчанию — Qwerty123!
    password = factory.PostGenerationMethodCall("set_password", "Qwerty123!")


class ProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Profile

    user = factory.SubFactory(UserFactory)
    email = factory.LazyAttribute(lambda o: o.user.email)
