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
- API backend FastAPI untuk workflow otomatisasi dan integrasi eksternal
- login/register dan project per user
- preview dan export hasil ke folder workspace

## Stack
- Python 3.11+
- Streamlit
- FastAPI
- SQLite
- MoviePy
- Pillow
- FFmpeg
- OpenAI Whisper (opsional, untuk transkripsi otomatis)

## Persyaratan sistem
- Instal FFmpeg di sistem operasi Anda sebelum menjalankan aplikasi.
- Untuk transkripsi otomatis, install `openai-whisper` dari `requirements.txt`.

## Struktur proyek
- `app.py` – antarmuka aplikasi Streamlit
- `api.py` – backend API FastAPI untuk proses otomatisasi dan integrasi
- `auth.py` – fungsi autentikasi dan register user
- `db.py` – database SQLite untuk user, project, dan jobs
- `src/video_pipeline.py` – pipeline utama pemrosesan video, deteksi momen, thumbnail, dan copywriting
- `uploads/` – penyimpanan file input
- `workspace/` – hasil output video, transcript, subtitle, thumbnail, metadata, dan database aplikasi

## Cara menjalankan

Streamlit frontend:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

API backend:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api:app --host 0.0.0.0 --port 8000
```

Testing:
```bash
pytest -q
```

## Endpoint API

- `GET /health` – cek status service
- `POST /register` – register user baru
- `POST /login` – login user
- `GET /projects` – ambil project user
- `POST /projects` – buat project baru
- `POST /process` – upload video dan dapatkan hasil processing
- `GET /jobs` – daftar history pekerjaan user
- `GET /jobs/{job_id}` – detail job berdasarkan ID
- `GET /jobs/{job_id}/download` – download hasil pekerjaan dalam format zip

Contoh request:
```bash
curl -X POST "http://localhost:8000/process" \
  -F "username=demo" \
  -F "password=secret" \
  -F "project_id=1" \
  -F "file=@video.mp4" \
  -F "max_clips=3" \
  -F "clip_duration=30" \
  -F "target_platform=TikTok"
```

## Flow kerja
1. Register/login ke aplikasi
2. Buat project atau pilih project aktif
3. Upload video panjang
4. Sistem mengekstrak audio dan mentranskripsikan isi video
5. Momen paling penting dideteksi berdasarkan kata kunci, durasi, dan energi audio
6. Video dipotong menjadi klip terbaik sesuai jumlah yang diinginkan
7. Setiap klip dibuat dengan subtitle, hook, caption, tagar, dan thumbnail multi-variant
8. Hasil file disimpan di folder `workspace`
9. Riwayat proses serta export zip dapat diakses dari dashboard atau API

## Catatan
Versi ini adalah tahap 7 dari pengembangan, fokus pada kesiapan deployment: testing API, struktur user/project, dokumentasi yang lebih lengkap, serta workflow yang lebih stabil untuk penggunaan nyata.
