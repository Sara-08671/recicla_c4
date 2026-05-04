from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Usuario
from .forms import JornadaForm
from django.shortcuts import get_object_or_404, render
from .models import Jornada, Inscripcion, Asistencia, Puntaje, AccionDestacada
from .forms import InscripcionForm
from django.utils import timezone
from .models import Jornada, Usuario
from django.core.mail import send_mail
from django.urls import reverse
from django.contrib.sites.shortcuts import get_current_site
from .models import TemaForo, Usuario, ReaccionForo, ComentarioForo, DenunciaForo
from django.utils import timezone
from .models import Jornada
from datetime import datetime, timedelta
from django.contrib.auth.hashers import check_password, make_password
from django.db.models import Sum, Count, Q
from functools import wraps
from .models import Notificacion
from django.db import models
from .decorators import rol_required
from django.db.models import Sum, Max
from .models import Usuario, Puntaje
from .forms import JornadaForm, AsignarPuntajeForm
from .forms import PuntajeForm
import openpyxl
from django.core.paginator import Paginator
from django.db import IntegrityError
from xhtml2pdf import pisa
from django.template.loader import render_to_string
import io
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from django.utils import timezone
from .models import Usuario, UserChangeLog
from .forms import UsuarioForm
from django.urls import reverse
from django.core.mail import send_mail
from django.utils.crypto import get_random_string
from .forms import PasswordResetRequestForm
from .models import Notificacion
from .validators import validar_contrasena_segura, validar_mayor_14_annos
from django.core.exceptions import ValidationError


# ---------------------------
# INICIO DE SESION Y REGISTRO
# ---------------------------

# LOGIN
def login_view(request):
    if request.method == "POST":
        correo = request.POST.get("correo")
        contrasena = request.POST.get("contrasena")

        try:
            usuario = Usuario.objects.get(correo=correo)

            # Verificar si está bloqueado
            if usuario.bloqueado_hasta and timezone.now() < usuario.bloqueado_hasta:
                remaining = (usuario.bloqueado_hasta - timezone.now()).total_seconds() // 3600
                messages.error(request, f"Cuenta bloqueada por intentos fallidos. Intente de nuevo en {int(remaining)} horas.")
                return redirect("login")

            # validar la contraseña encriptada
            if not check_password(contrasena, usuario.contrasena):
                usuario.intentos_fallidos += 1
                if usuario.intentos_fallidos >= 5:
                    usuario.bloqueado_hasta = timezone.now() + timedelta(hours=24)
                usuario.save()

                intentos_restantes = 5 - usuario.intentos_fallidos
                if intentos_restantes > 0:
                    messages.error(request, f"Correo o contraseña incorrectos. Te quedan {intentos_restantes} intentos.")
                else:
                    messages.error(request, "Has alcanzado el máximo de intentos. Cuenta bloqueada por 24 horas.")
                return redirect("login")

            # Verificar que la cuenta esté verificada
            if not usuario.verificado:
                messages.error(request, "Debes verificar tu correo antes de iniciar sesión. Revisa tu bandeja de entrada.")
                return redirect("login")

            # Verificar estado (pendiente, rechazado, etc.)
            if not usuario.puede_acceder():
                if usuario.estado == 'pendiente':
                    messages.error(request, "Tu cuenta está pendiente de aprobación.")
                elif usuario.estado == 'rechazado':
                    messages.error(request, "Tu solicitud fue rechazada.")
                return redirect("login")

            # Resetear intentos fallidos al login exitoso
            usuario.intentos_fallidos = 0
            usuario.bloqueado_hasta = None
            usuario.save()

        except Usuario.DoesNotExist:
            messages.error(request, "Correo o contraseña incorrectos")
            return redirect("login")

        # Normalizar rol y guardar sesión
        rol_normalizado = (usuario.rol or "").strip().lower()

        request.session["usuario_id"] = usuario.id_usuario
        request.session["usuario_nombre"] = usuario.nombre
        request.session["usuario_rol"] = rol_normalizado

        # Redirección por rol
        if rol_normalizado == "administrador":
            return redirect("admi_inicio")
        elif rol_normalizado == "organizador":
            return redirect("organizador_inicio")
        else:
            return redirect("residente_inicio")

    return render(request, "login/login.html")



# REGISTRO
def register_view(request):
    if request.method == "POST":
        nombre = request.POST.get("nombre")
        apellido = request.POST.get("apellido")
        correo = request.POST.get("correo")
        contrasena = request.POST.get("contrasena")
        fecha_nacimiento_str = request.POST.get("fecha_nacimiento")
        barrio = request.POST.get("barrio")
        rol = request.POST.get("rol")
        justificacion = request.POST.get("justificacion", "").strip()

        # Validar campos obligatorios
        campos_obligatorios = {
            "nombre": nombre,
            "apellido": apellido,
            "correo": correo,
            "contrasena": contrasena,
            "fecha_nacimiento": fecha_nacimiento_str,
            "barrio": barrio,
            "rol": rol,
        }
        for campo, valor in campos_obligatorios.items():
            if not valor:
                messages.error(request, f"El campo '{campo}' es obligatorio.")
                return redirect("register")

        # Validar correo único
        if Usuario.objects.filter(correo=correo).exists():
            messages.error(request, "El correo ya está registrado.")
            return redirect("register")

        # Validar edad (mayor de 14 años)
        try:
            fecha_nacimiento = datetime.strptime(fecha_nacimiento_str, "%Y-%m-%d").date()
        except ValueError:
            messages.error(request, "Fecha de nacimiento inválida.")
            return redirect("register")

        if not validar_mayor_14_annos(fecha_nacimiento):
            messages.error(request, "Debes tener al menos 14 años para registrarte.")
            return redirect("register")

        # Si el rol no es residente, requiere justificación
        if rol != "residente" and not justificacion:
            messages.error(request, "Debes proporcionar una justificación para solicitar el rol de organizador o administrador.")
            return redirect("register")

        # Estado inicial según rol
        if rol == "residente":
            estado_inicial = "activo"
        else:
            estado_inicial = "pendiente"

        # Generar token de verificación
        token_verificacion = get_random_string(64)

        nuevo_usuario = Usuario.objects.create(
            nombre=nombre,
            apellido=apellido,
            correo=correo,
            contrasena=make_password(contrasena),
            fecha_nacimiento=fecha_nacimiento,
            barrio=barrio,
            rol=rol,
            estado=estado_inicial,
            justificacion=justificacion if rol != "residente" else None,
            verificado=False,
            token_verificacion=token_verificacion,
            intentos_fallidos=0
        )

        # Enviar correo de verificación
        dominio = get_current_site(request).domain
        verificar_url = f"http://{dominio}/verify_email/{token_verificacion}/"

        mensaje_verificacion = f"""
Hola {nombre}!

Gracias por registrarte en Recicla Comuna 4.

Por favor, verifica tu correo haciendo clic en el siguiente enlace:

{verificar_url}

Este enlace expira en 24 horas.

Saludos,
Equipo Recicla Comuna 4
        """

        send_mail(
            subject="✅ Verifica tu correo - Recicla Comuna 4",
            message=mensaje_verificacion,
            from_email="reciclacomuna@gmail.com",
            recipient_list=[correo],
            fail_silently=False,
        )

        # Si es organizador o administrador, notificar al admin
        if rol in ["organizador", "administrador"]:
            aprobar_url = f"http://{dominio}/aprobar/{nuevo_usuario.id_usuario}/"
            rechazar_url = f"http://{dominio}/rechazar/{nuevo_usuario.id_usuario}/"

            mensaje_admin = f"""
NUEVA SOLICITUD DE USUARIO QUE REQUIERE APROBACIÓN:

📋 Información del usuario:
• Nombre: {nombre} {apellido}
• Correo: {correo}
• Rol solicitado: {rol.upper()}
• Barrio: {barrio}
• Justificación: {justificacion}
• Fecha de registro: {nuevo_usuario.fecha_registro}

⚡ Acciones disponibles:

✅ Aprobar usuario: {aprobar_url}
❌ Rechazar usuario: {rechazar_url}
            """

            send_mail(
                subject=f"🔔 Nueva solicitud de {rol} - Recicla Comuna 4",
                message=mensaje_admin,
                from_email="reciclacomuna@gmail.com",
                recipient_list=["reciclacomuna@gmail.com"],
                fail_silently=False,
            )

        # Enviar correo de verificación
        dominio = get_current_site(request).domain
        verificar_url = f"http://{dominio}/verify_email/{token_verificacion}/"

        mensaje_verificacion = f"""
Hola {nombre}!

Gracias por registrarte en Recicla Comuna 4.

Por favor, verifica tu correo haciendo clic en el siguiente enlace:

{verificar_url}

Este enlace expira en 24 horas.

Saludos,
Equipo Recicla Comuna 4
        """

        send_mail(
            subject="✅ Verifica tu correo - Recicla Comuna 4",
            message=mensaje_verificacion,
            from_email="reciclacomuna@gmail.com",
            recipient_list=[correo],
            fail_silently=False,
        )

        # Si es organizador o administrador, notificar al admin para aprobación
        if rol in ["organizador", "administrador"]:
            aprobar_url = f"http://{dominio}/aprobar/{nuevo_usuario.id_usuario}/"
            rechazar_url = f"http://{dominio}/rechazar/{nuevo_usuario.id_usuario}/"

            mensaje_admin = f"""
NUEVA SOLICITUD DE USUARIO QUE REQUIERE APROBACIÓN:

📋 Información del usuario:
• Nombre: {nombre} {apellido}
• Correo: {correo}
• Rol solicitado: {rol.upper()}
• Barrio: {barrio}
• Justificación: {justificacion}
• Fecha de registro: {nuevo_usuario.fecha_registro}

⚡ Acciones disponibles:

✅ Aprobar usuario: {aprobar_url}
❌ Rechazar usuario: {rechazar_url}
            """

            send_mail(
                subject=f"🔔 Nueva solicitud de {rol} - Recicla Comuna 4",
                message=mensaje_admin,
                from_email="reciclacomuna@gmail.com",
                recipient_list=["reciclacomuna@gmail.com"],
                fail_silently=False,
            )

        messages.success(request, "✅ Registro exitoso. Revisa tu correo para verificar tu cuenta.")
        return redirect("login")

    return render(request, "login/register.html")


