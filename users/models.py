from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
class User(AbstractUser):
    email = models.EmailField(unique=True)
    npm = models.CharField(max_length=10, blank=True)
    phone_number = models.CharField(max_length=16, blank=True)
    faculty = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    profile_picture = models.URLField(blank=True)
    reward_points = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.username

    @property
    def is_driver(self):
        #  buat nanti ada vehicle
        return self.vehicles.exists()

    def add_reward_points(self, amount):
        self.reward_points += amount
        self.save()