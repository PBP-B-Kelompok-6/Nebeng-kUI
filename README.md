# Nebeng-kUI

## Deskripsi Aplikasi
Nebeng-kUI adalah aplikasi ride-sharing atau berbagi tebengan khusus untuk mahasiswa di lingkungan kampus. Aplikasi ini memungkinkan pengguna untuk saling menawarkan atau mencari tumpangan saat berangkat dan pulang kampus. Untuk mendorong partisipasi aktif, aplikasi ini dilengkapi dengan sistem reward bagi pengguna yang memberikan tumpangan.

Manfaat aplikasi ini bagi masyarakat (khususnya sivitas akademika) adalah membantu mahasiswa menghemat biaya transportasi, mengurangi kesulitan mencari slot parkir di dalam kampus, serta berkontribusi langsung dalam menurunkan emisi karbon dengan mengurangi jumlah penggunaan kendaraan pribadi secara individu.

   Tema Proyek: Sustainable Living
   Sub-tema: Clean Energy & Carbon Footprint

## Peran dan Target Pengguna
Target Pengguna: Mahasiswa UI yang membawa kendaraan pribadi dan mahasiswa yang membutuhkan tumpangan.

Peran Pengguna:
1.  Pemberi Tebengan (Driver): Pengguna yang membawa kendaraan pribadi (motor/mobil) dan memiliki kursi kosong untuk ditawarkan kepada mahasiswa lain.
2.  Pencari Tebengan (Passenger): Pengguna yang membutuhkan tumpangan menuju atau dari kampus.
#Catatan : Setiap user bisa menjadi kedua role tersebu

## Anggota Kelompok
1. Fadlan Fathul Islam / 2506601275
2. Muhammad Ridho Anwar / 2506595745
3. Andrew Chandra Halim / 2506656431
4. Vincent Armando / 2506618540

##  Daftar Modul dan Pembagian Kerja

1. Modul Profil, Kendaraan & Reward (User Management) - [Andrew]
   Deskripsi: Mengelola profil pengguna, pendataan kendaraan, serta sistem reward (poin emisi) bagi pemberi tumpangan.
   CRUD:
       Create: Menambahkan data kendaraan (motor/mobil, pelat nomor, kapasitas).
       Read: Menampilkan halaman profil, daftar kendaraan, dan jumlah poin reward yang telah dikumpulkan oleh driver.
       Update: Mengedit detail profil/kendaraan, dan Update poin reward secara otomatis setiap kali driver berhasil menyelesaikan tebengan.
       Delete: Menghapus data kendaraan jika sudah tidak digunakan.

2. Modul Forum Tebengan (Social Media Feed) - [Vincent]
   Deskripsi: Mengelola sistem feed/postingan ala media sosial untuk mencari atau menawarkan tebengan.
   CRUD:
       Create: Membuat post baru ("Mencari Tebengan" atau "Memberi Tebengan") beserta titik kumpul, tujuan, dan batas kuota maksimal.
       Read: Menampilkan daftar postingan tebengan yang masih aktif di halaman utama forum.
       Update: Sistem secara otomatis mengubah status post menjadi "Penuh" dan menyembunyikannya dari feed jika kuota sudah tercapai.
       Delete: Menghapus postingan tebengan milik sendiri.

3. Modul Reservasi & Obrolan (Booking & Chat) - [Fadlan]
   Deskripsi: Menangani pemesanan tebengan dan komunikasi janjian antar mahasiswa.
   CRUD:
       Create: Membuat data reservasi baru saat menekan tombol "Join" pada sebuah post, serta mengirim pesan obrolan.
       Read: Menampilkan halaman kotak masuk (Inbox) dan riwayat pesan dengan pemberi/penerima tebengan.
       Update: Memperbarui status reservasi (Diterima/Ditolak/Selesai).
       Delete: Membatalkan reservasi dan menghapus riwayat pesan chat.

4. Modul Peta & Titik Kumpul (API & Pick-up Points) - [Ridho]
   Deskripsi: Mengintegrasikan peta untuk menemukan, menampilkan, dan menyimpan lokasi strategis penjemputan (halte, gerbang kampus, area kosan).
   CRUD:
       Create: Menyimpan (menyematkan) titik kumpul kustom/favorit ke dalam akun pribadi pengguna.
       Read: Menampilkan titik koordinat dan informasi halte/fasilitas sekitar yang diambil dari OpenStreetMap API ke dalam peta interaktif.
       Update: Mengedit catatan khusus pada titik kumpul favorit (contoh: "Tunggu di dekat pos satpam gerbang Kutek").
       Delete: Menghapus titik kumpul dari daftar favorit pengguna.

##  Penggunaan Public API dan Initial Data
   Public API yang digunakan: [OpenStreetMap API (Overpass)](https://wiki.openstreetmap.org/wiki/Overpass_API). API ini gratis dan bisa dipakai untuk menampilkan koordinat spesifik area kampus, halte, dan titik kumpul di sekitar Depok .
   Initial Data: Proyek ini akan di-seed dengan 50 data awal yang berisi daftar titik lokasi kumpul strategis (seperti halte bis kuning, stasiun KRL, gerbang fakultas, dan area kos).

##  Tautan Penting
   * Tautan Deployment (PWS): https://vincent-armando-nebengkui.pws.cs.ui.ac.id/
   * Tautan Desain UI/Wireframe (Figma): https://www.figma.com/design/NBWjUCqdKOdoI8wgXfTb5E/Nebeng-kUI?node-id=0-1&t=calHUAJZhuKMqxEM-1
   * Tautan System Design: https://drive.google.com/file/d/1eBAYazG7ObP_Oq-u8arAwh9j7H5QoSvr/view?usp=sharing