def solicitudes_pendientes(request):
    """Vista para ver usuarios pendientes de aprobación"""
    if not request.session.get("usuario_id"):
        return redirect("login")

    usuario_actual = Usuario.objects.get(id_usuario=request.session["usuario_id"])
    if usuario_actual.rol != "administrador":
        messages.error(request, "No tienes permisos para ver esta página.")
        return redirect("admi_inicio")

    # Rechazar automáticamente solicitudes pendientes > 72 horas
    limite_tiempo = timezone.now() - timedelta(hours=72)
    solicitudes_expiradas = Usuario.objects.filter(
        estado='pendiente',
        rol__in=['organizador', 'administrador'],
        fecha_registro__lt=limite_tiempo
    )
    for usuario_exp in solicitudes_expiradas:
        usuario_exp.estado = 'rechazado'
        usuario_exp.save()
        send_mail(
            subject="❌ Solicitud de cuenta rechazada automáticamente - Recicla Comuna 4",
            message=f"""
Hola {usuario_exp.nombre},

Tu solicitud para el rol de {usuario_exp.rol} no fue aprobada dentro del plazo de 72 horas y ha sido rechazada automáticamente.

Si crees que esto es un error, por favor contacta al administrador del sistema.

Saludos,
Equipo Recicla Comuna 4
            """,
            from_email="reciclacomuna@gmail.com",
            recipient_list=[usuario_exp.correo],
            fail_silently=False,
        )

    pendientes = Usuario.objects.filter(estado='pendiente', rol__in=['organizador', 'administrador'])
    return render(request, "administrador/solicitudes_pendientes.html", {
        'solicitudes': pendientes
    })

def aprobar_usuario(request, id_usuario):
    usuario = Usuario.objects.get(id_usuario=id_usuario)

    if usuario.estado == 'pendiente':
        usuario.estado = 'aprobado'
        usuario.save()

        if usuario.verificado:
            mensaje = f"""
¡Felicidades {usuario.nombre}!

Tu solicitud para el rol de {usuario.rol} ha sido aprobada.

Ahora puedes iniciar sesión en: http://{get_current_site(request).domain}

Saludos,
Equipo Recicla Comuna 4
            """
        else:
            mensaje = f"""
¡Felicidades {usuario.nombre}!

Tu solicitud para el rol de {usuario.rol} ha sido aprobada.

Antes de poder iniciar sesión, debes verificar tu correo electrónico.
Revisa tu bandeja de entrada (y spam) para el enlace de verificación.

Una vez verificada tu cuenta, podrás acceder al sistema.

Saludos,
Equipo Recicla Comuna 4
            """

        send_mail(
            subject="✅ Tu cuenta ha sido aprobada - Recicla Comuna 4",
            message=mensaje,
            from_email="reciclacomuna@gmail.com",
            recipient_list=[usuario.correo],
            fail_silently=False,
        )

        return HttpResponse(f"""
        <div style="text-align: center; padding: 50px; font-family: Arial;">
            <h2 style="color: #27AE60;">✅ Usuario Aprobado</h2>
            <p>El usuario <strong>{usuario.nombre}</strong> ha sido aprobado exitosamente.</p>
            <p>Se ha enviado una notificación por correo.</p>
            <a href="/" style="color: #2e7d32;">Volver al inicio</a>
        </div>
        """)
    else:
        return HttpResponse("Este usuario ya fue procesado anteriormente.")

def rechazar_usuario(request, id_usuario):
    usuario = Usuario.objects.get(id_usuario=id_usuario)
    
    if usuario.estado == 'pendiente':
        usuario.estado = 'rechazado'
        usuario.save()
        
        send_mail(
            subject="❌ Solicitud de cuenta rechazada - Recicla Comuna 4",
            message=f"""
Hola {usuario.nombre},

Lamentamos informarte que tu solicitud para el rol de {usuario.rol} ha sido rechazada.

Si crees que esto es un error, por favor contacta al administrador del sistema.

Saludos,
Equipo Recicla Comuna 4
            """,
            from_email="reciclacomuna@gmail.com",
            recipient_list=[usuario.correo],
            fail_silently=False,
        )
        
        return HttpResponse(f"""
        <div style="text-align: center; padding: 50px; font-family: Arial;">
            <h2 style="color: #e74c3c;">❌ Usuario Rechazado</h2>
            <p>El usuario <strong>{usuario.nombre}</strong> ha sido rechazado.</p>
            <p>Se ha enviado una notificación por correo.</p>
            <a href="/" style="color: #2e7d32;">Volver al inicio</a>
        </div>
        """)
    else:
        return HttpResponse("Este usuario ya fue procesado anteriormente.")



def password_reset_request(request):
    if request.method == "POST":
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            correo = form.cleaned_data['correo']
            try:
                usuario = Usuario.objects.get(correo=correo)
                token = get_random_string(64)
                usuario.reset_token = token
                usuario.save()

                print(f"TOKEN GUARDADO: {usuario.reset_token}")
                token = get_random_string(64)
                
                usuario.reset_token = token
                usuario.save()
                

                dominio = get_current_site(request).domain
                reset_url = f"http://{dominio}/reset_password/{token}/"

                mensaje = f"""
Hola {usuario.nombre},

Recibimos una solicitud para restablecer tu contraseña.

Haz clic en el siguiente enlace para crear una nueva contraseña:

{reset_url}

Si no solicitaste esto, puedes ignorar este mensaje.

Saludos,
Equipo Recicla Comuna 4
                """

                send_mail(
                    subject="🔑 Restablecer contraseña - RC4",
                    message=mensaje,
                    from_email="reciclacomuna@gmail.com",
                    recipient_list=[correo],
                    fail_silently=False,
                )

                messages.success(request, "Se ha enviado un enlace a tu correo para restablecer tu contraseña.")
                return redirect("login")

            except Usuario.DoesNotExist:
                messages.error(request, "No existe un usuario con ese correo.")
    else:
        form = PasswordResetRequestForm()

    return render(request, "login/password_reset_request.html", {"form": form})

def password_reset_confirm(request, token):
    try:
        usuario = Usuario.objects.get(reset_token=token)
    except Usuario.DoesNotExist:
        messages.error(request, "Token inválido o expirado.")
        return redirect("login")

    if request.method == "POST":
        nueva_contrasena = request.POST.get("nueva_contrasena")
        confirmar_contrasena = request.POST.get("confirmar_contrasena")

        if nueva_contrasena != confirmar_contrasena:
            messages.error(request, "Las contraseñas no coinciden.")
            return redirect(request.path)

        try:
            validar_contrasena_segura(nueva_contrasena)
        except ValidationError as e:
            messages.error(request, f"Contraseña no cumple requisitos: {e.messages[0]}")
            return redirect(request.path)

        usuario.contrasena = make_password(nueva_contrasena)
        usuario.reset_token = ""
        usuario.save()

        messages.success(request, "Contraseña actualizada correctamente. Puedes iniciar sesión.")
        return redirect("login")

    return render(request, "login/password_reset_confirm.html")


def verify_email(request, token):
    try:
        usuario = Usuario.objects.get(token_verificacion=token)
    except Usuario.DoesNotExist:
        messages.error(request, "Enlace de verificación inválido o expirado.")
        return redirect("login")

    if usuario.verificado:
        messages.info(request, "Tu cuenta ya estaba verificada. Ya puedes iniciar sesión.")
        return redirect("login")

    usuario.verificado = True
    usuario.fecha_verificacion = timezone.now()
    usuario.token_verificacion = None

    if usuario.rol == "residente":
        usuario.estado = "activo"

    usuario.save()

    if usuario.rol == "residente":
        messages.success(request, "✅ ¡Cuenta verificada correctamente! Ya puedes iniciar sesión.")
    else:
        messages.success(request, "✅ ¡Cuenta verificada! Espera a que un administrador apruebe tu solicitud.")
    return redirect("login")


