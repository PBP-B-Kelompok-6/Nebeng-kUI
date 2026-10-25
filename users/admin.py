from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from users.models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Data Mahasiswa', {
            'fields': ('npm', 'phone_number', 'faculty', 'bio',
                       'profile_picture', 'reward_points'),
        }),
    )
