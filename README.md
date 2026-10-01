# Video Clipper Automation

Aplikasi otomatis untuk memotong video panjang menjadi beberapa klip singkat yang siap dipublish di platform seperti TikTok, Reels, Shorts, YouTube, dan LinkedIn.

Fitur utama:
- upload video panjang
- analisis otomatis momen penting dari transcript dan audio
- pemotongan otomatis menjadi beberapa klip terbaik
- transkripsi audio otomatis
- pembuatan subtitle otomatis
- pembuatan hook, caption, dan tagar berdasarkan teks penting
- generator thumbnail multi-variant untuk setiap klip
- riwayat proses dan export zip hasil
- preview dan export hasil ke folder workspace

## Stack
- Python 3.11+
- Streamlit
- MoviePy
- Pillow
- FFmpeg
- OpenAI Whisper (opsional, untuk transkripsi otomatis)

## Persyaratan sistem
- Instal FFmpeg di sistem operasi Anda sebelum menjalankan aplikasi.
- Untuk transkripsi otomatis, install `openai-whisper` dari `requirements.txt`.

## Struktur proyek
- `app.py` – antarmuka aplikasi
- `src/video_pipeline.py` – pipeline utama pemrosesan video, deteksi momen, thumbnail, dan copywriting
- `uploads/` – penyimpanan file input
- `workspace/` – hasil output video, transcript, subtitle, thumbnail, metadata, dan riwayat proses

## Cara menjalankan
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Flow kerja
1. Upload video panjang
2. Sistem mengekstrak audio dan mentranskripsikan isi video
3. Momen paling penting dideteksi berdasarkan kata kunci, durasi, dan energi audio
4. Video dipotong menjadi klip terbaik sesuai jumlah yang diinginkan
5. Setiap klip dibuat dengan subtitle, hook, caption, tagar, dan thumbnail multi-variant
6. Hasil file disimpan di folder `workspace`
7. Riwayat proses serta export zip dapat diakses dari dashboard aplikasi

## Catatan
Versi ini adalah tahap 5 dari pengembangan, fokus pada workflow yang lebih siap dipakai: proses berulang, riwayat job, serta export hasil untuk kebutuhan publikasi atau pengiriman ke tim.
