# Video Clipper Automation

Aplikasi otomatis untuk mengubah video panjang menjadi beberapa klip yang lebih pendek, siap diproses menjadi konten untuk platform seperti TikTok, Reels, Shorts, YouTube, dan LinkedIn.

Fitur utama:
- upload video panjang
- segmentasi otomatis berdasarkan momen penting
- pembuatan subtitle otomatis
- konversi teks jadi hook, caption, dan tagar
- pembuatan thumbnail concept
- ekspor hasil siap publish

## Stack yang digunakan
- Python
- Streamlit
- MoviePy
- Whisper (opsional untuk transkripsi otomatis)
- FFmpeg

## Struktur proyek
- `app.py` – antarmuka aplikasi
- `src/video_pipeline.py` – pipeline utama pengolahan video
- `requirements.txt` – dependency
- `workspace/` – tempat hasil proses

## Cara menjalankan
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Flow kerja
1. Upload video panjang
2. Sistem memotong video ke beberapa bagian yang paling menarik
3. Auto-generate teks, subtitle, caption, tagar, dan hook
4. Hasil disimpan di folder workspace

## Catatan
Versi awal ini fokus pada MVP: otomatisasi proses dasar dan template konten siap pakai untuk pemasaran digital.
