# Panduan Testing & Verifikasi di Neo4j — TDAS AD Audit v4

Dokumen ini berisi **query Cypher siap pakai** untuk menguji/memverifikasi hasil setiap fase pipeline langsung di **Neo4j Browser**, lengkap dengan **angka kanonik** yang seharusnya muncul. Cocok untuk:
- Memastikan pipeline berjalan benar (smoke test setelah Run All).
- Demo & pembuktian saat sidang/presentasi ke dosen.

> **Akses:** buka `http://localhost:7474` → login (`neo4j` / `lalarasa`) → tempel query di kolom atas → tekan ▶.
> Semua nama property di sini sudah diverifikasi langsung dari kode `neo4j_phase*.py`.

**Data kanonik acuan:** 887 user · severity 9/36/44/133/665 · top anomali `mti.admin` (0.64).

---

## Peta property pada node `User`

| Sumber | Property |
|--------|----------|
| Phase 2 (Ingestion) | `user_id` (key), `username` |
| Phase 3 (Rules) | `rule_violations`, `rule_R001_unique_hosts` … `rule_R010_sensitive_groups` |
| Phase 4 (Features) | `feature_critical_server_ratio`, `feature_failure_ratio`, `feature_shared_device_risk`, `feature_ip_network_risk`, `feature_privilege_level`, `feature_connectivity`, `feature_rule_violations`, `feature_lockout_count`, `feature_admin_actions`, `feature_sensitive_groups` |
| Phase 5 (Ensemble) | `anomaly_score`, `severity`, `anomaly_votes`, `is_anomaly`, `if_score`, `lof_score`, `ee_score` |
| Phase 5.5 (SHAP) | `shap_top_feature`, `shap_top_feature_label`, `shap_top_feature_value`, `shap_top_feature_2`, `shap_top_feature_3` |

---

## A. Phase 2 — Ingestion (struktur graph)

**Jumlah node per label:**
```cypher
MATCH (n)
RETURN labels(n)[0] AS node_type, count(*) AS jumlah
ORDER BY jumlah DESC;
```

**Jumlah relationship per tipe:**
```cypher
MATCH ()-[r]->()
RETURN type(r) AS relationship, count(*) AS jumlah
ORDER BY jumlah DESC;
```

✅ **Harus:** `User = 887`, total node ~680K. Muncul **10 tipe relationship**: LOGIN_FROM, AUTHENTICATED_VIA, FAILED_LOGIN, CONNECTED_FROM, USED_IP, USED_SERVICE, MEMBER_OF, REFERENCES, LOCKED_OUT, ADMIN_ACTION_ON.

---

## B. Phase 3 — Rule Engine

**Distribusi pelanggaran rule:**
```cypher
MATCH (u:User)
RETURN u.rule_violations AS pelanggaran, count(*) AS jumlah_user
ORDER BY pelanggaran;
```

**Ringkasan cepat (selaras laporan):**
```cypher
MATCH (u:User)
RETURN
  sum(CASE WHEN u.rule_violations = 0 THEN 1 ELSE 0 END)  AS nol,
  sum(CASE WHEN u.rule_violations IN [1,2] THEN 1 ELSE 0 END) AS satu_dua,
  sum(CASE WHEN u.rule_violations >= 3 THEN 1 ELSE 0 END) AS tiga_plus,
  avg(u.rule_violations) AS rata_rata;
```

✅ **Harus:** nol = 165 · 1–2 = 125 · 3+ = 597 · rata-rata ≈ **3.39**.

---

## C. Phase 4 — Feature Extraction

**Pastikan 11 fitur terisi (contoh satu user):**
```cypher
MATCH (u:User {username: 'mti.admin'})
RETURN u.feature_critical_server_ratio, u.feature_failure_ratio,
       u.feature_shared_device_risk,    u.feature_ip_network_risk,
       u.feature_privilege_level,       u.feature_connectivity,
       u.feature_lockout_count,         u.feature_admin_actions,
       u.feature_sensitive_groups,      u.feature_rule_violations;
```

**Cek tidak ada fitur yang kosong (null) di seluruh populasi:**
```cypher
MATCH (u:User)
WHERE u.feature_failure_ratio IS NULL
   OR u.feature_connectivity  IS NULL
RETURN count(u) AS user_fitur_kosong;
```

✅ **Harus:** semua `feature_*` terisi; `user_fitur_kosong = 0`.

---

## D. Phase 5 — Ensemble Anomaly Detection ★ (utama)

**Distribusi severity — angka inti presentasi:**
```cypher
MATCH (u:User)
RETURN u.severity AS severity, count(*) AS jumlah
ORDER BY jumlah DESC;
```
✅ **Harus persis:** NORMAL **665** · LOW **133** · MEDIUM **44** · HIGH **36** · CRITICAL **9**.

**Distribusi voting ensemble (berapa model setuju):**
```cypher
MATCH (u:User)
RETURN u.anomaly_votes AS votes, count(*) AS jumlah
ORDER BY votes;
```
✅ **Harus:** 0→807 · 1→35 · 2→35 · 3→10. *(votes ≥ 2 ⇒ `is_anomaly` true ≈ 45 user.)*

