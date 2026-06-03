from django.contrib.auth.hashers import check_password
from django.utils import timezone
from .models import Usuario
from datetime import timedelta
import requests


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


class GoogleOAuthBackend:
    """
    Autentica usando OAuth de Google.
    """
    def authenticate(self, request, access_token=None):
        if not access_token:
            return None
        
        # Verificar el token de acceso con Google
        try:
            response = requests.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {access_token}'}
            )
            
            if response.status_code != 200:
                return None
                
            google_data = response.json()
            email = google_data.get('email')
            if not email:
                return None
                
            # Buscar o crear usuario
            try:
                usuario = Usuario.objects.get(correo=email)
            except Usuario.DoesNotExist:
                # Crear nuevo usuario desde datos de Google
                nombre_completo = google_data.get('name', '')
                # Dividir nombre en nombre y apellido (simple approach)
                if ' ' in nombre_completo:
                    nombre, apellido = nombre_completo.split(' ', 1)
                else:
                    nombre = nombre_completo
                    apellido = ''
                
                usuario = Usuario.objects.create(
                    nombre=nombre,
                    apellido=apellido,
                    correo=email,
                    # Generar una contraseña aleatoria (no se usará para login con Google)
                    contrasena=Usuario.make_random_password(),
                    rol='residente',  # Rol por defecto
                    estado='activo',  # Google ya verificó el email
                    verificado=True,  # Marcar como verificado
                    fecha_nacimiento=None,  # Se podrá actualizar después
                    barrio='',  # Se podrá actualizar después
                )
            
            # Verificar que el usuario pueda acceder
            if usuario.puede_acceder():
                return usuario
            return None
                
        except Exception:
            return None

    def get_user(self, user_id):
        try:
            return Usuario.objects.get(pk=user_id)
        except Usuario.DoesNotExist:
            return None
