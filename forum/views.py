from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView

from .forms import RidePostForm
from .models import RidePost


class FeedView(ListView):
    model = RidePost
    template_name = "forum/feed.html"
    context_object_name = "posts"

    def get_queryset(self):
        qs = RidePost.objects.filter(
            status=RidePost.Status.AKTIF, departure_time__gte=timezone.now()
        ).select_related("author")
        tipe = self.request.GET.get("tipe")
        if tipe in ("cari", "beri"):
            qs = qs.filter(post_type=tipe)
        return qs


class PostDetailView(DetailView):
    model = RidePost
    template_name = "forum/detail.html"
    context_object_name = "post"


class PostCreateView(LoginRequiredMixin, CreateView):
    model = RidePost
    form_class = RidePostForm
    template_name = "forum/post_form.html"
    success_url = reverse_lazy("forum:feed")

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)


class PostDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = RidePost
    template_name = "forum/post_confirm_delete.html"
    success_url = reverse_lazy("forum:feed")

    def test_func(self):
        return self.get_object().author == self.request.user