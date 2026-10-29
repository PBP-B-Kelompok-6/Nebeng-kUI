from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from users.models import Redemption, User, RewardLog



@admin.register(User)
class CustomUserAdmin(UserAdmin):
    readonly_fields = ("reward_points", "balance")
    fieldsets = UserAdmin.fieldsets + (
        ('Data Mahasiswa', {
            'fields': ('npm', 'phone_number', 'faculty', 'bio',
                       'profile_picture', 'reward_points', 'balance'),
        }),
    )

@admin.register(Redemption)
class RedemptionAdmin(admin.ModelAdmin):
    list_display = ("user", "points", "amount_rupiah", "created_at")
    search_fields = ("user__username",)
    readonly_fields = ("user", "points", "amount_rupiah", "status", "created_at")

    def has_add_permission(self, request):
        return False

@admin.register(RewardLog)
class RewardLogAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "reason", "reference", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "reason", "reference")