# -------------------------
#  ADMINISTRADOR
# -------------------------

#LISTADO PRINCIPAL
@rol_required('administrador')
def admin_users_list(request):
    uid = request.session.get("usuario_id")
    if not uid:
        return redirect("login")
    try:
        user = Usuario.objects.get(id_usuario=uid)
        if user.rol != "administrador":
            messages.error(request, "No tienes permisos.")
            return redirect("admi_inicio")
    except Usuario.DoesNotExist:
        return redirect("login")

    q = request.GET.get("q", "").strip()
    rol = request.GET.get("rol", "")
    estado = request.GET.get("estado", "")
    page = int(request.GET.get("page", 1))
    per_page = int(request.GET.get("per_page", 10))

    users_qs = Usuario.objects.all().order_by('-fecha_registro')

    if q:
        users_qs = users_qs.filter(
            Q(nombre__icontains=q) | Q(apellido__icontains=q) | Q(correo__icontains=q)
        )
    if rol:
        users_qs = users_qs.filter(rol=rol)
    if estado:
        users_qs = users_qs.filter(estado=estado)

    paginator = Paginator(users_qs, per_page)
    page_obj = paginator.get_page(page)

    context = {
        "users": page_obj,
        "q": q,
        "rol": rol,
        "estado": estado,
        "page_obj": page_obj,
        "per_page": per_page,
    }
    return render(request, "administrador/usuarios_list.html", context)

#CREAR USUARIO
@rol_required('administrador')
def admin_users_create(request):
    uid = request.session.get("usuario_id")
    if not uid:
        return redirect("login")
    usuario_actual = Usuario.objects.get(id_usuario=uid)
    if usuario_actual.rol != "administrador":
        messages.error(request, "No tienes permisos.")
        return redirect("admi_inicio")

    if request.method == "POST":
        form = UsuarioForm(request.POST)
        if form.is_valid():
            if pwd:
                nuevo.contrasena = make_password(pwd)
            else:
                nuevo.contrasena = make_password("Cambiar123!")

            token_ver = get_random_string(64)
            nuevo.token_verificacion = token_ver
            nuevo.verificado = False
            nuevo.intentos_fallidos = 0
            if nuevo.rol == "residente":
                nuevo.estado = "pendiente"
            nuevo.save()

            # Enviar correo de verificación
            dominio = get_current_site(request).domain
            verificar_url = f"http://{dominio}/verify_email/{token_ver}/"
            mensaje_ver = f"""
Hola {nuevo.nombre}!

Bienvenido a Recicla Comuna 4. Por favor, verifica tu correo:

{verificar_url}

Saludos,
Equipo Recicla Comuna 4
            """
            send_mail(
                subject="✅ Verifica tu correo - Recicla Comuna 4",
                message=mensaje_ver,
                from_email="reciclacomuna@gmail.com",
                recipient_list=[nuevo.correo],
                fail_silently=False,
            )

            UserChangeLog.objects.create(
                usuario=nuevo,
                quien=f"{usuario_actual.nombre} {usuario_actual.apellido}",
                accion="crear",
                detalle=f"Creado por admin id={usuario_actual.id_usuario}"
            )
            messages.success(request, "Usuario creado. Se ha enviado correo de verificación.")
            return redirect("admin_users_list")
    else:
        form = UsuarioForm()

    return render(request, "administrador/usuarios_form.html", {"form": form, "crear": True})

# EDITAR USUARIO
@rol_required('administrador')
def admin_users_edit(request, id_usuario):
    uid = request.session.get("usuario_id")
    if not uid:
        return redirect("login")
    usuario_actual = Usuario.objects.get(id_usuario=uid)
    if usuario_actual.rol != "administrador":
        messages.error(request, "No tienes permisos.")
        return redirect("admi_inicio")

    usuario = get_object_or_404(Usuario, id_usuario=id_usuario)

    if request.method == "POST":
        form = UsuarioForm(request.POST, instance=usuario)
        if form.is_valid():
            viejo = { "nombre": usuario.nombre, "apellido": usuario.apellido, "correo": usuario.correo, "rol": usuario.rol, "estado": usuario.estado }
            form.save()
            UserChangeLog.objects.create(
                usuario=usuario,
                quien=f"{usuario_actual.nombre} {usuario_actual.apellido}",
                accion="editar",
                detalle=f"Antes: {viejo}"
            )
            messages.success(request, "Usuario actualizado.")
            return redirect("admin_users_list")
    else:
        form = UsuarioForm(instance=usuario)

    return render(request, "administrador/usuarios_form.html", {"form": form, "crear": False, "usuario_obj": usuario})

# SUSPENDER USUARIO
@rol_required('administrador')
def admin_users_suspend(request, id_usuario):
    uid = request.session.get("usuario_id")
    if not uid:
        return redirect("login")
    usuario_actual = Usuario.objects.get(id_usuario=uid)
    if usuario_actual.rol != "administrador":
        messages.error(request, "No tienes permisos.")
        return redirect("admi_inicio")

    usuario = get_object_or_404(Usuario, id_usuario=id_usuario)
    usuario.estado = "suspendido"
    usuario.save()
    UserChangeLog.objects.create(usuario=usuario, quien=f"{usuario_actual.nombre} {usuario_actual.apellido}", accion="suspender", detalle="Suspensión por administrador")
    messages.success(request, "Usuario suspendido (no eliminado).")
    return redirect("admin_users_list")

# RESTAURAR USUARIO
@rol_required('administrador')
def admin_users_restore(request, id_usuario):
    uid = request.session.get("usuario_id")
    if not uid:
        return redirect("login")
    usuario_actual = Usuario.objects.get(id_usuario=uid)
    if usuario_actual.rol != "administrador":
        messages.error(request, "No tienes permisos.")
        return redirect("admi_inicio")

    usuario = get_object_or_404(Usuario, id_usuario=id_usuario)
    usuario.estado = "activo"
    usuario.save()
    UserChangeLog.objects.create(usuario=usuario, quien=f"{usuario_actual.nombre} {usuario_actual.apellido}", accion="restaurar", detalle="Restaurado por administrador")
    messages.success(request, "Usuario reactivado.")
    return redirect("admin_users_deleted")

# LISTADO DE SUSPENDIDOS
@rol_required('administrador')
def admin_users_deleted(request):
    uid = request.session.get("usuario_id")
    if not uid:
        return redirect("login")
    usuario_actual = Usuario.objects.get(id_usuario=uid)
    if usuario_actual.rol != "administrador":
        messages.error(request, "No tienes permisos.")
        return redirect("admi_inicio")

    usuarios = Usuario.objects.filter(estado="suspendido").order_by("-fecha_registro")
    return render(request, "administrador/usuarios_deleted.html", {"usuarios": usuarios})

# EXPORTAR A XLSX
@rol_required('administrador')
def admin_users_export_xlsx(request):
    uid = request.session.get("usuario_id")
    if not uid:
        return redirect("login")
    usuario_actual = Usuario.objects.get(id_usuario=uid)
    if usuario_actual.rol != "administrador":
        messages.error(request, "No tienes permisos.")
        return redirect("admi_inicio")

    usuarios = Usuario.objects.all().order_by("id_usuario")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["ID", "Nombre", "Apellido", "Correo", "Rol", "Estado", "Fecha registro"])
    for u in usuarios:
        ws.append([u.id_usuario, u.nombre, u.apellido, u.correo, u.rol, u.estado, u.fecha_registro])

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    response = HttpResponse(stream.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response['Content-Disposition'] = 'attachment; filename=usuarios.xlsx'
    return response

# EXPORTAR A PDF
@rol_required('administrador')
def admin_users_export_pdf(request):
    uid = request.session.get("usuario_id")
    if not uid:
        return redirect("login")
    usuario_actual = Usuario.objects.get(id_usuario=uid)
    if usuario_actual.rol != "administrador":
        messages.error(request, "No tienes permisos.")
        return redirect("admi_inicio")

    usuarios = Usuario.objects.all().order_by("id_usuario")
    html = render_to_string("administrador/usuarios_pdf.html", {"usuarios": usuarios})
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    else:
        messages.error(request, "Error generando PDF")
        return redirect("admin_users_list")

# BUSQUEDA
@rol_required('administrador')
def admin_users_api_search(request):
    q = request.GET.get("q", "").strip()
    rol = request.GET.get("rol", "")
    estado = request.GET.get("estado", "")
    qs = Usuario.objects.all().order_by('-fecha_registro')
    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(apellido__icontains=q) | Q(correo__icontains=q))
    if rol:
        qs = qs.filter(rol=rol)
    if estado:
        qs = qs.filter(estado=estado)

    data = []
    for u in qs[:200]:
        data.append({
            "id": u.id_usuario,
            "nombre": u.nombre,
            "apellido": u.apellido,
            "correo": u.correo,
            "rol": u.rol,
            "estado": u.estado,
        })
    return JsonResponse({"results": data})