**Skor 3 model + skor akhir untuk user CRITICAL:**
```cypher
MATCH (u:User)
WHERE u.severity = 'CRITICAL'
RETURN u.username, u.if_score, u.lof_score, u.ee_score,
       u.anomaly_score, u.anomaly_votes
ORDER BY u.anomaly_score DESC;
```
✅ **Harus:** `mti.admin` di puncak, `anomaly_score = 0.64`.

**Total user perlu perhatian (MEDIUM ke atas):**
```cypher
MATCH (u:User)
WHERE u.severity IN ['CRITICAL','HIGH','MEDIUM']
RETURN count(u) AS perlu_perhatian;
```
✅ **Harus:** **89**.

---

## E. Phase 5.5 — SHAP Explainability

**Top anomali + PENYEBAB (yang dibawa ke laporan):**
```cypher
MATCH (u:User)
WHERE u.severity IN ['CRITICAL','HIGH']
RETURN u.username, u.anomaly_score, u.severity,
       u.shap_top_feature_label AS penyebab_utama,
       u.shap_top_feature_value
ORDER BY u.anomaly_score DESC
LIMIT 10;
```
✅ **Harus (5 teratas):**

| Username | Score | Severity | Penyebab utama |
|----------|:-----:|----------|----------------|
| mti.admin | 0.6400 | CRITICAL | Sering lockout |
| andre.saputra | 0.3925 | CRITICAL | Banyak admin action |
| mahathir.muhammad | 0.3914 | CRITICAL | Banyak admin action |
| mti.sysadmin | 0.3911 | CRITICAL | Banyak admin action |
| eris.rismansyah | 0.3740 | CRITICAL | Sering lockout |

**Lihat 3 penyebab teratas sekaligus untuk satu user:**
```cypher
MATCH (u:User {username: 'mti.admin'})
RETURN u.shap_top_feature_label AS penyebab_1,
       u.shap_top_feature_2     AS penyebab_2,
       u.shap_top_feature_3     AS penyebab_3,
       u.shap_top_feature_value AS kontribusi_1;
```

---

## F. Query DEMO untuk Presentasi (visualisasi graph)

**Tampilkan user CRITICAL beserta host & server yang diaksesnya:**
```cypher
MATCH (u:User {username: 'mti.admin'})
OPTIONAL MATCH (u)-[r1:LOGIN_FROM]->(h:Hostname)
OPTIONAL MATCH (u)-[r2:AUTHENTICATED_VIA]->(s:Server)
RETURN u, r1, h, r2, s
LIMIT 50;
```
> Klik tab **Graph** di Neo4j Browser → muncul visual node `mti.admin` terhubung ke banyak host & server. Bukti kuat: "user ini login dari banyak host sekaligus".

**Bandingkan satu user anomali vs satu user normal:**
```cypher
MATCH (u:User)
WHERE u.username IN ['mti.admin','<user_normal>']
RETURN u.username, u.severity, u.anomaly_score, u.rule_violations,
       u.shap_top_feature_label
ORDER BY u.anomaly_score DESC;
```

**Sebaran severity sebagai tabel ringkas (untuk slide):**
```cypher
MATCH (u:User)
WITH u.severity AS sev, count(*) AS n
RETURN sev, n,
       round(100.0 * n / 887, 1) AS persen
ORDER BY n DESC;
```

---

## Alur testing saat sidang (3 langkah)

1. **Buktikan data ada & benar** → jalankan **A** (struktur) + **D** (severity 9/36/44/133/665).
2. **Buktikan dapat dijelaskan** → jalankan **E** (ada kolom penyebab SHAP per user).
3. **Visualisasi** → jalankan **F** (graph view satu user mencurigakan).

> **Catatan penting untuk dosen:** query di Neo4j hanya **menampilkan** hasil yang sudah dihitung pipeline ML (IF/LOF/EE/SHAP) lalu ditulis balik ke node `User`. Neo4j di sini berperan sebagai **penyimpanan + visualisasi**, bukan mesin yang menghitung anomali.

---

## Troubleshooting query

| Gejala | Penyebab & solusi |
|--------|-------------------|
| Property `severity`/`anomaly_score` = null | Phase 5 belum dijalankan, atau dijalankan di database lain. Jalankan ulang pipeline. |
| `User` count ≠ 887 | Phase 2 belum selesai / database belum di-reset. Pastikan `CREATE OR REPLACE DATABASE` jalan. |
| `shap_top_feature_label` null | Phase 5.5 belum dijalankan (urutan: Phase 5 → 5.5). |
| Severity tidak cocok angka kanonik | Pipeline lama (sebelum severity kuantil) atau data ter-inflasi. Run ulang dari Phase 2. |
| Browser kosong / tak bisa connect | Instance Neo4j belum aktif. Nyalakan di Neo4j Desktop. |

*Dokumen ini auto-konsisten dengan data kanonik (887 user, 89 anomali MEDIUM+). Bila pipeline diubah & dijalankan ulang, sesuaikan angka acuan di atas.*
