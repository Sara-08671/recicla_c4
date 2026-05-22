from django.contrib import admin
from .models import Recordatorio

# Register your models here.

@admin.register(Recordatorio)
class RecordatorioAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'jornada', 'periodicidad', 'activo', 'enviado', 'fecha_creacion')
    list_filter = ('activo', 'enviado', 'periodicidad')
    search_fields = ('usuario__nombre', 'usuario__apellido', 'jornada__titulo')
