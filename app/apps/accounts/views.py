
from dj_rest_auth.registration.views import SocialLoginView, RegisterView, LoginView
from rest_framework import generics, permissions
from .serializers import UserSerializer, CustomRegisterSerializer, CustomLoginSerializer


class CustomRegisterView(RegisterView):
    permission_classes = [permissions.AllowAny]
    serializer_class = CustomRegisterSerializer
    
class CustomLoginView(LoginView):
    permission_classes = [permissions.AllowAny]
    serializer_class = CustomLoginSerializer

class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user