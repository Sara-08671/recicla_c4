from django.urls import path
from . import views

urlpatterns = [
    #PRIMERA PAGINA
    path("", views.usuario_inicio, name="usuario_inicio"),
    
    # LOGIN / REGISTRO / SALIR
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),

    # PANEL PRINCIPAL POR ROL
    path("panel/admin/", views.admin_panel, name="admin_panel"),
    path("panel/residente/", views.residente_panel, name="residente_panel"),

    # ADMINISTRADOR
    path("admi/asistencia/", views.admi_asistencia, name="admi_asistencia"),
    path('admi/acciones/validar/', views.admi_validar_acciones, name='admi_validar_acciones'),
    path("admi/creacionjornadas/", views.admi_creacion_jornadas, name="admi_creacion_jornadas"),
    path("admi/foro/", views.admi_publicacion_foro, name="admi_publicacion_foro"),
    path("admi/recoleccion/", views.admi_recoleccion, name="admi_recoleccion"),
    path("admi/recompensa/", views.admi_recompensa, name="admi_recompensa"),
    path("admi/inicio/", views.admi_inicio, name="admi_inicio"),
    path('admi/solicitudes/', views.solicitudes_pendientes, name='solicitudes_pendientes'),
    path("admi/educacion/", views.admi_educacion, name="admi_educacion"),
    path("admi/contacto/", views.admi_contacto, name="admi_contacto"),
    path('admi/foro/publicaciones/', views.admi_foro_publicaciones, name='admi_foro_publicaciones'),
    path('admi/configuracion/', views.admi_configuracion, name='admi_configuracion'),
    path("admi/usuarios/", views.panel_usuarios, name="panel_usuarios"),
    path("admi/usuarios/agregar/", views.agregar_usuario, name="agregar_usuario"),
    path("admi/usuarios/editar/<int:id>/", views.editar_usuario, name="editar_usuario"),
    path("admi/usuarios/suspender/<int:id>/", views.suspender_usuario, name="suspender_usuario"),
    path('admin/usuarios/', views.admin_users_list, name='admin_users_list'),
    path('admin/usuarios/<int:id_usuario>/suspend/', views.admin_users_suspend, name='admin_users_suspend'),
    path('admin/usuarios/<int:id_usuario>/restore/', views.admin_users_restore, name='admin_users_restore'),
    path('admin/usuarios/deleted/', views.admin_users_deleted, name='admin_users_deleted'),
    path('admin/usuarios/export/xlsx/', views.admin_users_export_xlsx, name='admin_users_export_xlsx'),
    path('admin/usuarios/export/pdf/', views.admin_users_export_pdf, name='admin_users_export_pdf'),
    path('admin/usuarios/api/search/', views.admin_users_api_search, name='admin_users_api_search'),
    path('admi/usuarios/eliminar/<int:id_usuario>/', views.eliminar_usuario, name='eliminar_usuario'),
    path('admi/usuarios/reactivar/<int:id>/', views.reactivar_usuario, name='reactivar_usuario'),
    path('administrador/puntaje/asignar/', views.asignar_puntaje, name='asignar_puntaje'),
    path('admi/perfil/', views.perfil_admin, name='perfil_admin'),
    path('admi/perfil/cambiar-foto/', views.cambiar_foto_admin, name='cambiar_foto_admin'),
    path('admi/notificaciones/', views.admi_notificaciones, name='admi_notificaciones'),
    path('admi/jornadas/modificar/<int:jornada_id>/', views.admi_modificar_jornada, name='admi_modificar_jornada'),
    path('admi/jornadas/eliminar/<int:jornada_id>/', views.admi_eliminar_jornada, name='admi_eliminar_jornada'),

    # ORGANIZADOR
    path("organizador/asistencia/", views.organizador_asistencia, name="organizador_asistencia"),
    path("organizador/creacionjornadas/", views.organizador_creacion_jornadas, name="organizador_creacion_jornadas"),
    path("organizador/foro/", views.organizador_publicacion_foro, name="organizador_publicacion_foro"),
    path("organizador/recoleccion/", views.organizador_recoleccion, name="organizador_recoleccion"),
    path("organizador/recompensa/", views.organizador_recompensa, name="organizador_recompensa"),
    path("organizador/inicio/", views.organizador_inicio, name="organizador_inicio"),
    path("organizador/educacion/", views.organizador_educacion, name="organizador_educacion"),
    path("organizador/contacto/", views.organizador_contacto, name="organizador_contacto"),
    path('organizador/foro/publicaciones/', views.organizador_foro_publicaciones, name='organizador_foro_publicaciones'),
    path('organizador/configuracion/', views.organizador_configuracion, name='organizador_configuracion'),
    path('organizador/perfil/', views.perfil_organizador, name='perfil_organizador'),
    path('organizador/perfil/cambiar-foto/', views.cambiar_foto_organizador, name='cambiar_foto_organizador'),
    path('organizador/notificaciones/', views.organizador_notificaciones, name='organizador_notificaciones'),
    path('organizador/jornadas/modificar/<int:jornada_id>/', views.organizador_modificar_jornada, name='organizador_modificar_jornada'),
    path('organizador/jornadas/eliminar/<int:jornada_id>/', views.organizador_eliminar_jornada, name='organizador_eliminar_jornada'),

    # RESIDENTE
    path("residente/cat_recompensas/", views.residente_cat_recompensas, name="residente_cat_recompensas"),
    path("residente/como-participar/", views.residente_como_participar, name="residente_como_participar"),
    path("residente/inicio/", views.residente_inicio, name="residente_inicio"),
    path('usuarios/<int:id_usuario>/puntaje/admin/', views.historial_puntaje, name='historial_puntaje_admin'),
    path('residente/puntaje/', views.perfil_residente, name='perfil_residente'),
    path('residente/inscripcion/<int:id_jornada>/', views.residente_inscripcion, name='residente_inscripcion'),
    path("residente/recoleccion/", views.residente_recoleccion, name="residente_recoleccion"),
    path("residente/foro/", views.residente_publicacion_foro, name="residente_publicacion_foro"),
    path("residente/index/", views.residente_index, name="residente_index"),
    path("residente/educacion/", views.residente_educacion, name="residente_educacion"),
    path("residente/contacto/", views.residente_contacto, name="residente_contacto"),
    path('residente/foro/publicaciones/', views.residente_foro_publicaciones, name='residente_foro_publicaciones'),
    path('residente/configuracion/', views.residente_configuracion, name='residente_configuracion'),
    path('residente/cambiar-foto/', views.cambiar_foto, name='cambiar_foto'),
    path('residente/notificaciones/', views.residente_notificaciones, name='residente_notificaciones'),

    # USUARIO
    path("usuario/como-participar/", views.usuario_como_participar, name="usuario_como_participar"),
    path("usuario/educacion/", views.usuario_educacion, name="usuario_educacion"),
    path("usuario/contacto/", views.usuario_contacto, name="usuario_contacto"),
    path('usuario/jornadas/', views.residente_lista_jornadas, name='residente_lista_jornadas'),
    path("usuario/jornadas/<int:id_jornada>/ver/", views.residente_ver_jornada, name="residente_ver_jornada"),
    path('usuario/jornada/<int:jornada_id>/inscribirse/', views.inscribirse_jornada, name='inscribirse_jornada'),
    path('usuario/foro/publicaciones/', views.usuario_foro_publicaciones, name='usuario_foro_publicaciones'),

    # APROBACIÓN USUARIOS
    path("aprobar/<int:id_usuario>/", views.aprobar_usuario, name="aprobar_usuario"),
    path("rechazar/<int:id_usuario>/", views.rechazar_usuario, name="rechazar_usuario"),
    path("password_reset/", views.password_reset_request, name="password_reset_request"),
    path("reset_password/<str:token>/", views.password_reset_confirm, name="password_reset_confirm"),
    path("verify_email/<str:token>/", views.verify_email, name="verify_email"),

    # FORO - Acciones
    path('foro/reaccionar/<int:tema_id>/', views.foro_reaccionar, name='foro_reaccionar'),
    path('foro/comentar/<int:tema_id>/', views.foro_comentar, name='foro_comentar'),
    path('foro/denunciar/<int:tema_id>/', views.foro_denunciar, name='foro_denunciar'),
]