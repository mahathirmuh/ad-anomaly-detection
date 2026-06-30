# Diagram Pipeline — Penjelasan

Folder ini berisi diagram alur pipeline: sumber Mermaid (`.mmd`) + hasil render (`.png` / `.svg`). Semua label diagram memakai **Bahasa Inggris** (konsisten), narasi penjelasan memakai Bahasa Indonesia.

## Daftar file

| File | Bentuk | Dipakai di | Penjelasan |
| --- | --- | --- | --- |
| `alur_project.(mmd/png/svg)` | Vertikal, ber-STAGE, **detail** (titik keputusan + fallback + artefak output) | [../ALUR_PROJECT.md](../ALUR_PROJECT.md), dokumentasi | Narasi lengkap per-STAGE ada di [../ALUR_PROJECT.md](../ALUR_PROJECT.md) |
| `paper_pipeline.(mmd/png/svg)` | **Landscape ringkas** (kiri → kanan) | **Figure 1** paper IJIES (Section 3.1) | Lihat bagian di bawah |
| `process_flow.(mmd/png/svg)` | **Sederhana — alur proses** (kiri → kanan, bahasa awam, tanpa detail teknis) | **Presentasi / sidang** (saran dosen: jangan terlalu teknis) | Lihat bagian di bawah |
| `framework_figure.(svg/png)` | **Gaya "framework figure" berbasis ikon** (line-art, layout ular 2 baris + kotak putus-putus), meniru gaya paper IEEE | **Figur paper / presentasi** (alternatif Figure 1) | Lihat bagian di bawah |

---

## Penjelasan `paper_pipeline.png`

Ini versi **ringkas-horizontal** yang dipakai sebagai **Figure 1** di paper (muat selebar kolom-penuh jurnal). Alur dibaca **kiri → kanan**:

1. **AD Audit Logs** — sumber data: ±1,8 juta event autentikasi Active Directory (887 user).
2. **Neo4j · Knowledge Graph** (Phase 2) — log diubah menjadi *property graph* (relasi user–host–server–IP–service–group).
3. **Rule Engine** (Phase 3) — 10 aturan domain dijalankan sebagai query Cypher → `rule_violations` / **rule_score** per user.
4. **Feature Extraction** (Phase 4) — 11 fitur graph per user (agregasi Cypher).
5. **Ensemble · contamination 5%** — tiga model *unsupervised* berjalan paralel:
   - **Isolation Forest** (berbasis pohon), **Local Outlier Factor** (densitas), **Elliptic Envelope** (kovarians).
6. **Majority Vote (≥ 2 of 3)** — user dianggap anomali bila ≥ 2 dari 3 model setuju → `ensemble_anomaly_score`.
7. **Score Fusion** — `final = 0.6 · ensemble + 0.4 · rule`. Panah putus-putus **rule_score** menandakan kontribusi Rule Engine (bobot 0.4) ke fusi.
8. **SHAP · TreeExplainer** — atribusi fitur per user (*top cause*), pada sub-model Isolation Forest.
9. **Severity** — klasifikasi ambang *data-driven* kuantil P75/P90/P95/P99.
10. **Explainer · Phase 7** — penjelasan *human-readable* yang *grounded* ke knowledge base + LLM.
11. **Anomaly Report** — daftar anomali ter-ranking, dijelaskan, dan tertaut MITRE ATT&CK.

> **Catatan:** penjelasan in-paper untuk figure ini ada di **Section 3.1 (System architecture)** dan **caption Figure 1** pada `output/IJIES_Draft_Paper_Mahathir_Muhammad.docx`.

---

## Penjelasan `process_flow.png` (versi sederhana)

Versi **non-teknis** untuk presentasi/sidang (saran dosen: *jangan terlalu teknis, lebih ke alur proses*). Hanya **alur proses** tingkat tinggi — tanpa hyperparameter, nama model, nama file, atau cabang fallback. 8 langkah, kiri → kanan:

