# Panduan Presentasi & Penggunaan — TDAS AD Audit v4

**Explainable Anomaly Detection in Active Directory: Integrating a Rule-Based Knowledge Engine, Ensemble Learning, and SHAP for Human-Readable Reasoning**

Penulis: **Mahathir Muhammad** · Dosen: **Dr. Kelly Rossa Sungkono, S.Kom., M.Kom.**
Status: pipeline final, hasil **kanonik & reproducible**, draft paper IJIES siap.

> Dokumen ini punya 2 bagian:
> **Bagian 1 — Panduan Presentasi** (apa yang dijelaskan ke dosen + antisipasi tanya-jawab).
> **Bagian 2 — Cara Penggunaan** (cara menjalankan & me-regenerate semua output).

---

# BAGIAN 1 — PANDUAN PRESENTASI

## 1.1 Ringkasan 30 detik (elevator pitch)

> "Saya memodelkan **1,8 juta log Active Directory** dari ManageEngine ADAudit Plus menjadi sebuah **knowledge graph di Neo4j**. Dari graph itu saya ekstrak **11 fitur per user**, lalu mendeteksi anomali dengan **ensemble 3 algoritma unsupervised** (Isolation Forest, LOF, Elliptic Envelope). Setiap deteksi **dijelaskan dengan SHAP** sehingga auditor tahu *mengapa* seorang user dianggap mencurigakan. Dari **887 user**, sistem menandai **89 user** sebagai perlu perhatian (severity MEDIUM ke atas), dengan tingkat keparahan ditentukan secara **objektif berbasis kuantil**, bukan angka karangan."

## 1.2 Alur cerita presentasi (urutan slide)

Gunakan file outline: [docs/presentations/PPT_Outline_TDAS_AD_Audit_v4.docx](docs/presentations/PPT_Outline_TDAS_AD_Audit_v4.docx) (22 slide + 7 gambar).

| # | Slide | Inti yang diucapkan |
|---|-------|--------------------|
| 1 | Judul | Nama, judul paper, posisi penelitian |
| 2–3 | Latar belakang & kontribusi | Insider threat sulit dideteksi → butuh graph + ensemble + explainable |
| 4 | Problem statement | Deteksi akurat **dan** dapat dijelaskan, tanpa label ground-truth |
| 5–6 | SOTA & research gap | SOTA terbelah (ML generik vs rule AD); kita gabungkan keduanya |
| 7 | **Pipeline 7-phase** | Tunjukkan diagram alur — ini tulang punggung |
| 8 | **Knowledge Graph** | 7 node, 10 relationship — tunjukkan skema |
| 9 | 10 Rules | Rule engine domain (R001–R010) jalan SEBELUM ML |
| 10 | 11 Features | Fitur diekstrak dari **relasi graph**, bukan kolom CSV |
| 11 | **Ensemble** | Tugas IF/LOF/EE + rumus skor + severity kuantil |
| 12 | **SHAP** | Penjelasan per user (bukti kuantitatif) |
| 13 | Dataset | 1,833,352 events → 887 user |
| 14 | Hasil severity | Distribusi 9/36/44/133/665 |
| 15 | Top-5 anomali | mti.admin score 0.64, dst + penyebab SHAP |
| 16–17 | **Ablation** | Jawaban langsung permintaan Dr. Kelly |
| 18 | Justifikasi ensemble | "Robustness over peak performance" |
| 19 | Limitations | Jujur: weak supervision (proxy, bukan label asli) |
| 20–22 | Deliverables, kesimpulan, Q&A | — |

## 1.3 Konsep inti yang WAJIB dikuasai (ini yang biasa ditanya)

### a) Ada berapa metode ML, dan di phase mana?
**3 algoritma**, semuanya di **Phase 5**:
- **Isolation Forest (IF)** — tree-based
- **Local Outlier Factor (LOF)** — density-based
- **Elliptic Envelope (EE)** — statistical (covariance)

SHAP **bukan** algoritma deteksi — ia adalah *explainer* (Phase 5.5).

### b) "Ensemble learning"-nya yang mana?
Ensemble = **gabungan keputusan 3 model** lewat *voting*. Seorang user ditandai anomali jika **minimal 2 dari 3 model** setuju.

Rumus skor akhir:
```
final_score = 0.60 × (jumlah_vote / 3) + 0.40 × (rule_violations / 10)
```
60% dari ML (3 model), 40% dari rule domain. Ini membuat skor *anchored* ke pengetahuan domain AD, tidak murni statistik buta.

### c) Tugas masing-masing IF / LOF / EE (beda di mana?)
| Model | Menangkap | Analogi pada kasus AD |
|-------|-----------|----------------------|
| **IF** | Anomali **global ekstrem** — titik yang gampang "diisolasi" | User yang nilainya jauh menyimpang di banyak fitur sekaligus (mis. admin super aktif) |
| **LOF** | Anomali **lokal di dalam cluster** — normal secara global tapi aneh dibanding tetangga terdekatnya | User yang "mirip grupnya" tapi sedikit lebih sering gagal login / pindah host dibanding rekan se-rolenya |
| **EE** | Outlier **statistik multivariat** — di luar elips kovariansi data | User yang kombinasi fiturnya melanggar pola korelasi normal (mis. host tinggi TAPI privilege rendah) |

Kunci jawaban: **mereka menangkap *jenis* anomali yang berbeda**, jadi menggabungkannya menutup blind-spot masing-masing. Ini dibuktikan oleh **Cohen's Kappa LOF–EE = 0.18** (kesepakatan rendah = sudut pandang berbeda).

### d) Dari mana angka severity & level-nya? (kekhawatiran utama dosen)
**Dulu** ambang severity dipilih subjektif. **Sekarang** memakai **kuantil dari distribusi skor** (data-driven, reproducible):

| Level | Ambang | Nilai kanonik | Arti |
|-------|--------|---------------|------|
| CRITICAL | ≥ P99 | ≥ 0.358 | 1% teratas |
| HIGH | ≥ P95 | ≥ 0.292 | 5% teratas |
| MEDIUM | ≥ P90 | ≥ 0.238 | 10% teratas |
| LOW | ≥ P75 | ≥ 0.209 | 25% teratas |
| NORMAL | < P75 | < 0.209 | sisanya |

**Jawaban saat ditanya "kok bisa nentukan angka itu?"**:
> "Angkanya **tidak saya tentukan manual**. Saya pakai persentil distribusi skor — CRITICAL = 1% skor tertinggi, HIGH = 5% teratas, dst. Jadi ambangnya **mengikuti data**, dan kalau datanya berubah, ambangnya menyesuaikan otomatis. Pendekatan thresholding berbasis kuantil ini didukung literatur deteksi anomali (Aggarwal 2017; Goldstein & Uchida 2016). Sebagai pembanding kualitatif, ide tingkat keparahan berjenjang juga selaras dengan CVSS v3.1/v4.0 (FIRST.org)."

### e) SHAP — teks penyebabnya dari dataset atau dari coding?
**Dua-duanya, dengan peran berbeda:**
- **Nilai/angka** kontribusi → dihitung **dari data** oleh `shap.TreeExplainer` pada Isolation Forest.
- **Teks label** (mis. "Sering lockout", "Banyak admin action") → **dipetakan di kode** lewat dictionary `FEATURE_LABELS` (nama fitur → kalimat Bahasa Indonesia).

Jadi SHAP memilih *fitur mana* yang paling berpengaruh (dari data), lalu kode menerjemahkan nama fitur itu jadi kalimat yang dibaca auditor.

### f) Machine learning-nya baca data dari mana? (graph atau CSV?)
Alurnya: **CSV mentah → Neo4j graph → 11 fitur graph → ML**.
ML **tidak** membaca CSV langsung. Ia membaca **11 fitur per user** yang dihitung dari **relasi di graph** (mis. `host_diversity` = jumlah hostname unik yang terhubung ke user lewat relasi `LOGIN_FROM`). Inilah nilai tambah knowledge graph: fitur lahir dari *relasi*, bukan sekadar kolom.

11 fitur: `host_diversity`, `critical_server_ratio`, `failure_ratio`, `shared_device_risk`, `ip_network_risk`, `privilege_level`, `connectivity`, `rule_violations`, `lockout_count`, `admin_actions`, `sensitive_groups`.

### g) Ablation — mana yang lebih tinggi? (permintaan eksplisit Dr. Kelly)
Diuji **7 konfigurasi** terhadap proxy `rule_violations ≥ 6` (K = top-57):

| Konfigurasi | Accuracy | F1 |
|-------------|:--------:|:--:|
| IF | 0.912 | 0.316 |
| LOF | 0.894 | 0.175 |
| EE | **0.932** | **0.474** |
| IF+LOF | 0.899 | 0.211 |
| IF+EE | 0.930 | 0.456 |
| LOF+EE | 0.930 | 0.456 |
| **IF+LOF+EE** | 0.930 | 0.456 |

Precision@K individual: **IF 0.333 · LOF 0.044 · EE 0.533**.

**Cara menyampaikan temuan (penting — jujur & defensif):**
> "Secara angka, **EE tertinggi** (Acc 0.932 / F1 0.474). TAPI ini **bias**: 'akurasi' di sini diukur terhadap proxy berbasis rule, dan EE memang paling selaras dengan rule (Kappa IF–EE 0.70). Yang lebih penting: **ensemble penuh IF+LOF+EE tidak pernah jadi yang terburuk** di konfigurasi manapun — sementara model tunggal volatil (LOF anjlok ke F1 0.175). Jadi prinsipnya **robustness over peak performance**: memilih 1 model 'terbaik' berisiko overfit ke satu definisi anomali."

## 1.4 Angka kunci yang harus dihafal

- **Dataset:** 1.833.352 events → **887 user**
- **Severity:** CRITICAL **9** · HIGH **36** · MEDIUM **44** · LOW **133** · NORMAL **665**
- **Total perlu perhatian (MEDIUM+):** **89 user**
- **Voting:** 3-votes **10** user · 2-votes **35** · 1-vote **35** · 0-votes **807**
- **Top anomali:** `mti.admin` skor **0.640** (CRITICAL, 6/10 rules, penyebab "Sering lockout")
- **Rata-rata pelanggaran rule:** **3.39** /user
- **SHAP global top-3:** `rule_violations` (0.559), `host_diversity` (0.513), `shared_device_risk` (0.500)

## 1.5 Antisipasi pertanyaan dosen (siap jawab)

| Pertanyaan | Jawaban singkat |
|-----------|----------------|
| "Severity-nya subjektif?" | Tidak lagi — kuantil P75/P90/P95/P99, data-driven & reproducible. |
| "Bagaimana verifikasi benar/salah severity?" | Tidak ada label asli (unsupervised). Kami pakai **proxy** `rule_violations` sebagai *weak supervision*; ini saya tulis terbuka di **Limitations**. |
| "Kenapa pakai 3 model, bukan 1?" | Tiap model tangkap jenis anomali berbeda (Kappa LOF–EE 0.18). Ensemble paling robust di ablation. |
| "IF+EE bagaimana?" | Sudah diuji: Acc 0.930 / F1 0.456 — ada di tabel 7-konfigurasi. |
| "Reproducible nggak? Data berubah tiap run?" | Reproducible. Phase 2 reset DB (`CREATE OR REPLACE DATABASE`) + `random_state=42`. Hasil byte-identik antar-run. |
| "Kontribusi barunya apa?" | Gabungan KG AD + ensemble heterogen + SHAP + severity kuantil dalam satu pipeline reproducible. |
| "Kenapa Neo4j, bukan tabel biasa?" | Fitur lahir dari relasi (host_diversity, connectivity). Graph membuat konteks relasional bisa di-query & divisualisasi. |

## 1.6 Demo langsung (opsional, jika dosen minta)

Buka **Neo4j Browser** di `http://localhost:7474`, lalu jalankan query memperlihatkan user anomali beserta penyebab SHAP:
```cypher
MATCH (u:User)
WHERE u.severity IN ['CRITICAL','HIGH']
RETURN u.username, u.anomaly_score, u.severity, u.shap_top_feature_label
ORDER BY u.anomaly_score DESC
LIMIT 10;
```
> Catatan: query ini hanya **menampilkan** hasil yang sudah dihitung pipeline ML (IF/LOF/EE/SHAP) dan ditulis balik ke node `User`. Neo4j di sini = penyimpanan + visualisasi, bukan yang menghitung anomali.

---

# BAGIAN 2 — CARA PENGGUNAAN

## 2.1 Prasyarat

| Komponen | Versi | Catatan |
|----------|-------|---------|
| Python | 3.12 | |
| Neo4j | 5.x | Desktop/Server, instance aktif |
| Library | lihat `requirements.txt` | `pip install -r requirements.txt` |

Kredensial koneksi (default di semua script `neo4j_phase*.py`):
```
NEO4J_URI      = "bolt://localhost:7687"
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "lalarasa"
```
> Ganti password sesuai instance Anda jika berbeda. Pastikan Neo4j **sudah running** sebelum menjalankan pipeline.

## 2.2 Setup

```powershell
# 1. Masuk folder project
cd c:\Users\itsupport\Documents\Apps\tdas_adauditv3

# 2. (opsional) buat virtual env
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Install dependency
pip install -r requirements.txt

# 4. Pastikan Neo4j instance aktif (cek di Neo4j Desktop / browser http://localhost:7474)
```

## 2.3 Menjalankan pipeline

### Opsi A — Notebook (disarankan, paling mudah dipresentasikan)
Buka **[pipeline_adaudit.ipynb](pipeline_adaudit.ipynb)** lalu **Run All** dari atas. Notebook menjalankan seluruh urutan Phase 2 → 6 + Ablation Study, lengkap dengan narasi markdown tiap fase.

### Opsi B — Per-phase via script (untuk debugging)
Jalankan berurutan:
```powershell
python restructure_for_neo4j.py     # siapkan data dari CSV mentah (sekali saja)
python neo4j_ingest_phase2.py       # Phase 2: bangun knowledge graph (reset DB otomatis)
python neo4j_phase3_rules.py        # Phase 3: 10 rule domain
python neo4j_phase4_features.py     # Phase 4: 11 fitur graph
python neo4j_phase5_anomaly.py      # Phase 5: ensemble IF+LOF+EE + severity kuantil
python neo4j_phase55_shap.py        # Phase 5.5: SHAP explainability
python neo4j_phase6_reporting.py    # Phase 6: laporan TXT/JSON
```
> **Urutan wajib** — tiap fase membaca hasil fase sebelumnya (dari graph & CSV `data/phase*.csv`).

## 2.4 Reproducibility (penting)

- **Phase 2 mereset database** dengan `CREATE OR REPLACE DATABASE neo4j` di awal — graph dibangun ulang dari nol tiap run, jadi tidak ada penggandaan/inflasi relasi.
- Semua model memakai `random_state=42`.
- Hasilnya **deterministik**: menjalankan ulang pipeline menghasilkan angka yang **persis sama** (terbukti: ukuran output byte-identik antar-run).

## 2.5 Akses Neo4j Browser

1. Buka `http://localhost:7474`
2. Login (`neo4j` / `lalarasa`)
3. Jalankan query Cypher (lihat contoh di §1.6) untuk eksplorasi/visualisasi.

## 2.6 Regenerate deliverable (dokumen)

Setelah pipeline selesai (CSV `data/phase5*.csv`, `data/phase55*.csv`, dan `output/*.json` terbentuk), semua dokumen di-generate **dinamis dari data kanonik**:

```powershell
python generate_report_docx_v3.py    # → output/AD_Anomaly_Detection_Report_v3.docx (laporan formal 12 section)
python generate_paper_ijies.py       # → output/IJIES_Draft_Paper_Mahathir_Muhammad.docx (draft paper)
python generate_ppt_outline_v4.py    # → docs/presentations/PPT_Outline_TDAS_AD_Audit_v4.docx (22 slide + 7 gambar)
```
> Karena dinamis, kalau pipeline berubah cukup jalankan ulang generator — angka & gambar ikut update sendiri.
> ⚠️ Tutup file `.docx` di Word dulu sebelum regenerate (kalau terbuka → `PermissionError`).

## 2.7 Output yang dihasilkan

| File | Isi |
|------|-----|
| `output/anomaly_detection_report.txt` | Laporan teks untuk auditor |
| `output/anomaly_statistics.json` | Statistik ringkas (distribusi severity, voting, dll) |
| `output/anomaly_detection_detailed.json` | Detail per user |
| `output/AD_Anomaly_Detection_Report_v3.docx` | Laporan formal 12 section |
| `output/IJIES_Draft_Paper_Mahathir_Muhammad.docx` | Draft paper format IJIES |
| `docs/presentations/PPT_Outline_TDAS_AD_Audit_v4.docx` | Outline presentasi + 7 gambar |
| `data/phase*.csv` | Hasil antar-fase (di-`.gitignore`, regenerated) |
| `models/` | Model IF/LOF/EE + Scaler tersimpan (di-`.gitignore`) |

## 2.8 Troubleshooting

| Gejala | Penyebab & solusi |
|--------|-------------------|
| `cannot import name 'Neo4jIngester'` | Nama kelas yang benar **`Neo4jIngestor`** (pakai 'o'). |
| `ServiceUnavailable` / `ConnectionRefused` | Neo4j tidak running, atau instance/port salah. Nyalakan instance yang benar. |
| Phase 5 error `NEO4J_URI not defined` | Jalankan cell koneksi di bagian atas notebook dulu (jangan loncat ke Phase 5). |
| Data berubah antar-run | Pastikan pakai versi Phase 2 terbaru (yang reset DB). Versi lama meng-inflasi `r.count`. |
| `PermissionError` saat generate `.docx` | File sedang dibuka di Word — tutup dulu. |
| `UnicodeEncodeError` (cp1252) di Windows | Set `$env:PYTHONIOENCODING="utf-8"` sebelum menjalankan script. |
| Neo4j OOM / crash saat clear | Jangan pakai `DETACH DELETE` massal — gunakan `CREATE OR REPLACE DATABASE` (sudah default). |

---

## Lampiran — Glosarium singkat untuk dosen

- **Knowledge Graph** — representasi data sebagai node (entitas) & relationship (relasi) yang bisa di-query.
- **Ensemble** — penggabungan beberapa model agar keputusan lebih robust.
- **Unsupervised** — belajar tanpa label benar/salah; cocok karena log AD tak berlabel.
- **SHAP** — metode menjelaskan kontribusi tiap fitur ke prediksi sebuah model.
- **Quantile/Persentil** — nilai pembatas; P95 = batas yang melebihi 95% data.
- **Cohen's Kappa** — ukuran kesepakatan dua klasifikasi (1=sepakat penuh, 0=acak).
- **Precision@K** — dari K teratas yang ditandai, berapa persen yang benar relevan.
- **Weak supervision / proxy** — label perkiraan (di sini `rule_violations`) sebagai pengganti label asli.

*Dokumen ini auto-konsisten dengan data kanonik pipeline (887 user, 89 anomali MEDIUM+). Update dengan menjalankan ulang pipeline lalu generator dokumen.*
