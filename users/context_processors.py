def co2_kalkulator(request):
    # Pastikan perhitungan hanya berjalan jika ada user yang login
    if request.user.is_authenticated:
        ride_count = request.user.reward_logs.count()
        
        # Menggunakan konstanta 0.5 kg per perjalanan (bisa kamu sesuaikan)
        total_co2 = ride_count * 0.5 
        co2_formatted = int(total_co2) if total_co2.is_integer() else round(total_co2, 1)
        
        return {'global_co2_saved': co2_formatted}
    
    # Jika belum login, kembalikan nilai 0
    return {'global_co2_saved': 0}