def inscribirse_jornada(request, jornada_id):
    jornada = get_object_or_404(Jornada, id=jornada_id)

    if request.method == 'POST':
        form = InscripcionForm(request.POST)
        if form.is_valid():
            inscripcion = form.save(commit=False)
            inscripcion.fecha_inscripcion = timezone.now()
            inscripcion.save()
            return redirect('detalle_jornada', jornada_id=jornada.id)
    else:
        form = InscripcionForm(initial={'jornada': jornada.id, 'usuario': request.user.id})

    return render(request, 'residente/inscripcion.html', {'form': form, 'jornada': jornada})

# CREAR JORNADA
@rol_required('administrador')
def admi_creacion_jornadas(request):
    if request.method == "POST":
        titulo = request.POST.get("titulo")
        descripcion = request.POST.get("descripcion")
        fecha = request.POST.get("fecha")
        hora = request.POST.get("hora")
        barrio = request.POST.get("barrio")
        direccion = request.POST.get("direccion")
        tipo_material = request.POST.get("tipo_material")
        cupo_maximo = request.POST.get("cupo_maximo")
        estado = request.POST.get("estado")

        Jornada.objects.create(
            titulo=titulo,
            descripcion=descripcion,
            fecha=fecha,
            hora=hora,
            barrio=barrio,
            direccion=direccion,
            tipo_material=tipo_material,
            cupo_maximo=cupo_maximo,
            estado=estado
        )
        return redirect("admi_creacion_jornadas")

    jornadas = Jornada.objects.all().order_by("-fecha")

    for j in jornadas:
        j.inscritos_activos = Inscripcion.objects.filter(
            jornada=j, estado='activa'
        ).count()

    return render(request, "administrador/creacionjornadas.html", {
        "jornadas": jornadas
    })

# PANEL
@rol_required('administrador')
def admin_panel(request):
    if not request.session.get("usuario_id"):
        return redirect("login")
    return render(request, "administrador/asistencia.html")

# FORO ADMIN
@rol_required('administrador')
def admi_foro_publicaciones(request):
    FECHA_CORTE = timezone.datetime(2025, 11, 23, tzinfo=timezone.get_current_timezone())

    publicaciones = TemaForo.objects.filter(
        fecha_publicacion__gte=FECHA_CORTE
    ).annotate(
        total_me_gusta=Count('reacciones', filter=Q(reacciones__tipo='me_gusta')),
        total_no_me_gusta=Count('reacciones', filter=Q(reacciones__tipo='no_me_gusta')),
        total_me_encanta=Count('reacciones', filter=Q(reacciones__tipo='me_encanta')),
    ).prefetch_related('comentarios__autor').order_by("-fecha_publicacion")

    return render(request, "administrador/foro_publicaciones.html", {
        "publicaciones": publicaciones
    })

@rol_required('administrador')
def admi_publicacion_foro(request):
    if request.method == "POST":
        titulo = request.POST.get("titulo")
        contenido = request.POST.get("contenido")
        usuario_id = request.session.get("usuario_id")

        if not usuario_id:
            messages.error(request, "Debe iniciar sesión para publicar.")
            return redirect("login")

        try:
            usuario = Usuario.objects.get(id_usuario=usuario_id)

            TemaForo.objects.create(
                titulo=titulo,
                contenido=contenido,
                id_usuario=usuario,
                fecha_publicacion=timezone.now()
            )

            messages.success(request, "¡Publicación creada exitosamente! 🎉")
            return redirect("admi_foro_publicaciones")

        except Exception as e:
            messages.error(request, f"Error al guardar la publicación: {e}")

    return render(request, "administrador/publicacion_foro.html")

@rol_required('administrador')
def admi_recoleccion(request):
    return render(request, "administrador/recoleccion.html")

@rol_required('administrador')
def admi_recompensa(request):
    return render(request, "administrador/recompensa.html")

@rol_required('administrador')
def admi_educacion(request):
    return render(request, "administrador/educacion.html")

@rol_required('administrador')
def admi_contacto(request):
    return render(request, "administrador/contacto.html")

@rol_required('administrador')
def admi_inicio(request):
    return render(request, "administrador/inicio.html")

@rol_required('administrador')
def admi_asistencia(request):
    from datetime import timedelta
    from django.utils import timezone

    jornadas_finalizadas = Jornada.objects.filter(estado='finalizada')

    jornada_id = request.GET.get('jornada_id') or request.POST.get('jornada_id')
    jornada = None
    inscripciones = []

    if jornada_id:
        jornada = get_object_or_404(Jornada, id_jornada=jornada_id)

        if jornada.estado != 'finalizada':
            messages.error(request, "Solo se pueden asignar puntos a jornadas finalizadas.")
            return redirect("admi_asistencia")

        limite = jornada.last_update + timedelta(hours=48)
        if timezone.now() > limite:
            messages.error(request, "Ya pasaron las 48 horas limite para asignar puntos a esta jornada.")
            return redirect("admi_asistencia")

        inscripciones = Inscripcion.objects.filter(
            jornada=jornada,
            estado='activa'
        ).select_related('usuario')

    if request.method == "POST" and jornada:
        puntos_residente = 10
        puntos_organizador = 20

        for inscripcion in inscripciones:
            presente = request.POST.get(f"presente_{inscripcion.id_inscripcion}") == "1"
            observaciones = request.POST.get(f"obs_{inscripcion.id_inscripcion}", "")

            Asistencia.objects.update_or_create(
                inscripcion=inscripcion,
                defaults={
                    "presente": presente,
                    "observaciones": observaciones
                }
            )

            if presente:
                usuario = inscripcion.usuario
                puntos = puntos_organizador if usuario.rol == "organizador" else puntos_residente

                ya_tiene = Puntaje.objects.filter(
                    usuario=usuario,
                    jornada=jornada
                ).exists()

                if not ya_tiene:
                    Puntaje.objects.create(
                        usuario=usuario,
                        puntos=puntos,
                        motivo=f"Asistencia a jornada: {jornada.titulo}",
                        jornada=jornada
                    )

        messages.success(request, "Asistencia y puntos registrados correctamente.")
        return redirect("admi_asistencia")

    return render(request, "administrador/asistencia.html", {
        "jornadas_finalizadas": jornadas_finalizadas,
        "jornada": jornada,
        "inscripciones": inscripciones
    })

# CONFIGURACION
@rol_required('administrador')
def admi_configuracion(request):
    usuario_id = request.session.get("usuario_id")
    usuario = get_object_or_404(Usuario, id_usuario=usuario_id)

    if request.method == "POST":
        password_actual = request.POST.get("password_actual")
        password_nueva = request.POST.get("password_nueva")
        password_confirmacion = request.POST.get("password_confirmacion")

        if password_actual and password_nueva and password_confirmacion:
            if not check_password(password_actual, usuario.contrasena):
                messages.error(request, "❌ La contraseña actual es incorrecta.")
                return redirect("admi_configuracion")

            if password_nueva != password_confirmacion:
                messages.error(request, "❌ Las nuevas contraseñas no coinciden.")
                return redirect("admi_configuracion")

            usuario.contrasena = make_password(password_nueva)
            usuario.save()

            messages.success(request, "✔ Contraseña actualizada. Inicia sesión nuevamente.")
            return redirect("login")

    return render(request, "administrador/configuracion.html", {"usuario": usuario})

# PANEL USUARIOS
@rol_required('administrador')
def panel_usuarios(request):
    busqueda = request.GET.get('q', '')
    estado_filtro = request.GET.get('estado', '')
    page_number = request.GET.get('page', 1)
    per_page = 10

    usuarios_qs = Usuario.objects.exclude(estado='suspendido')

    if busqueda:
        usuarios_qs = usuarios_qs.filter(
            Q(nombre__icontains=busqueda) |
            Q(apellido__icontains=busqueda) |
            Q(correo__icontains=busqueda)
        )

    if estado_filtro:
        usuarios_qs = usuarios_qs.filter(estado=estado_filtro)

    paginator = Paginator(usuarios_qs, per_page)
    usuarios = paginator.get_page(page_number)

    suspendidos_qs = Usuario.objects.filter(estado='suspendido')
    paginator_sus = Paginator(suspendidos_qs, per_page)
    suspendidos = paginator_sus.get_page(page_number)

    if request.method == 'POST':
        form = PuntajeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('panel_usuarios')
    else:
        form = PuntajeForm()

    return render(request, 'administrador/usuarios.html', {
        'usuarios': usuarios,
        'suspendidos': suspendidos,
        'busqueda': busqueda,
        'estado_filtro': estado_filtro,
        'form': form
    })

