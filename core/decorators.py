from functools import wraps
from django.shortcuts import render, redirect
from .models import Usuario

def rol_required(roles):
    if isinstance(roles, str):
        roles = [roles]
    roles = [r.strip().lower() for r in roles]

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            print("SESION:", request.session.get("usuario_id"), request.session.session_key)

            usuario_id = request.session.get("usuario_id")
            session_role = request.session.get("usuario_rol")

            # 1) Si no hay sesión => plantilla bonita
            if not usuario_id:
                return render(request, "errores/no_sesion.html")

            # 2) Comprobar rol en sesión primero (más rápido)
            if session_role:
                if session_role.strip().lower() in roles:
                    return view_func(request, *args, **kwargs)
                # si sesión dice otro rol, igual consultamos DB por seguridad y para depurar

            # 3) Consultar BD y verificar rol (normalizando)
            try:
                usuario = Usuario.objects.get(id_usuario=usuario_id)
            except Usuario.DoesNotExist:
                return render(request, "errores/no_sesion.html")

            db_role = (usuario.rol or "").strip().lower()
            if db_role in roles:
                # Sincronizar sesión con la info correcta por si acaso
                request.session['usuario_rol'] = usuario.rol
                return view_func(request, *args, **kwargs)

            return render(request, "errores/no_permiso.html")
        return _wrapped_view
    return decorator
