from rest_framework.authentication import SessionAuthentication


class MobileSessionAuthentication(SessionAuthentication):
    """
    SessionAuthentication tanpa pengecekan CSRF, khusus untuk klien mobile.

    Aplikasi Flutter (pbp_django_auth) menyimpan cookie sesi tetapi tidak
    punya token CSRF, jadi POST/PATCH/DELETE dengan SessionAuthentication
    biasa akan selalu 403. Form HTML di situs web tetap dilindungi
    CsrfViewMiddleware seperti biasa.
    """

    def enforce_csrf(self, request):
        return None