# AGREGAR DEL PANEL USUARIOS
@rol_required('administrador')
def agregar_usuario(request):
    uid = request.session.get("usuario_id")
    if not uid:
        return redirect("login")
    
    usuario_actual = Usuario.objects.get(id_usuario=uid)
    if usuario_actual.rol != "administrador":
        messages.error(request, "No tienes permisos.")
        return redirect("admi_inicio")

    if request.method == "POST":
        nombre = request.POST.get("nombre")
        apellido = request.POST.get("apellido")
        correo = request.POST.get("correo")
        contrasena = request.POST.get("contrasena")
        fecha_nacimiento_str = request.POST.get("fecha_nacimiento")
        barrio = request.POST.get("barrio")
        rol = request.POST.get("rol")
        estado = request.POST.get("estado")

        if not all([nombre, apellido, correo, contrasena, fecha_nacimiento_str, barrio, rol, estado]):
            messages.error(request, "Todos los campos son obligatorios.")
            return redirect("agregar_usuario")

        if Usuario.objects.filter(correo=correo).exists():
            messages.error(request, "El correo ya está registrado.")
            return redirect("agregar_usuario")

        try:
            fecha_nacimiento = datetime.strptime(fecha_nacimiento_str, "%Y-%m-%d").date()
        except ValueError:
            messages.error(request, "Fecha de nacimiento inválida.")
            return redirect("agregar_usuario")

        if not validar_mayor_14_annos(fecha_nacimiento):
            messages.error(request, "El usuario debe tener al menos 14 años.")
            return redirect("agregar_usuario")

        nuevo_usuario = Usuario.objects.create(
            nombre=nombre,
            apellido=apellido,
            correo=correo,
            contrasena=make_password(contrasena),
            fecha_nacimiento=fecha_nacimiento,
            barrio=barrio,
            rol=rol,
            estado=estado,
            verificado=False,
            token_verificacion=get_random_string(64),
            intentos_fallidos=0
        )

        # Enviar correo de verificación
        dominio = get_current_site(request).domain
        verificar_url = f"http://{dominio}/verify_email/{nuevo_usuario.token_verificacion}/"
        mensaje_ver = f"""
Hola {nombre}!

Bienvenido a Recicla Comuna 4. Por favor, verifica tu correo:

{verificar_url}

Saludos,
Equipo Recicla Comuna 4
        """
        send_mail(
            subject="✅ Verifica tu correo - Recicla Comuna 4",
            message=mensaje_ver,
            from_email="reciclacomuna@gmail.com",
            recipient_list=[correo],
            fail_silently=False,
        )

        UserChangeLog.objects.create(
            usuario=nuevo_usuario,
            quien=f"{usuario_actual.nombre} {usuario_actual.apellido}",
            accion="crear",
            detalle=f"Creado por admin id={usuario_actual.id_usuario}"
        )

        messages.success(request, "Usuario creado correctamente. Se ha enviado correo de verificación.")
        return redirect("panel_usuarios")

    return render(request, "administrador/usuarios_agregar.html")

# REACTIVAR DEL PANEL USUARIOS
@rol_required('administrador')
def reactivar_usuario(request, id):
    uid = request.session.get("usuario_id")
    if not uid:
        return redirect("login")

    usuario_actual = Usuario.objects.get(id_usuario=uid)
    if usuario_actual.rol != "administrador":
        messages.error(request, "No tienes permisos.")
        return redirect("admi_inicio")

    usuario = get_object_or_404(Usuario, id_usuario=id)
    usuario.estado = "activo"
    usuario.save()

    UserChangeLog.objects.create(
        usuario=usuario,
        quien=f"{usuario_actual.nombre} {usuario_actual.apellido}",
        accion="reactivar",
        detalle="Usuario reactivado"
    )

    messages.success(request, "Usuario reactivado correctamente.")
    return redirect("panel_usuarios")

# EDITAR DEL PANEL USUARIOS
@rol_required('administrador')
def editar_usuario(request, id):
    uid = request.session.get("usuario_id")
    if not uid:
        return redirect("login")
    usuario_actual = Usuario.objects.get(id_usuario=uid)
    if usuario_actual.rol != "administrador":
        messages.error(request, "No tienes permisos.")
        return redirect("admi_inicio")

    usuario = get_object_or_404(Usuario, id_usuario=id)

    if request.method == "POST":
        viejo = {
            "nombre": usuario.nombre,
            "apellido": usuario.apellido,
            "correo": usuario.correo,
            "rol": usuario.rol,
            "estado": usuario.estado
        }

        usuario.nombre = request.POST.get("nombre")
        usuario.apellido = request.POST.get("apellido")
        usuario.correo = request.POST.get("correo")
        usuario.rol = request.POST.get("rol")
        usuario.estado = request.POST.get("estado")

        nueva_contra = request.POST.get("nueva_contrasena")
        if nueva_contra.strip() != "":
            usuario.contrasena = make_password(nueva_contra)

        usuario.save()

        UserChangeLog.objects.create(
            usuario=usuario,
            quien=f"{usuario_actual.nombre} {usuario_actual.apellido}",
            accion="editar",
            detalle=f"Antes: {viejo}"
        )

        messages.success(request, "Usuario actualizado correctamente.")
        return redirect("panel_usuarios")

    return render(request, "administrador/usuarios_editar.html", {"usuario": usuario})

# SUSPENDER DEL PANEL USUARIOS
@rol_required('administrador')
def suspender_usuario(request, id):
    uid = request.session.get("usuario_id")
    if not uid:
        return redirect("login")
    usuario_actual = Usuario.objects.get(id_usuario=uid)
    if usuario_actual.rol != "administrador":
        messages.error(request, "No tienes permisos.")
        return redirect("admi_inicio")

    usuario = get_object_or_404(Usuario, id_usuario=id)
    usuario.estado = "suspendido"
    usuario.save()

    UserChangeLog.objects.create(
        usuario=usuario,
        quien=f"{usuario_actual.nombre} {usuario_actual.apellido}",
        accion="suspender",
        detalle="Usuario suspendido"
    )

    messages.success(request, "Usuario suspendido correctamente.")
    return redirect("panel_usuarios")

@rol_required('administrador')
def eliminar_usuario(request, id_usuario):
    usuario = get_object_or_404(Usuario, id_usuario=id_usuario)

    try:
        usuario.delete()
    except IntegrityError:
        usuario.estado = 'suspendido'
        usuario.save()

    return redirect('panel_usuarios')


@rol_required('administrador')
def panel_puntajes(request):
    uid = request.session.get("usuario_id")
    if not uid:
        return redirect("login")
    
    usuario_actual = Usuario.objects.get(id_usuario=uid)
    if usuario_actual.rol != "administrador":
        messages.error(request, "No tienes permisos.")
        return redirect("admi_inicio")

    puntajes_qs = Puntaje.objects.select_related('usuario', 'jornada').order_by('-fecha')

    page = request.GET.get('page', 1)
    per_page = 10
    paginator = Paginator(puntajes_qs, per_page)
    page_obj = paginator.get_page(page)

    return render(request, "administrador/asignar_puntaje.html", {
        "puntajes": page_obj,
        "page_obj": page_obj
    })

@rol_required('administrador')
def perfil_admin(request):
    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        return redirect("login")
    
    usuario = get_object_or_404(Usuario, id_usuario=usuario_id)
    
    if usuario.rol != "administrador":
        messages.error(request, "No tienes permisos.")
        return redirect("admi_inicio")
    
    puntajes = Puntaje.objects.filter(usuario=usuario).order_by('-fecha')
    total_puntos = puntajes.aggregate(total=Sum('puntos'))['total'] or 0
    mayor_puntaje = puntajes.aggregate(mayor=Max('puntos'))['mayor'] or 0
    count = puntajes.count()
    promedio = (total_puntos / count) if count > 0 else 0
    promedio = round(promedio, 2)
    
    return render(request, "administrador/perfil.html", {
        "usuario": usuario,
        "puntajes": puntajes,
        "total_puntos": total_puntos,
        "mayor_puntaje": mayor_puntaje,
        "promedio": promedio
    })

@rol_required('administrador')
def historial_puntaje(request, id_usuario):
    usuario = get_object_or_404(Usuario, pk=id_usuario)
    puntajes = Puntaje.objects.filter(usuario=usuario).order_by('-fecha')
    
    if request.method == 'POST':
        form = AsignarPuntajeForm(request.POST)
        if form.is_valid():
            nuevo_puntaje = form.save(commit=False)
            nuevo_puntaje.usuario = usuario
            nuevo_puntaje.save()
            return redirect('historial_puntaje_admin', id_usuario=id_usuario)
    else:
        form = AsignarPuntajeForm()
    
    context = {
        'usuario': usuario,
        'puntajes': puntajes,
        'form': form,
    }
    return render(request, 'administrador/historial_puntaje.html', context)

@rol_required('administrador')
def cambiar_foto_admin(request):
    usuario_id = request.session.get("usuario_id")
    usuario = get_object_or_404(Usuario, id_usuario=usuario_id)

    if usuario.rol != "administrador":
        messages.error(request, "No tienes permisos.")
        return redirect("admi_inicio")

    if request.method == "POST":
        foto = request.FILES.get("foto")
        if foto:
            usuario.foto = foto
            usuario.save()
            messages.success(request, "Foto de perfil actualizada.")
            return redirect("perfil_admin")

    return render(request, "administrador/cambiar_foto.html", {"usuario": usuario})

@rol_required('administrador')
def asignar_puntaje(request, id_usuario):
    usuario = get_object_or_404(Usuario, id_usuario=id_usuario)

    if request.method == "POST":
        form = PuntajeForm(request.POST)
        if form.is_valid():
            puntaje = form.save(commit=False)
            puntaje.usuario = usuario
            puntaje.save()
            messages.success(request, "Puntaje asignado correctamente.")
            return redirect("historial_puntaje", id_usuario=usuario.id_usuario)
    else:
        form = PuntajeForm()

    return render(request, "administrador/asignar_puntaje.html", {
        "usuario": usuario,
        "form": form
    })

@rol_required('administrador')
def admi_notificaciones(request):
    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        return redirect("login")

    usuario = Usuario.objects.filter(id_usuario=usuario_id, rol="administrador").first()
    if not usuario:
        return redirect("login")

    query = request.GET.get("buscar", "")
    tipo_filtro = request.GET.get("tipo", "")
    usuario_filtro = request.GET.get("usuario", "")

    notificaciones = Notificacion.objects.all()

    if query:
        notificaciones = notificaciones.filter(
            Q(mensaje__icontains=query) |
            Q(tipo__icontains=query)
        )

    if tipo_filtro:
        notificaciones = notificaciones.filter(tipo=tipo_filtro)

    if usuario_filtro:
        notificaciones = notificaciones.filter(usuario_id=usuario_filtro)

    notificaciones = notificaciones.order_by('-fecha_envio')

    usuarios = Usuario.objects.all()

    if request.method == "POST":
        id_usuario = request.POST.get("usuario_id")
        tipo = request.POST.get("tipo")
        mensaje = request.POST.get("mensaje")

        if id_usuario and tipo and mensaje:
            Notificacion.objects.create(
                usuario_id=id_usuario,
                tipo=tipo,
                mensaje=mensaje
            )
            return redirect("admi_notificaciones")

    return render(request, "administrador/notificaciones.html", {
        "usuario": usuario,
        "notificaciones": notificaciones,
        "usuarios": usuarios,
        "query": query,
        "tipo_filtro": tipo_filtro,
        "usuario_filtro": usuario_filtro
    })

@rol_required('administrador')
def admi_eliminar_jornada(request, jornada_id):
    jornada = get_object_or_404(Jornada, id_jornada=jornada_id)
    jornada.delete()
    return redirect("admi_creacion_jornadas")

@rol_required('administrador')
def admi_modificar_jornada(request, jornada_id):
    jornada = get_object_or_404(Jornada, id_jornada=jornada_id)

    if request.method == "POST":
        form = JornadaForm(request.POST, instance=jornada)
        if form.is_valid():
            form.save()
            messages.success(request, "Jornada modificada correctamente.")
            return redirect("admi_creacion_jornadas")
    else:
        form = JornadaForm(instance=jornada)

    return render(request, "administrador/modificar_jornada.html", {"form": form, "jornada": jornada})

@rol_required('administrador')
def admi_validar_acciones(request):
    from .models import AccionDestacada

    acciones_pendientes = AccionDestacada.objects.filter(
        validada=False
    ).select_related('inscripcion__usuario', 'inscripcion__jornada')

    if request.method == "POST":
        accion_id = request.POST.get("accion_id")
        accion = get_object_or_404(AccionDestacada, id=accion_id)

        accion.validada = True
        accion.save()

        Puntaje.objects.create(
            usuario=accion.inscripcion.usuario,
            puntos=accion.puntos_sugeridos,
            motivo=f"Accion destacada: {accion.descripcion}",
            jornada=accion.inscripcion.jornada
        )

        messages.success(request, f"Accion validada y {accion.puntos_sugeridos} puntos asignados a {accion.inscripcion.usuario.nombre}.")
        return redirect("admi_validar_acciones")

    return render(request, "administrador/validar_acciones.html", {
        "acciones_pendientes": acciones_pendientes
    })


# ---------------------------
# PANEL RESIDENTE
# ---------------------------
@rol_required('residente')
def residente_lista_jornadas(request):
    jornadas = Jornada.objects.exclude(
        estado='cancelada'
    ).order_by('fecha')

    for j in jornadas:
        j.inscritos_activos = Inscripcion.objects.filter(
            jornada=j, estado='activa'
        ).count()

    return render(request, "residente/lista_jornadas.html", {
        "jornadas": jornadas
    })

@rol_required('residente')
def residente_ver_jornada(request, id_jornada):
    jornada = get_object_or_404(Jornada, id_jornada=id_jornada)

    return render(request, "residente/ver_jornada.html", {
        "jornada": jornada
    })

# FORO RESIDENTE
@rol_required('residente')
def residente_foro_publicaciones(request):
    FECHA_CORTE = timezone.datetime(2025, 11, 23, tzinfo=timezone.get_current_timezone())

    publicaciones = TemaForo.objects.filter(
        fecha_publicacion__gte=FECHA_CORTE
    ).annotate(
        total_me_gusta=Count('reacciones', filter=Q(reacciones__tipo='me_gusta')),
        total_no_me_gusta=Count('reacciones', filter=Q(reacciones__tipo='no_me_gusta')),
        total_me_encanta=Count('reacciones', filter=Q(reacciones__tipo='me_encanta')),
    ).prefetch_related('comentarios__autor').order_by("-fecha_publicacion")

    return render(request, "residente/foro_publicaciones.html", {
        "publicaciones": publicaciones
    })

@rol_required('residente')
def residente_publicacion_foro(request):
    if request.method == "POST":
        titulo = request.POST.get("titulo")
        contenido = request.POST.get("contenido")
        usuario_id = request.session.get("usuario_id")

        if not usuario_id:
            messages.error(request, "Debe iniciar sesión para publicar.")
            return redirect("login")

        try:
            usuario = Usuario.objects.get(id_usuario=usuario_id)

            TemaForo.objects.create(
                titulo=titulo,
                contenido=contenido,
                id_usuario=usuario,
                fecha_publicacion=timezone.now()
            )

            messages.success(request, "¡Publicación creada exitosamente! 🎉")
            return redirect("residente_foro_publicaciones")

        except Exception as e:
            messages.error(request, f"Error al guardar la publicación: {e}")

    return render(request, "residente/publicacion_foro.html")

@rol_required('residente')
def residente_panel(request):
    return render(request, "residente/panel.html")


@rol_required('residente')
def residente_index(request):
    return render(request, "residente/index.html")

@rol_required('residente')
def residente_inicio(request):
    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        return redirect("login")
    
    usuario = get_object_or_404(Usuario, id_usuario=usuario_id)
    return render(request, 'residente/inicio.html', {'usuario': usuario})

@rol_required('residente')
def residente_inscripcion(request, id_jornada):
    jornada = get_object_or_404(Jornada, id_jornada=id_jornada)
    usuario_id = request.session.get("usuario_id")
    usuario = get_object_or_404(Usuario, id_usuario=usuario_id)

    if jornada.estado != 'activa':
        messages.error(request, "No puedes inscribirte en esta jornada porque esta " + jornada.estado + ".")
        return render(request, "residente/inscripcion.html", {
            "jornada": jornada,
            "usuario": usuario
        })

    if request.method == "POST":
        ya_inscrito = Inscripcion.objects.filter(
            usuario=usuario,
            jornada=jornada,
            estado='activa'
        ).exists()

        if ya_inscrito:
            messages.error(request, "Ya estas inscrito en esta jornada.")
            return render(request, "residente/inscripcion.html", {
                "jornada": jornada,
                "usuario": usuario
            })

        inscritos_activos = Inscripcion.objects.filter(
            jornada=jornada,
            estado='activa'
        ).count()

        if jornada.cupo_maximo and inscritos_activos >= jornada.cupo_maximo:
            messages.error(request, "Lo sentimos, esta jornada ya alcanzo el cupo maximo.")
            return render(request, "residente/inscripcion.html", {
                "jornada": jornada,
                "usuario": usuario
            })

        Inscripcion.objects.create(
            usuario=usuario,
            jornada=jornada,
            estado='activa'
        )

        mensaje = (
            f"Hola {usuario.nombre}!\n\n"
            f"Tu inscripcion a la jornada fue exitosa. Aqui estan los detalles:\n\n"
            f"Jornada: {jornada.titulo}\n"
            f"Fecha: {jornada.fecha}\n"
            f"Hora: {jornada.hora}\n"
            f"Lugar: {jornada.direccion}, {jornada.barrio}\n"
            f"Tipo de material: {jornada.tipo_material}\n\n"
            f"Te esperamos. Recuerda llegar a tiempo.\n"
            f"Equipo Recicla Comuna 4"
        )

        Notificacion.objects.create(
            usuario=usuario,
            tipo="inscripcion",
            mensaje=mensaje
        )

        send_mail(
            subject="Confirmacion de inscripcion - Recicla Comuna 4",
            message=mensaje,
            from_email="reciclacomuna@gmail.com",
            recipient_list=[usuario.correo],
            fail_silently=True,
        )

        return render(request, "residente/inscripcion.html", {
            "jornada": jornada,
            "usuario": usuario,
            "inscripcion_exitosa": True
        })

    return render(request, "residente/inscripcion.html", {
        "jornada": jornada,
        "usuario": usuario
    })

