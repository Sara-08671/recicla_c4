from django import forms
from .models import Jornada
from .models import Inscripcion
from django import forms
from .models import Usuario
from django.contrib.auth.hashers import make_password
from .models import Puntaje
from .models import Notificacion


class JornadaForm(forms.ModelForm):
    class Meta:
        model = Jornada
        fields = ['titulo', 'descripcion', 'fecha', 'hora', 'direccion', 'barrio', 'tipo_material', 'cupo_maximo', 'estado']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'hora': forms.TimeInput(attrs={'type': 'time'}),
        }

class InscripcionForm(forms.ModelForm):
    class Meta:
        model = Inscripcion
        fields = ['usuario', 'jornada']  # ← QUITAMOS estado
        widgets = {
            'usuario': forms.HiddenInput(),
            'jornada': forms.HiddenInput(),
        }

# core/forms.py
class UsuarioForm(forms.ModelForm):
    password_plain = forms.CharField(
        label="Contraseña (si quieres cambiarla)",
        required=False,
        widget=forms.PasswordInput(render_value=False)
    )

    class Meta:
        model = Usuario
        fields = [
            'nombre',
            'apellido',
            'correo',
            'fecha_nacimiento',
            'barrio',
            'rol',
            'estado',
            'foto'   # 👈 AGREGAR ESTE CAMPO
        ]

    def save(self, commit=True):
        instance = super().save(commit=False)
        pwd = self.cleaned_data.get('password_plain')
        if pwd:
            instance.contrasena = make_password(pwd)
        if commit:
            instance.save()
        return instance

    
class PuntajeForm(forms.ModelForm):
    class Meta:
        model = Puntaje
        exclude = ['fecha']
class AsignarPuntajeForm(forms.ModelForm):
    class Meta:
        model = Puntaje
        fields = ['puntos']
        
class PasswordResetRequestForm(forms.Form):
    correo = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "Ingresa tu correo"})
    )

class NotificacionForm(forms.ModelForm):
    usuario = forms.ModelChoiceField(
        queryset=Usuario.objects.all(),
        label="Enviar a:",
        widget=forms.Select(attrs={"class": "form-control"})
    )

    class Meta:
        model = Notificacion
        fields = ["usuario", "tipo", "mensaje"]
        widgets = {
            "tipo": forms.TextInput(attrs={"class": "form-control"}),
            "mensaje": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }