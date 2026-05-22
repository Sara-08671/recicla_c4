import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.models import Jornada, Inscripcion, Recordatorio, Usuario, Notificacion
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = 'Envia recordatorios de jornadas a los usuarios inscritos'

    def handle(self, *args, **options):
        ahora = timezone.now()
        self.stdout.write(f"Iniciando envio de recordatorios a las {ahora}...")

        recordatorios_enviados = 0
        recordatorios_error = 0

        # Obtener recordatorios activos que no han sido enviados
        recordatorios = Recordatorio.objects.filter(
            activo=True,
            enviado=False,
            jornada__estado__in=['activa', 'en_curso', 'pendiente']
        ).select_related('usuario', 'jornada')

        for recordatorio in recordatorios:
            usuario = recordatorio.usuario
            jornada = recordatorio.jornada
            periodicidad = recordatorio.periodicidad

            # Verificar que el usuario sigue inscrito y la jornada esta activa
            inscrito = Inscripcion.objects.filter(
                usuario=usuario,
                jornada=jornada,
                estado='activa'
            ).exists()

            if not inscrito:
                recordatorio.enviado = True
                recordatorio.save()
                continue

            # Calcular el umbral de tiempo segun la periodicidad
            try:
                if periodicidad == '24h':
                    delta = timedelta(hours=24)
                    nombre_periodo = '24 horas'
                elif periodicidad == '1h':
                    delta = timedelta(hours=1)
                    nombre_periodo = '1 hora'
                elif periodicidad == '30min':
                    delta = timedelta(minutes=30)
                    nombre_periodo = '30 minutos'
                else:
                    continue
            except Exception:
                continue

            # Combinar fecha y hora de la jornada
            try:
                fecha_hora_jornada = timezone.make_aware(
                    timezone.datetime.combine(jornada.fecha, jornada.hora),
                    timezone=timezone.get_current_timezone()
                )
            except Exception:
                continue

            # Calcular el momento en que se debe enviar el recordatorio
            momento_recordatorio = fecha_hora_jornada - delta

            # Si ya paso el momento del recordatorio, enviar si no se ha enviado
            if ahora >= momento_recordatorio:
                try:
                    mensaje = (
                        f"Hola {usuario.nombre},\n\n"
                        f"Este es un recordatorio: la jornada '{jornada.titulo}' "
                        f"comenzara en {nombre_periodo}.\n\n"
                        f"Detalles de la jornada:\n"
                        f"  Fecha: {jornada.fecha}\n"
                        f"  Hora: {jornada.hora}\n"
                        f"  Lugar: {jornada.direccion}, {jornada.barrio}\n"
                        f"  Tipo de material: {jornada.tipo_material}\n\n"
                        f"¡Te esperamos!\n"
                        f"Equipo Recicla Comuna 4"
                    )

                    # Enviar correo electronico
                    send_mail(
                        subject=f"🔔 Recordatorio: {jornada.titulo} en {nombre_periodo}",
                        message=mensaje,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[usuario.correo],
                        fail_silently=True,
                    )

                    # Crear notificacion en el sistema
                    Notificacion.objects.create(
                        usuario=usuario,
                        tipo="recordatorio",
                        mensaje=f"Recordatorio: '{jornada.titulo}' comienza en {nombre_periodo}."
                    )

                    # Marcar recordatorio como enviado
                    recordatorio.enviado = True
                    recordatorio.save()
                    recordatorios_enviados += 1

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Recordatorio enviado a {usuario.correo} para jornada '{jornada.titulo}' ({periodicidad})"
                        )
                    )
                except Exception as e:
                    recordatorios_error += 1
                    self.stderr.write(
                        self.style.ERROR(
                            f"Error enviando recordatorio a {usuario.correo}: {str(e)}"
                        )
                    )

        self.stdout.write(f"\nProceso completado. {recordatorios_enviados} recordatorios enviados, {recordatorios_error} errores.")