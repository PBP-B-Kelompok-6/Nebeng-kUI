from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView
from django.contrib import messages
from django.shortcuts import redirect
from .forms import RidePostForm
from .models import RidePost
from django.db.models import Count, Prefetch, Q
from reservasi.models import Reservasi
from django.http import JsonResponse


class FeedView(ListView):
    model = RidePost
    template_name = "forum/feed.html"
    context_object_name = "posts"

    def get_queryset(self):
        user = self.request.user
        mine = self.request.GET.get("mine") == "1" and user.is_authenticated

        if mine:
            # semua post milik sendiri, termasuk yang sudah penuh
            qs = RidePost.objects.filter(author=user)
        else:
            qs = RidePost.objects.filter(
                status=RidePost.Status.AKTIF, departure_time__gte=timezone.now()
            )

        qs = (
            qs.select_related("author")
            .annotate(
                pending_count=Count(
                    "reservations", filter=Q(reservations__status="MENUNGGU")
                )
            )
            .order_by("departure_time")
        )

        if user.is_authenticated:
            qs = qs.prefetch_related(
                Prefetch(
                    "reservations",
                    queryset=Reservasi.objects.filter(penumpang=user),
                    to_attr="my_res",
                )
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["mine"] = self.request.GET.get("mine") == "1"
        return ctx

class PostDetailView(DetailView):
    model = RidePost
    template_name = "forum/detail.html"
    context_object_name = "post"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        post = self.object
        if user.is_authenticated:
            if post.author == user:
                ctx["join_requests"] = post.reservations.select_related("penumpang")
            else:
                ctx["my_reservation"] = post.reservations.filter(penumpang=user).first()
        return ctx


class PostCreateView(LoginRequiredMixin, CreateView):
    model = RidePost
    form_class = RidePostForm
    template_name = "forum/post_form.html"
    success_url = reverse_lazy("forum:feed")

    # 1. VALIDASI: Cek kendaraan sebelum memproses request apapun
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.vehicles.exists():
            messages.error(request, "Kamu harus mendaftarkan kendaraan terlebih dahulu sebelum bisa menawarkan tumpangan.")
            return redirect("users:profile")  # Sesuaikan URL name ini dengan profilmu
        return super().dispatch(request, *args, **kwargs)

    # 2. INJEKSI USER: Kirim data user ke dalam form
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        form.instance.author = self.request.user
        
        # 2. Tarik data kendaraan yang dipilih dari form
        kendaraan_pilihan = form.cleaned_data['kendaraan']
        
        # 3. Salin kapasitas kendaraan ke max_quota milik postingan
        sisa_kursi_penumpang = kendaraan_pilihan.capacity - 1
        form.instance.max_quota = max(sisa_kursi_penumpang, 1)
        # Simpan ke database
        response = super().form_valid(form)

        # BACA AJAX: Jika request dari JS, kembalikan JSON
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success', 'message': 'Berhasil!'})
            
        return response
    
    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
        return super().form_invalid(form)


class PostDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = RidePost
    template_name = "forum/post_confirm_delete.html"
    success_url = reverse_lazy("forum:feed")

    def test_func(self):
        return self.get_object().author == self.request.user

    # Ganti perilaku standar saat menerima request POST (hapus)
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete() # Hapus dari database
        
        # BACA AJAX: Balas dengan JSON
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
            
        return redirect(self.get_success_url())