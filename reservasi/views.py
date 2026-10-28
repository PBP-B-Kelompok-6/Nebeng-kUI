from django.shortcuts import render

# Create your views here.
def show_reservasi(request):
    return render(request, 'reservasi/chat.html')
