from django.contrib.auth.hashers import check_password
from django.utils import timezone
from .models import Usuario
from datetime import timedelta

class UsuariosBackend:
    """
    Autentica contra la tabla usuarios de MySQL Workbench.
    Incluye validación de bloqueo por intentos fallidos.
    """
    MAX_INTENTOS = 5
    TIEMPO_BLOQUEO = timedelta(hours=24)  # 24 horas de bloqueo

    def authenticate(self, request, correo=None, contrasena=None):
        try:
            user = Usuario.objects.get(correo=correo)
        except Usuario.DoesNotExist:
            return None

        # Verificar si la cuenta está bloqueada
        if user.bloqueado_hasta and timezone.now() < user.bloqueado_hasta:
            return None  # Cuenta bloqueada

        # Verificar contraseña
        if check_password(contrasena, user.contrasena):
            # Autenticación exitosa: resetear contador de intentos
            user.intentos_fallidos = 0
            user.bloqueado_hasta = None
            user.save()
            return user
        else:
            # Contraseña incorrecta: incrementar contador
            user.intentos_fallidos += 1
            if user.intentos_fallidos >= self.MAX_INTENTOS:
                user.bloqueado_hasta = timezone.now() + self.TIEMPO_BLOQUEO
            user.save()
            return None

    def get_user(self, user_id):
        try:
            return Usuario.objects.get(pk=user_id)
        except Usuario.DoesNotExist:
            return None