@rol_required('residente')
def residente_configuracion(request):
    usuario_id = request.session.get("usuario_id")
    usuario = get_object_or_404(Usuario, id_usuario=usuario_id)

    if request.method == "POST":
        password_actual = request.POST.get("password_actual")
        password_nueva = request.POST.get("password_nueva")
        password_confirmacion = request.POST.get("password_confirmacion")

        if password_actual and password_nueva and password_confirmacion:
            if not check_password(password_actual, usuario.contrasena):
                messages.error(request, "❌ La contraseña actual es incorrecta.")
                return redirect("residente_configuracion")

            if password_nueva != password_confirmacion:
                messages.error(request, "❌ Las nuevas contraseñas no coinciden.")
                return redirect("residente_configuracion")

            try:
                validar_contrasena_segura(password_nueva)
            except ValidationError as e:
                messages.error(request, f"❌ {e.messages[0]}")
                return redirect("residente_configuracion")

            usuario.contrasena = make_password(password_nueva)
            usuario.save()

            messages.success(request, "✔ Contraseña actualizada. Inicia sesión nuevamente.")
            return redirect("login")

    return render(request, "residente/configuracion.html", {"usuario": usuario})

@rol_required('residente')
def residente_recoleccion(request):
    return render(request, "residente/recoleccion.html")

@rol_required('residente')
def residente_cat_recompensas(request):
    return render(request, "residente/cat_recompensas.html")

@rol_required('residente')
def residente_como_participar(request):
    return render(request, "residente/como_participar.html")

@rol_required('residente')
def residente_educacion(request):
    return render(request, "residente/educacion.html")

@rol_required('residente')
def residente_contacto(request):
    return render(request, "residente/contacto.html")

@rol_required('residente')
def perfil_residente(request):
    usuario_id = request.session.get("usuario_id")
    usuario = get_object_or_404(Usuario, id_usuario=usuario_id)

    puntajes = Puntaje.objects.filter(usuario=usuario).order_by('-fecha')
    total_puntos = puntajes.aggregate(total=Sum('puntos'))['total'] or 0
    mayor_puntaje = puntajes.aggregate(mayor=Max('puntos'))['mayor'] or 0
    count = puntajes.count()
    promedio = (total_puntos / count) if count > 0 else 0
    promedio = round(promedio, 2)

    return render(request, 'residente/perfil.html', {
        'usuario': usuario,
        'puntajes': puntajes,
        'total_puntos': total_puntos,
        'mayor_puntaje': mayor_puntaje,
        'promedio': promedio,
    })
 
@rol_required('residente')       
def cambiar_foto(request):
    usuario_id = request.session.get("usuario_id")
    usuario = get_object_or_404(Usuario, id_usuario=usuario_id)

    if request.method == "POST":
        foto = request.FILES.get("foto")
        if foto:
            usuario.foto = foto
            usuario.save()
            return redirect("perfil_residente")

    return render(request, "residente/cambiar_foto.html", {"usuario": usuario})

@rol_required('residente')
def residente_notificaciones(request):
    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        return redirect("login")

    usuario = Usuario.objects.filter(id_usuario=usuario_id).first()
    if not usuario:
        return redirect("login")

    notificaciones = Notificacion.objects.filter(
        usuario_id=usuario.id_usuario
    ).order_by('-fecha_envio')

    return render(request, "residente/notificaciones.html", {
        "usuario": usuario,
        "notificaciones": notificaciones
    })


# ---------------------------
# PANEL ORGANIZADOR
# ---------------------------

# CREAR JORNADA
@rol_required('organizador')
def organizador_creacion_jornadas(request):
    if request.method == "POST":
        titulo = request.POST.get("titulo")
        descripcion = request.POST.get("descripcion")
        fecha = request.POST.get("fecha")
        hora = request.POST.get("hora")
        barrio = request.POST.get("barrio")
        direccion = request.POST.get("direccion")
        tipo_material = request.POST.get("tipo_material")
        cupo_maximo = request.POST.get("cupo_maximo")
        estado = request.POST.get("estado")

        Jornada.objects.create(
            titulo=titulo,
            descripcion=descripcion,
            fecha=fecha,
            hora=hora,
            barrio=barrio,
            direccion=direccion,
            tipo_material=tipo_material,
            cupo_maximo=cupo_maximo,
            estado=estado
        )
        return redirect("organizador_creacion_jornadas")

    jornadas = Jornada.objects.all().order_by("-fecha")

    for j in jornadas:
        j.inscritos_activos = Inscripcion.objects.filter(
            jornada=j, estado='activa'
        ).count()

    return render(request, "organizador/creacionjornadas.html", {
        "jornadas": jornadas
    })

@rol_required('organizador')
def organizador_eliminar_jornada(request, jornada_id):
    jornada = get_object_or_404(Jornada, id_jornada=jornada_id)
    jornada.delete()
    return redirect("organizador_creacion_jornadas")

@rol_required('organizador')
def organizador_modificar_jornada(request, jornada_id):
    jornada = get_object_or_404(Jornada, id_jornada=jornada_id)

    if request.method == "POST":
        form = JornadaForm(request.POST, instance=jornada)
        if form.is_valid():
            form.save()
            messages.success(request, "Jornada modificada correctamente.")
            return redirect("organizador_creacion_jornadas")
    else:
        form = JornadaForm(instance=jornada)

    return render(request, "organizador/modificar_jornada.html", {"form": form, "jornada": jornada})

# FORO ORGANIZADOR
@rol_required('organizador')
def organizador_foro_publicaciones(request):
    FECHA_CORTE = timezone.datetime(2025, 11, 23, tzinfo=timezone.get_current_timezone())

    publicaciones = TemaForo.objects.filter(
        fecha_publicacion__gte=FECHA_CORTE
    ).annotate(
        total_me_gusta=Count('reacciones', filter=Q(reacciones__tipo='me_gusta')),
        total_no_me_gusta=Count('reacciones', filter=Q(reacciones__tipo='no_me_gusta')),
        total_me_encanta=Count('reacciones', filter=Q(reacciones__tipo='me_encanta')),
    ).prefetch_related('comentarios__autor').order_by("-fecha_publicacion")

    return render(request, "organizador/foro_publicaciones.html", {
        "publicaciones": publicaciones
    })

@rol_required('organizador')
def organizador_publicacion_foro(request):
    if request.method == "POST":
        titulo = request.POST.get("titulo")
        contenido = request.POST.get("contenido")
        usuario_id = request.session.get("usuario_id")

        if not usuario_id:
            messages.error(request, "Debe iniciar sesión para publicar.")
            return redirect("login")

        try:
            usuario = Usuario.objects.get(id_usuario=usuario_id)

            TemaForo.objects.create(
                titulo=titulo,
                contenido=contenido,
                id_usuario=usuario,
                fecha_publicacion=timezone.now()
            )

            messages.success(request, "¡Publicación creada exitosamente! 🎉")
            return redirect("organizador_foro_publicaciones")

        except Exception as e:
            messages.error(request, f"Error al guardar la publicación: {e}")

    return render(request, "organizador/publicacion_foro.html")

@rol_required('organizador')
def organizador_recoleccion(request):
    return render(request, "organizador/recoleccion.html")

@rol_required('organizador')
def organizador_recompensa(request):
    return render(request, "organizador/recompensa.html")

@rol_required('organizador')
def organizador_educacion(request):
    return render(request, "organizador/educacion.html")

@rol_required('organizador')
def organizador_contacto(request):
    return render(request, "organizador/contacto.html")

@rol_required('organizador')
def organizador_inicio(request):
    return render(request, "organizador/inicio.html")

