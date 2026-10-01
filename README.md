# Video Clipper Automation

Aplikasi otomatis untuk memotong video panjang menjadi beberapa klip singkat yang siap dipublish di platform seperti TikTok, Reels, Shorts, YouTube, dan LinkedIn.

Fitur utama:
- upload video panjang
- analisis otomatis momen penting dari transcript dan audio
- pemotongan otomatis menjadi beberapa klip terbaik
- transkripsi audio otomatis
- pembuatan subtitle otomatis
- pembuatan hook, caption, dan tagar berdasarkan teks penting
- preview thumbnail untuk setiap klip
- export hasil ke folder workspace

## Stack
- Python 3.11+
- Streamlit
- MoviePy
- FFmpeg
- OpenAI Whisper (opsional, untuk transkripsi otomatis)

## Persyaratan sistem
- Instal FFmpeg di sistem operasi Anda sebelum menjalankan aplikasi.
- Untuk transkripsi otomatis, install `openai-whisper` dari `requirements.txt`.

## Struktur proyek
- `app.py` – antarmuka aplikasi
- `src/video_pipeline.py` – pipeline utama pemrosesan video dan deteksi momen penting
- `uploads/` – penyimpanan file input
- `workspace/` – hasil output video, transcript, subtitle, thumbnail, dan metadata

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
5. Setiap klip dibuat dengan subtitle, hook, caption, dan tagar
6. Hasil file disimpan di folder `workspace`

## Catatan
Versi ini adalah tahap 3 dari pengembangan, fokus pada deteksi momen penting otomatis agar hasil clipping lebih relevan dan siap publikasi dibanding pemotongan rata-rata. Pengembangan berikutnya dapat menambahkan generasi thumbnail visual, summary AI, dan ekspor batch untuk platform tertentu.
