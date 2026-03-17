import factory
from django.contrib.auth import get_user_model
from app.apps.accounts.models import Profile, User

User = get_user_model()

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        pwd = extracted if extracted else "defaultpassword123"
        self.set_password(pwd)
        if create:
            self.save()
            
    email = factory.Sequence(lambda n: f"user{n}@gmail.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")

    password = factory.PostGenerationMethodCall("set_password", "Qwerty123!")

class ProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Profile

    user = factory.SubFactory(UserFactory)
    email = factory.LazyAttribute(lambda o: o.user.email)
    password = "Qwerty123!"