@rol_required('organizador')
def organizador_asistencia(request):
    jornadas_finalizadas = Jornada.objects.filter(estado='finalizada')

    jornada_id = request.GET.get('jornada_id') or request.POST.get('jornada_id')
    jornada = None
    inscripciones = []

    if jornada_id:
        jornada = get_object_or_404(Jornada, id_jornada=jornada_id)
        inscripciones = Inscripcion.objects.filter(
            jornada=jornada,
            estado='activa'
        ).select_related('usuario')

    if request.method == "POST" and jornada:
        for inscripcion in inscripciones:
            descripcion = request.POST.get(f"accion_{inscripcion.id_inscripcion}", "").strip()
            puntos = request.POST.get(f"puntos_{inscripcion.id_inscripcion}", 5)

            if descripcion:
                AccionDestacada.objects.create(
                    inscripcion=inscripcion,
                    descripcion=descripcion,
                    puntos_sugeridos=puntos,
                    validada=False
                )

        messages.success(request, "Acciones destacadas registradas. El administrador las validara.")
        return redirect("organizador_asistencia")

    return render(request, "organizador/asistencia.html", {
        "jornadas_finalizadas": jornadas_finalizadas,
        "jornada": jornada,
        "inscripciones": inscripciones
    })

# CONFIGURACION
@rol_required('organizador')
def organizador_configuracion(request):
    usuario_id = request.session.get("usuario_id")
    usuario = get_object_or_404(Usuario, id_usuario=usuario_id)

    if request.method == "POST":
        password_actual = request.POST.get("password_actual")
        password_nueva = request.POST.get("password_nueva")
        password_confirmacion = request.POST.get("password_confirmacion")

        if password_actual and password_nueva and password_confirmacion:
            if not check_password(password_actual, usuario.contrasena):
                messages.error(request, "❌ La contraseña actual es incorrecta.")
                return redirect("organizador_configuracion")

            if password_nueva != password_confirmacion:
                messages.error(request, "❌ Las nuevas contraseñas no coinciden.")
                return redirect("organizador_configuracion")

            try:
                validar_contrasena_segura(password_nueva)
            except ValidationError as e:
                messages.error(request, f"❌ {e.messages[0]}")
                return redirect("organizador_configuracion")

            usuario.contrasena = make_password(password_nueva)
            usuario.save()

            messages.success(request, "✔ Contraseña actualizada. Inicia sesión nuevamente.")
            return redirect("login")

    return render(request, "organizador/configuracion.html", {"usuario": usuario})

@rol_required('organizador')
def perfil_organizador(request):
    usuario_id = request.session.get("usuario_id")
    usuario = get_object_or_404(Usuario, id_usuario=usuario_id)

    puntajes = Puntaje.objects.filter(usuario=usuario).order_by('-fecha')
    total_puntos = puntajes.aggregate(total=Sum('puntos'))['total'] or 0
    mayor_puntaje = puntajes.aggregate(mayor=Max('puntos'))['mayor'] or 0
    count = puntajes.count()
    promedio = (total_puntos / count) if count > 0 else 0
    promedio = round(promedio, 2)

    return render(request, 'organizador/perfil.html', {
        'usuario': usuario,
        'puntajes': puntajes,
        'total_puntos': total_puntos,
        'mayor_puntaje': mayor_puntaje,
        'promedio': promedio,
    })
            
@rol_required('organizador')
def cambiar_foto_organizador(request):
    usuario_id = request.session.get("usuario_id")
    usuario = get_object_or_404(Usuario, id_usuario=usuario_id)

    if usuario.rol != "organizador":
        messages.error(request, "No tienes permisos.")
        return redirect("organizador_inicio")

    if request.method == "POST":
        foto = request.FILES.get("foto")
        if foto:
            usuario.foto = foto
            usuario.save()
            messages.success(request, "Foto de perfil actualizada.")
            return redirect("perfil_organizador")

    return render(request, "organizador/cambiar_foto.html", {"usuario": usuario})


@rol_required('organizador')
def organizador_notificaciones(request):
    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        return redirect("login")

    usuario = Usuario.objects.filter(id_usuario=usuario_id).first()
    if not usuario:
        return redirect("login")

    notificaciones = Notificacion.objects.filter(
        usuario_id=usuario.id_usuario
    ).order_by('-fecha_envio')

    return render(request, "organizador/notificaciones.html", {
        "usuario": usuario,
        "notificaciones": notificaciones
    })


# ---------------------------
# PANEL USUARIO
# ---------------------------

def usuario_inicio(request):
    return render(request, "usuario/inicio.html")

def usuario_como_participar(request):
    return render(request, "usuario/como_participar.html")

def usuario_educacion(request):
    return render(request, "usuario/educacion.html")

def usuario_contacto(request):
    return render(request, "usuario/contacto.html")


def usuario_foro_publicaciones(request):
    FECHA_CORTE = timezone.datetime(2025, 11, 23, tzinfo=timezone.get_current_timezone())

    publicaciones = TemaForo.objects.filter(
        fecha_publicacion__gte=FECHA_CORTE
    ).annotate(
        total_me_gusta=Count('reacciones', filter=Q(reacciones__tipo='me_gusta')),
        total_no_me_gusta=Count('reacciones', filter=Q(reacciones__tipo='no_me_gusta')),
        total_me_encanta=Count('reacciones', filter=Q(reacciones__tipo='me_encanta')),
    ).prefetch_related('comentarios__autor').order_by("-fecha_publicacion")

    return render(request, "usuario/foro_publicaciones.html", {
        "publicaciones": publicaciones
    })


# ---------------------------
# LOGOUT
# ---------------------------

def logout_view(request):
    request.session.flush()
    messages.success(request, "Sesión cerrada correctamente.")
    return redirect('login')


# ---------------------------
# FORO - ACCIONES AJAX
# ---------------------------

def foro_reaccionar(request, tema_id):
    if not request.session.get("usuario_id"):
        return JsonResponse({'error': 'No autenticado'}, status=401)

    if request.method != "POST":
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body)
        tipo = data.get('tipo')
    except Exception:
        return JsonResponse({'error': 'Datos inválidos'}, status=400)

    if tipo not in ['me_gusta', 'no_me_gusta', 'me_encanta']:
        return JsonResponse({'error': 'Tipo de reacción inválido'}, status=400)

    usuario = get_object_or_404(Usuario, id_usuario=request.session["usuario_id"])
    tema = get_object_or_404(TemaForo, id_tema=tema_id)

    reaccion_existente = ReaccionForo.objects.filter(tema=tema, usuario=usuario).first()

    if reaccion_existente:
        if reaccion_existente.tipo == tipo:
            # Mismo botón → quitar reacción (toggle)
            reaccion_existente.delete()
            accion = 'eliminada'
        else:
            # Cambiar reacción
            reaccion_existente.tipo = tipo
            reaccion_existente.save()
            accion = 'actualizada'
    else:
        ReaccionForo.objects.create(tema=tema, usuario=usuario, tipo=tipo)
        accion = 'creada'

    return JsonResponse({
        'accion': accion,
        'me_gusta': tema.reacciones.filter(tipo='me_gusta').count(),
        'no_me_gusta': tema.reacciones.filter(tipo='no_me_gusta').count(),
        'me_encanta': tema.reacciones.filter(tipo='me_encanta').count(),
        'mi_reaccion': tipo if accion != 'eliminada' else '',
    })


def foro_comentar(request, tema_id):
    if not request.session.get("usuario_id"):
        return JsonResponse({'error': 'No autenticado'}, status=401)

    if request.method != "POST":
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body)
        contenido = data.get('contenido', '').strip()
    except Exception:
        return JsonResponse({'error': 'Datos inválidos'}, status=400)

    if not contenido:
        return JsonResponse({'error': 'El comentario no puede estar vacío'}, status=400)

    usuario = get_object_or_404(Usuario, id_usuario=request.session["usuario_id"])
    tema = get_object_or_404(TemaForo, id_tema=tema_id)

    comentario = ComentarioForo.objects.create(
        tema=tema,
        autor=usuario,
        contenido=contenido
    )

    return JsonResponse({
        'id': comentario.id,
        'autor': f"{usuario.nombre} {usuario.apellido}",
        'contenido': comentario.contenido,
        'fecha': comentario.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
    })


def foro_denunciar(request, tema_id):
    if not request.session.get("usuario_id"):
        return JsonResponse({'error': 'No autenticado'}, status=401)

    if request.method != "POST":
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body)
        motivo = data.get('motivo', '').strip()
    except Exception:
        return JsonResponse({'error': 'Datos inválidos'}, status=400)

    if not motivo:
        return JsonResponse({'error': 'Debes escribir el motivo'}, status=400)

    usuario = get_object_or_404(Usuario, id_usuario=request.session["usuario_id"])
    tema = get_object_or_404(TemaForo, id_tema=tema_id)

    _, creada = DenunciaForo.objects.get_or_create(
        tema=tema,
        usuario=usuario,
        defaults={'motivo': motivo}
    )

    if not creada:
        return JsonResponse({'mensaje': 'Ya habías denunciado esta publicación anteriormente.'})

    return JsonResponse({'mensaje': '✅ Denuncia enviada correctamente. La revisaremos pronto.'})