1. **Active Directory Logs** — event login & aktivitas user.
2. **Build Knowledge Graph** — hubungkan user, perangkat, server.
3. **Apply Security Rules** — tandai pola berisiko (pengetahuan pakar).
4. **Summarize User Behavior** — buat profil per user.
5. **Detect Unusual Users** — machine learning menemukan yang menyimpang.
6. **Explain the Findings** — kenapa tiap user ditandai.
7. **Rank by Risk Level** — critical / high / medium / low.
8. **Readable Anomaly Report** — penjelasan jelas & bersumber.

> Butuh versi lengkap (keputusan + fallback)? Lihat `alur_project`. Butuh figur paper? Lihat `paper_pipeline`.

---

## `framework_figure.svg` (gaya ikon, seperti paper IEEE)

Figur **berbasis ikon line-art** yang meniru gaya *framework figure* paper IEEE (layout "ular": baris atas kiri → kanan, lalu turun, baris bawah kanan → kiri). Dibuat sebagai **SVG buatan tangan** (Mermaid tidak bisa ikon kustom) — vektor, **mudah diedit** (ubah label/ikon langsung di teks SVG), tajam di segala ukuran.

Alur: **AD Logs** → *(kotak putus-putus)* **Graph-Based Analysis** [Build Graph → Apply Rules → Extract Features] → **Anomaly Detection** ↓ **Severity Ranking** → **SHAP Attribution** → **Gen-AI Explainer** *(disuapi **Security Knowledge Base** — MITRE/Event IDs)* → **Evaluation**. Gen-AI Explainer + Security Knowledge Base = inti **Phase 7** (novelty "human-readable reasoning"). Catatan: label grup atas sengaja **"Graph-Based Analysis"** (bukan "Knowledge Graph") agar tidak rancu dengan **Security Knowledge Base** di bawah — keduanya konsep berbeda.

Versi tanpa caption untuk paper: `framework_figure_paper.svg/png` (dipakai sebagai **Figure 1** di `generate_paper_ijies.py`).

Rasterisasi ke PNG (butuh `sharp-cli`): `npx sharp-cli -i docs/diagrams/framework_figure.svg -o docs/diagrams/framework_figure.png --density 200`.

> Ikonnya geometris-bersih & relevan (dokumen, ensemble 3-lingkaran, bar severity, bar SHAP, **gelembung-chat + sparkle untuk Gen-AI**, **silinder untuk Knowledge Base**, gauge evaluasi). Untuk publikasi, gunakan `.svg` (vektor).

---

## `paper_pipeline` vs `alur_project` — beda peruntukan

| Aspek | `paper_pipeline` | `alur_project` |
| --- | --- | --- |
| Orientasi | Landscape (kiri → kanan) | Vertikal (atas → bawah) |
| Tingkat detail | Ringkas — alur inti | Detail — + titik keputusan, fallback, artefak CSV |
| Titik keputusan / fallback | Tidak ditampilkan | Ada (anomali? · API key? · output AI valid? → fallback template) |
| Tujuan | **Figure 1** paper (muat di kolom jurnal) | Dokumentasi & pemahaman menyeluruh |
| Narasi penjelasan | File ini | [../ALUR_PROJECT.md](../ALUR_PROJECT.md) (per-STAGE) |

---

## Re-render

```bash
# Figure paper (landscape)
npx @mermaid-js/mermaid-cli -i docs/diagrams/paper_pipeline.mmd -o docs/diagrams/paper_pipeline.png -b white -s 2

# Flowchart detail (vertikal)
npx @mermaid-js/mermaid-cli -i docs/diagrams/alur_project.mmd -o docs/diagrams/alur_project.png -b white -s 2

# Alur proses sederhana (presentasi / sidang)
npx @mermaid-js/mermaid-cli -i docs/diagrams/process_flow.mmd -o docs/diagrams/process_flow.png -b white -s 2
```
