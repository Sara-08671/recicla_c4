import re
from django.core.exceptions import ValidationError


def validar_contrasena_segura(value):
    """
    Valida que la contraseña cumpla con requisitos básicos:
    - Mínimo 8 caracteres
    - No puede ser solo números
    """
    # Verificar longitud mínima
    if len(value) < 8:
        raise ValidationError("La contraseña debe tener al menos 8 caracteres.")
    
    # Verificar que no sea solo números
    if value.isdigit():
        raise ValidationError("La contraseña no puede ser solo números.")


def validar_mayor_14_annos(fecha_nacimiento):
    """
    Valida que la fecha de nacimiento indique al menos 14 años cumplidos.
    Retorna True si es válido, False en caso contrario.
    """
    from datetime import date
    today = date.today()
    edad = today.year - fecha_nacimiento.year - ((today.month, today.day) < (fecha_nacimiento.month, fecha_nacimiento.day))
    return edad >= 14
