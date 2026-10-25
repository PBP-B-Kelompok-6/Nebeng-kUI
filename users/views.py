import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from users.forms import RegisterForm


def register_user(request):
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Akun berhasil dibuat. Silakan login.")
        return redirect("users:login")
    return render(request, "users/register.html", {"form": form})


def login_user(request):
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())

        next_url = request.POST.get("next", "")
        if not url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            next_url = settings.LOGIN_REDIRECT_URL

        response = redirect(next_url)
        response.set_cookie(
            "last_login",
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        return response
    return render(request, "users/login.html", {
        "form": form,
        "next": request.GET.get("next", ""),
    })


@require_POST
def logout_user(request):
    logout(request)
    response = redirect(settings.LOGOUT_REDIRECT_URL)
    response.delete_cookie("last_login")
    return response