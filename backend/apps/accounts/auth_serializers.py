from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Case-insensitive sign-in.

    Addresses are stored lower-cased, but a phone keyboard will happily
    capitalise the first letter — without this, `Aaron@…` fails to log in.
    """

    def validate(self, attrs):
        email = attrs.get(self.username_field)
        if isinstance(email, str):
            attrs[self.username_field] = email.strip().lower()
        return super().validate(attrs)


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer
