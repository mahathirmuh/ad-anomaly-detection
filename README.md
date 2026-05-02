# AD Audit — Anomaly Detection Pipeline

Sistem deteksi anomali perilaku pengguna Active Directory berbasis Knowledge Graph (Neo4j) dan Ensemble Machine Learning.

## Arsitektur Pipeline

```
Raw AD Logs
    │
    ▼
[Phase 2] Neo4j Ingestion         → Knowledge Graph (7 node types, 8 rel types)
    │
    ▼
[Phase 3] Rule-Based Engine       → 7 domain rules → flag pelanggaran per user
    │
    ▼
[Phase 4] Graph Feature Extraction → 8 fitur ML dari graph
    │
    ▼
[Phase 5] Ensemble Anomaly Detection → IF + LOF + EE → anomaly score
    │
    ▼
[Phase 5.5] SHAP Explainability   → top cause per user
    │
    ▼
[Phase 6] Reporting               → laporan teks, JSON, DOCX
```

---

## Prasyarat

### Software

| Software | Versi | Keterangan |
|----------|-------|------------|
| Python | 3.10+ | Direkomendasikan 3.12 |
| Neo4j | 5.x | Community atau Enterprise |
| Jupyter | 1.0+ | Untuk menjalankan notebook |

### Instalasi dependensi Python

```bash
pip install -r requirements.txt
```

Atau gunakan setup script (Linux/Mac):

```bash
bash setup.sh
```

Dependensi utama: `neo4j`, `pandas`, `numpy`, `scikit-learn`, `shap`, `matplotlib`, `python-docx`

---

## Konfigurasi

Edit bagian konfigurasi di **`pipeline_adaudit.ipynb`** (cell kedua) atau langsung di masing-masing script:

```python
NEO4J_URI      = "bolt://localhost:7687"
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "lalarasa"          # ganti dengan password Neo4j Anda

DATA_CSV = "data/restructured_data/unified_logon_events.csv"
```

Pastikan Neo4j sudah berjalan sebelum menjalankan pipeline:

- **Desktop**: buka Neo4j Desktop → klik **Start**
- **Service**: `neo4j start` atau `net start neo4j`
- **Verifikasi**: buka `http://localhost:7474` di browser

---

## Struktur Data Input

Letakkan file CSV raw di folder `data/raw_data/` dengan format berikut:

| File | Keterangan |
|------|------------|
| `Domain Controller Logon Activity.csv` | Event logon ke DC |
| `2. Member Server Logon Activity.csv` | Event logon ke member server |
| `Logon Failures.csv` | Event login gagal |
| `Recently Added Members to Security Groups.csv` | Penambahan member ke grup |

File yang sudah digabung tersedia di `data/restructured_data/unified_logon_events.csv` (1.8 juta+ events).

---

## Cara Menjalankan

### Opsi 1 — Jupyter Notebook (Direkomendasikan)

```bash
jupyter notebook pipeline_adaudit.ipynb
```

Jalankan cell per cell secara berurutan dari atas ke bawah. Setiap phase memiliki cell markdown penjelasan diikuti cell kode.

### Opsi 2 — Script Python Langsung

Jalankan secara berurutan dari terminal:

```bash
# Phase 2: Ingest data ke Neo4j (lama, jalankan sekali saja)
python neo4j_ingest_phase2.py

# Phase 3: Terapkan 7 domain rules
python neo4j_phase3_rules.py

# Phase 4: Ekstrak 8 fitur dari graph
python neo4j_phase4_features.py

# Phase 5: Ensemble anomaly detection
python neo4j_phase5_anomaly.py

# Phase 5.5: SHAP explainability
python neo4j_phase55_shap.py

# Phase 6: Generate laporan lengkap
python neo4j_phase6_reporting.py
```

---

## Detail Setiap Phase

### Phase 2 — Neo4j Ingestion

**Script:** `neo4j_ingest_phase2.py`  
**Input:** `data/restructured_data/unified_logon_events.csv`  
**Output:** Neo4j graph dengan node dan relationship

Node types yang dibuat:

| Node | Key Property | Keterangan |
|------|-------------|------------|
| `User` | `user_id` | Akun pengguna AD |
| `Hostname` | `hostname` | Workstation/komputer |
| `Server` | `server_id` | Server yang diakses |
| `IPAddress` | `ip_address` | Alamat IP |
| `Service` | `service_name` | Layanan yang diakses |
| `Group` | `group_name` | Security group |
| `Event` | `event_id` | Event Windows |

Relationship types:

| Relationship | Dari | Ke | Keterangan |
|-------------|------|----|------------|
| `LOGIN_FROM` | User | Hostname | Logon dari workstation |
| `AUTHENTICATED_VIA` | User | Server | Autentikasi ke server |
| `FAILED_LOGIN` | User | Server | Login gagal |
| `CONNECTED_FROM` | User | IPAddress | Koneksi dari IP |
| `USED_SERVICE` | User | Service | Menggunakan layanan |
| `MEMBER_OF` | User | Group | Anggota grup |

> **Estimasi waktu:** 10–30 menit untuk 1.8 juta events. Jalankan sekali saja.

---

### Phase 3 — Rule-Based Knowledge Engine

**Script:** `neo4j_phase3_rules.py`  
**Output:** Property `rule_violations` dan flag pada setiap node User

| Rule ID | Nama | Kondisi Anomali |
|---------|------|----------------|
| R001 | Multi-host login | Login dari > 3 host unik |
| R002 | Off-hours login | > 10% login di luar jam 08:00–18:00 |
| R003 | Shared device | Device dipakai oleh > 5 user berbeda |
| R004 | Critical server access | Akses ke Domain Controller atau server CRITICAL/HIGH |
| R005 | Failed login spike | > 50 kali login gagal |
| R006 | Unusual IP | > 20% koneksi dari IP di luar Office/VPN |
| R007 | After-hours privileged | Admin mengakses DC di luar jam kerja atau weekend |

---

### Phase 4 — Graph Feature Extraction

**Script:** `neo4j_phase4_features.py`  
**Output:** `data/phase4_graph_features.csv`

| Fitur | Keterangan | Range |
|-------|-----------|-------|
| `host_diversity` | Jumlah host unik relatif terhadap rata-rata | 0–N |
| `critical_server_ratio` | Proporsi akses ke server kritikal | 0.0–1.0 |
| `failure_ratio` | Rasio login gagal / total login | 0.0–1.0 |
| `shared_device_risk` | Rata-rata user per device yang diakses | 1–N |
| `ip_network_risk` | Proporsi IP di luar jaringan kantor/VPN | 0.0–1.0 |
| `privilege_level` | Level privilege tertinggi (1=user biasa, 4=admin) | 1–4 |
| `connectivity` | Degree centrality dalam graph | 0.0–1.0 |
| `rule_violations` | Jumlah rule yang dilanggar | 0–7 |

---

### Phase 5 — Ensemble Anomaly Detection

**Script:** `neo4j_phase5_anomaly.py`  
**Output:** `data/phase5_anomaly_results.csv`, `data/phase5_anomalies_summary.csv`, `models/`

Tiga algoritma digabungkan:

| Model | Metode | Kekuatan |
|-------|--------|---------|
| Isolation Forest (IF) | Random partitioning | Efektif untuk anomali global |
| Local Outlier Factor (LOF) | Density-based | Efektif untuk anomali lokal |
| Elliptic Envelope (EE) | Robust covariance | Efektif untuk distribusi Gaussian |

**Formula skor akhir:**

```
final_score = 0.60 × ensemble_votes_ratio + 0.40 × rule_violations_score
```

**Kriteria anomali:** user dianggap anomali jika >= 2 dari 3 model setuju.

**Klasifikasi severity:**

| Severity | Threshold Score |
|----------|---------------|
| CRITICAL | >= 0.7 |
| HIGH | >= 0.5 |
| MEDIUM | >= 0.3 |
| LOW | >= 0.1 |
| NORMAL | < 0.1 |

Model tersimpan di folder `models/`:
- `isolation_forest_model.pkl`
- `lof_model.pkl`
- `elliptic_envelope_model.pkl`
- `feature_scaler.pkl`

---

### Phase 5.5 — SHAP Explainability

**Script:** `neo4j_phase55_shap.py`  
**Output:** `data/phase55_shap_values.csv`, `data/phase55_shap_anomalies.csv`

Menggunakan `shap.TreeExplainer` yang native untuk Isolation Forest. Setiap user mendapat:
- Nilai SHAP untuk setiap fitur (kontribusi terhadap anomaly score)
- `top_feature_1/2/3`: tiga fitur penyebab utama
- Label Bahasa Indonesia untuk setiap fitur

Hasil juga ditulis kembali ke Neo4j sebagai property pada node User (`shap_top_feature`, `shap_top_feature_label`, dll).

---

### Phase 6 — Reporting

**Script:** `neo4j_phase6_reporting.py`  
**Output:**

| File | Format | Isi |
|------|--------|-----|
| `output/anomaly_detection_report.txt` | Teks | Executive summary, top anomali, rekomendasi |
| `output/anomaly_detection_detailed.json` | JSON | 50 anomali teratas + evidence + SHAP |
| `output/anomaly_statistics.json` | JSON | Distribusi severity, statistik fitur |
| `output/AD_Anomaly_Detection_Report.docx` | Word | Laporan formal siap cetak |

---

## Struktur Folder

```
tdas_adauditv3/
├── pipeline_adaudit.ipynb          # Notebook utama (jalankan ini)
│
├── neo4j_ingest_phase2.py          # Phase 2: Neo4j ingestion
├── neo4j_phase3_rules.py           # Phase 3: Rule engine
├── neo4j_phase4_features.py        # Phase 4: Feature extraction
├── neo4j_phase5_anomaly.py         # Phase 5: Anomaly detection
├── neo4j_phase55_shap.py           # Phase 5.5: SHAP explainability
├── neo4j_phase6_reporting.py       # Phase 6: Reporting
│
├── restructure_for_neo4j.py        # Pra-proses: gabung CSV raw
├── generate_report_docx.py         # Generate laporan Word
├── requirements.txt                # Dependensi Python
├── setup.sh                        # Setup script (Linux/Mac)
│
├── data/
│   ├── raw_data/                   # CSV mentah dari AD
│   ├── restructured_data/          # CSV gabungan (unified_logon_events.csv)
│   ├── phase4_graph_features.csv   # Output Phase 4
│   ├── phase5_anomaly_results.csv  # Output Phase 5
│   ├── phase55_shap_values.csv     # Output Phase 5.5 (semua user)
│   └── phase55_shap_anomalies.csv  # Output Phase 5.5 (anomali saja)
│
├── models/                         # Model ML tersimpan (.pkl)
├── output/                         # Laporan akhir
├── cypher/                         # Query Cypher untuk Neo4j Browser
└── docs/                           # Dokumentasi, referensi, presentasi
```

---

## Troubleshooting

### Neo4j tidak bisa terhubung

```
ServiceUnavailable: Failed to obtain a connection from the pool
```

Pastikan Neo4j berjalan dan cek kredensial di konfigurasi. Verifikasi dengan membuka `http://localhost:7474`.

### Error Cypher syntax di Phase 3/4

Pastikan menggunakan **Neo4j 5.x**. Script ini menggunakan sintaks terbaru:
- `datetime(x).hour` (bukan `hour(datetime(x))`)
- `COUNT { (pattern) }` (bukan `size((pattern))`)
- `NOT x IN list` (bukan `x NOT IN list`)

### SHAP error: model not found

Pastikan Phase 5 sudah dijalankan terlebih dahulu sehingga file `models/isolation_forest_model.pkl` ada.

### Encoding error di Windows

Jika muncul `UnicodeEncodeError` di terminal Windows, jalankan dengan:

```bash
set PYTHONIOENCODING=utf-8
python neo4j_phase6_reporting.py
```

---

## Output Contoh

```
ANOMALY DETECTION REPORT
========================
Total users analyzed : 2,729,818
Anomalies detected   : 19
  CRITICAL           : 2
  HIGH               : 5
  MEDIUM             : 12

Top Anomalous Users:
  mti.admin     Score: 0.5514  Cause: Level privilege tinggi
  svc.backup    Score: 0.4821  Cause: Pelanggaran rule
  ...
```

---

## Lisensi

Proyek ini dikembangkan untuk keperluan audit keamanan internal.
