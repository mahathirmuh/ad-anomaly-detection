# Cypher Query Cheatsheet — AD Audit

Kumpulan query Cypher siap pakai untuk eksplorasi hasil pipeline di Neo4j Browser (`http://localhost:7474`).

---

## 1. Diagnosis & Status Pipeline

### Cek total node per type

```cypher
MATCH (n) RETURN labels(n)[0] as node_type, count(n) as jumlah ORDER BY jumlah DESC
```

### Cek apakah pipeline sudah jalan lengkap

```cypher
MATCH (u:User)
RETURN
  count(u) as total_users,
  count(u.rule_violations) as has_phase3_rules,
  count(u.feature_host_diversity) as has_phase4_features,
  count(u.anomaly_score) as has_phase5_anomaly,
  count(u.shap_top_feature) as has_phase55_shap
```

### Cek properti yang ada di User node

```cypher
MATCH (u:User) RETURN keys(u) as properties LIMIT 1
```

### Cek total relationship per type

```cypher
MATCH ()-[r]->() RETURN type(r) as relation, count(r) as jumlah ORDER BY jumlah DESC
```

---

## 2. Investigasi Anomali

### Distribusi severity

```cypher
MATCH (u:User)
WHERE u.severity IS NOT NULL
RETURN u.severity, count(u) as jumlah
ORDER BY jumlah DESC
```

### Top 10 user paling anomali

```cypher
MATCH (u:User)
WHERE u.anomaly_score IS NOT NULL
RETURN u.username,
       u.anomaly_score,
       u.severity,
       u.rule_violations,
       u.shap_top_feature_label as alasan_utama
ORDER BY u.anomaly_score DESC
LIMIT 10
```

### Semua user CRITICAL & HIGH

```cypher
MATCH (u:User)
WHERE u.severity IN ['CRITICAL', 'HIGH']
RETURN u.username, u.anomaly_score, u.severity, u.shap_top_feature_label
ORDER BY u.anomaly_score DESC
```

### Detail satu user spesifik

```cypher
MATCH (u:User {username: 'mti.admin'})
RETURN u
```

### Lihat semua properti satu user

```cypher
MATCH (u:User {username: 'mti.admin'})
RETURN keys(u) as semua_properti, u
```

---

## 3. Rule Violations (Phase 3)

### User dengan rule violations terbanyak

```cypher
MATCH (u:User)
WHERE u.rule_violations >= 3
RETURN u.username, u.rule_violations, u.max_rule_severity
ORDER BY u.rule_violations DESC
LIMIT 20
```

### User yang melanggar rule tertentu (R001 - login banyak host)

```cypher
MATCH (u:User)
WHERE u.rule_R001_violation = true
RETURN u.username, u.rule_R001_unique_hosts, u.rule_R001_severity
ORDER BY u.rule_R001_unique_hosts DESC
```

### User yang sering lockout (R008)

```cypher
MATCH (u:User)
WHERE u.rule_R008_violation = true
RETURN u.username, u.rule_R008_lockouts, u.rule_R008_severity
ORDER BY u.rule_R008_lockouts DESC
```

### User yang banyak admin action (R009)

```cypher
MATCH (u:User)
WHERE u.rule_R009_violation = true
RETURN u.username, u.rule_R009_admin_actions, u.rule_R009_severity
ORDER BY u.rule_R009_admin_actions DESC
```

### User di sensitive group (R010)

```cypher
MATCH (u:User)
WHERE u.rule_R010_violation = true
RETURN u.username, u.rule_R010_sensitive_groups, u.rule_R010_severity
ORDER BY u.rule_R010_sensitive_groups DESC
```

### Statistik per rule (berapa user yang melanggar)

```cypher
MATCH (u:User)
RETURN
  sum(CASE WHEN u.rule_R001_violation THEN 1 ELSE 0 END) as R001,
  sum(CASE WHEN u.rule_R002_violation THEN 1 ELSE 0 END) as R002,
  sum(CASE WHEN u.rule_R003_violation THEN 1 ELSE 0 END) as R003,
  sum(CASE WHEN u.rule_R004_violation THEN 1 ELSE 0 END) as R004,
  sum(CASE WHEN u.rule_R005_violation THEN 1 ELSE 0 END) as R005,
  sum(CASE WHEN u.rule_R006_violation THEN 1 ELSE 0 END) as R006,
  sum(CASE WHEN u.rule_R007_violation THEN 1 ELSE 0 END) as R007,
  sum(CASE WHEN u.rule_R008_violation THEN 1 ELSE 0 END) as R008,
  sum(CASE WHEN u.rule_R009_violation THEN 1 ELSE 0 END) as R009,
  sum(CASE WHEN u.rule_R010_violation THEN 1 ELSE 0 END) as R010
```

---

## 4. Graph Visualization

### Visualisasi 1 user + semua koneksinya

```cypher
MATCH (u:User {username: 'mti.admin'})-[r]-(n)
RETURN u, r, n
LIMIT 50
```

### Visualisasi user CRITICAL + relasi mereka

```cypher
MATCH (u:User)-[r]-(n)
WHERE u.severity = 'CRITICAL'
RETURN u, r, n
LIMIT 100
```

### Hanya tampilkan login pattern (User -> Hostname)

```cypher
MATCH (u:User)-[r:LOGIN_FROM]->(h:Hostname)
WHERE u.severity IN ['CRITICAL', 'HIGH']
RETURN u, r, h
LIMIT 50
```

### Privilege escalation graph (admin actions)

```cypher
MATCH (actor:User)-[r:ADMIN_ACTION_ON]->(target:User)
WHERE actor.severity IN ['CRITICAL', 'HIGH', 'MEDIUM']
RETURN actor, r, target
LIMIT 50
```

---

## 5. Pattern Hunting (Threat Hunting)

### Shared device antar user anomali (kemungkinan akun bocor)

```cypher
MATCH (u1:User)-[:LOGIN_FROM]->(h:Hostname)<-[:LOGIN_FROM]-(u2:User)
WHERE u1.severity IN ['CRITICAL', 'HIGH']
  AND u2.severity IN ['CRITICAL', 'HIGH']
  AND u1.user_id < u2.user_id
RETURN u1.username, u2.username, h.name as device_bersama
LIMIT 20
```

### User anomali yang akses Domain Controller

```cypher
MATCH (u:User)-[:AUTHENTICATED_VIA]->(s:Server)
WHERE u.severity IN ['CRITICAL', 'HIGH']
  AND s.type = 'DOMAIN_CONTROLLER'
RETURN u.username, u.severity, s.name as DC, u.shap_top_feature_label
ORDER BY u.anomaly_score DESC
```

### IP yang dipakai banyak user (suspicious shared IP)

```cypher
MATCH (u:User)-[:CONNECTED_FROM]->(ip:IPAddress)
WITH ip, count(DISTINCT u) as user_count, collect(DISTINCT u.username) as users
WHERE user_count > 5
RETURN ip.address, user_count, users[..10] as users_list
ORDER BY user_count DESC
LIMIT 20
```

### Failed login spike (brute force candidates)

```cypher
MATCH (u:User)-[r:FAILED_LOGIN]->(s:Server)
WITH u, sum(r.count) as total_failures
WHERE total_failures > 50
RETURN u.username, total_failures, u.severity
ORDER BY total_failures DESC
LIMIT 20
```

### Off-hours access (login antara 22:00 - 06:00)

```cypher
MATCH (u:User)-[r:LOGIN_FROM]->(h:Hostname)
WHERE r.timestamp IS NOT NULL AND r.timestamp =~ '^[0-9]{4}-.*'
WITH u, h, datetime(replace(r.timestamp, ' ', 'T')).hour as login_hour
WHERE login_hour < 6 OR login_hour >= 22
RETURN u.username, h.name as host, login_hour, count(*) as jumlah
ORDER BY jumlah DESC
LIMIT 20
```

### Admin action chain (siapa beraksi terhadap akun anomali)

```cypher
MATCH (actor:User)-[r:ADMIN_ACTION_ON]->(target:User)
WHERE target.severity IN ['CRITICAL', 'HIGH']
RETURN actor.username, target.username, r.count, r.last_description
ORDER BY r.count DESC
```

### Lockout pattern per server

```cypher
MATCH (u:User)-[r:LOCKED_OUT]->(s:Server)
WITH s, sum(r.count) as total_lockouts, count(DISTINCT u) as unique_users
RETURN s.name as server, total_lockouts, unique_users
ORDER BY total_lockouts DESC
```

---

## 6. Per-Method ML Analysis (IF, LOF, EE)

Query untuk menganalisis hasil tiap algoritma anomaly detection secara terpisah.

### Isolation Forest (IF) — Top anomali

> Catatan: `if_score` makin **negatif** = makin anomali

```cypher
MATCH (u:User)
WHERE u.if_score IS NOT NULL
RETURN u.username, u.if_score, u.severity
ORDER BY u.if_score ASC
LIMIT 10
```

### Local Outlier Factor (LOF) — Top anomali

> Catatan: `lof_score` makin **negatif** = makin anomali

```cypher
MATCH (u:User)
WHERE u.lof_score IS NOT NULL
RETURN u.username, u.lof_score, u.severity
ORDER BY u.lof_score ASC
LIMIT 10
```

### Elliptic Envelope (EE) — Top anomali

> Catatan: `ee_score` makin **rendah/negatif** = makin anomali

```cypher
MATCH (u:User)
WHERE u.ee_score IS NOT NULL
RETURN u.username, u.ee_score, u.severity
ORDER BY u.ee_score ASC
LIMIT 10
```

### Bandingkan skor 3 model side-by-side

```cypher
MATCH (u:User)
WHERE u.anomaly_score IS NOT NULL
RETURN u.username,
       u.if_score   as IF,
       u.lof_score  as LOF,
       u.ee_score   as EE,
       u.anomaly_votes as votes,
       u.anomaly_score as final,
       u.severity
ORDER BY u.anomaly_score DESC
LIMIT 15
```

### User yang DISETUJUI SEMUA 3 model (votes = 3)

> Anomali paling kuat — semua model setuju

```cypher
MATCH (u:User)
WHERE u.anomaly_votes = 3
RETURN u.username, u.if_score, u.lof_score, u.ee_score,
       u.anomaly_score, u.severity, u.shap_top_feature_label
ORDER BY u.anomaly_score DESC
```

### User borderline (votes = 2) — perlu review manual

```cypher
MATCH (u:User)
WHERE u.anomaly_votes = 2
RETURN u.username, u.if_score, u.lof_score, u.ee_score,
       u.anomaly_score, u.severity, u.shap_top_feature_label
ORDER BY u.anomaly_score DESC
LIMIT 20
```

### User dengan vote tunggal (votes = 1) — kemungkinan false positive

```cypher
MATCH (u:User)
WHERE u.anomaly_votes = 1
RETURN u.username, u.if_score, u.lof_score, u.ee_score, u.severity
ORDER BY u.anomaly_score DESC
LIMIT 20
```

### Distribusi voting (berapa user di tiap level konsensus)

```cypher
MATCH (u:User)
WHERE u.anomaly_votes IS NOT NULL
RETURN u.anomaly_votes as setuju_berapa_model, count(u) as jumlah_user
ORDER BY u.anomaly_votes DESC
```

### Disagreement antar model (model A flag, B & C tidak)

```cypher
// Hanya IF yang flag (LOF & EE tidak)
MATCH (u:User)
WHERE u.if_anomaly = 1 AND u.lof_anomaly = 0 AND u.ee_anomaly = 0
RETURN u.username, u.if_score, u.severity
LIMIT 10
```

```cypher
// Hanya LOF yang flag
MATCH (u:User)
WHERE u.if_anomaly = 0 AND u.lof_anomaly = 1 AND u.ee_anomaly = 0
RETURN u.username, u.lof_score, u.severity
LIMIT 10
```

```cypher
// Hanya EE yang flag
MATCH (u:User)
WHERE u.if_anomaly = 0 AND u.lof_anomaly = 0 AND u.ee_anomaly = 1
RETURN u.username, u.ee_score, u.severity
LIMIT 10
```

### Statistik per model (avg, min, max score)

```cypher
MATCH (u:User)
WHERE u.if_score IS NOT NULL
RETURN
  avg(u.if_score)  as IF_avg,  min(u.if_score)  as IF_min,  max(u.if_score)  as IF_max,
  avg(u.lof_score) as LOF_avg, min(u.lof_score) as LOF_min, max(u.lof_score) as LOF_max,
  avg(u.ee_score)  as EE_avg,  min(u.ee_score)  as EE_min,  max(u.ee_score)  as EE_max
```

### User yang flagged satu model spesifik (tabel boolean)

```cypher
MATCH (u:User)
WHERE u.if_anomaly IS NOT NULL
RETURN u.username,
       u.if_anomaly  as IF_flag,
       u.lof_anomaly as LOF_flag,
       u.ee_anomaly  as EE_flag,
       u.anomaly_votes as total_votes
ORDER BY u.anomaly_votes DESC
LIMIT 20
```

---

## 7. SHAP Feature Analysis

### Distribusi top SHAP feature

```cypher
MATCH (u:User)
WHERE u.shap_top_feature_label IS NOT NULL
  AND u.severity <> 'NORMAL'
RETURN u.shap_top_feature_label as alasan, count(u) as jumlah
ORDER BY jumlah DESC
```

### User yang anomali karena privilege tinggi

```cypher
MATCH (u:User)
WHERE u.shap_top_feature_label = 'Level privilege tinggi'
RETURN u.username, u.anomaly_score, u.severity, u.feature_privilege_level
ORDER BY u.anomaly_score DESC
```

### User yang anomali karena banyak admin action

```cypher
MATCH (u:User)
WHERE u.shap_top_feature_label = 'Banyak admin action'
RETURN u.username, u.anomaly_score, u.feature_admin_actions
ORDER BY u.anomaly_score DESC
```

---

## 8. Statistics & Aggregations

### Statistik anomaly score

```cypher
MATCH (u:User) WHERE u.anomaly_score IS NOT NULL
RETURN
  count(u) as total,
  avg(u.anomaly_score) as avg_score,
  min(u.anomaly_score) as min_score,
  max(u.anomaly_score) as max_score,
  percentileCont(u.anomaly_score, 0.5) as median_score,
  percentileCont(u.anomaly_score, 0.95) as p95_score
```

### User per server (siapa paling sering akses server tertentu)

```cypher
MATCH (u:User)-[r:AUTHENTICATED_VIA]->(s:Server)
WHERE s.name = 'MBMMRWDC01.mbma.com'
RETURN u.username, r.frequency
ORDER BY r.frequency DESC
LIMIT 20
```

### Top 10 host paling banyak dipakai

```cypher
MATCH (u:User)-[:LOGIN_FROM]->(h:Hostname)
WITH h, count(DISTINCT u) as user_count
RETURN h.name as host, user_count
ORDER BY user_count DESC
LIMIT 10
```

### Distribusi login per jam (analisis pola waktu)

```cypher
MATCH (u:User)-[r:LOGIN_FROM]->(h:Hostname)
WHERE r.timestamp IS NOT NULL AND r.timestamp =~ '^[0-9]{4}-.*'
WITH datetime(replace(r.timestamp, ' ', 'T')).hour as jam
RETURN jam, count(*) as jumlah_login
ORDER BY jam
```

---

## 9. Multi-Hop Graph Traversal

### Path: User → Host → IP → Host lain → User lain

Mencari user yang share device DAN share IP (collusion suspect):

```cypher
MATCH path = (u1:User)-[:LOGIN_FROM]->(h1:Hostname)-[:USED_IP]->(ip:IPAddress)
              <-[:USED_IP]-(h2:Hostname)<-[:LOGIN_FROM]-(u2:User)
WHERE u1 <> u2
RETURN u1.username, h1.name, ip.address, h2.name, u2.username
LIMIT 10
```

### User yang akses DC dari IP unusual

```cypher
MATCH (u:User)-[:CONNECTED_FROM]->(ip:IPAddress)
MATCH (u)-[:AUTHENTICATED_VIA]->(s:Server)
WHERE s.type = 'DOMAIN_CONTROLLER'
  AND NOT ip.range_category IN ['Office_Network', 'VPN']
RETURN u.username, ip.address, s.name
LIMIT 20
```

### 2-hop: User → Group → User lain (member grup yang sama)

```cypher
MATCH (u1:User)-[:REAL_MEMBER_OF]->(g:Group)<-[:REAL_MEMBER_OF]-(u2:User)
WHERE u1 <> u2 AND g.privilege_level IN ['ADMIN', 'HIGH']
RETURN u1.username, u2.username, g.group_name as grup_sensitif
LIMIT 20
```

---

## 10. Maintenance & Cleanup

### Hapus semua data (HATI-HATI)

```cypher
MATCH (n) DETACH DELETE n
```

### Hapus property tertentu (kalau mau re-run analisis)

```cypher
MATCH (u:User)
REMOVE u.anomaly_score, u.severity, u.shap_top_feature
RETURN count(u)
```

### Cek transaksi yang sedang berjalan

```cypher
SHOW TRANSACTIONS
```

### Cek index dan constraint

```cypher
SHOW INDEXES
SHOW CONSTRAINTS
```

---

## 11. Tips Eksplorasi di Neo4j Browser

| Aksi | Cara |
|------|------|
| Lihat graph visual | Pilih view **Graph** di kanan atas hasil |
| Lihat tabel data | Pilih view **Table** |
| Lihat detail node | Klik node → panel kanan muncul properti |
| Expand relasi | Klik kanan node → "Expand" |
| Save query | Klik bookmark icon |
| Layout otomatis | Drag node, atau gunakan layout tools di kiri bawah |

---

## Glosarium Properti User Node

| Phase | Properti | Deskripsi |
|-------|----------|-----------|
| 2 | `user_id`, `username` | Identitas user |
| 3 | `rule_R001_violation` ... `rule_R010_violation` | Boolean per rule |
| 3 | `rule_violations` | Total rule yang dilanggar (0-10) |
| 3 | `max_rule_severity` | HIGH/MEDIUM/LOW |
| 4 | `feature_host_diversity` | Jumlah host unik |
| 4 | `feature_critical_server_ratio` | Akses server kritikal |
| 4 | `feature_failure_ratio` | Intensitas login gagal (Σ gagal ÷ relasi LOGIN_FROM; bukan rasio 0–1) |
| 4 | `feature_shared_device_risk` | Risiko shared device |
| 4 | `feature_ip_network_risk` | Risiko IP unusual |
| 4 | `feature_privilege_level` | Level privilege (1-4) |
| 4 | `feature_connectivity` | Degree centrality |
| 4 | `feature_rule_violations` | Sama dengan rule_violations |
| 4 | `feature_lockout_count` | Jumlah lockout |
| 4 | `feature_admin_actions` | Jumlah admin action |
| 4 | `feature_sensitive_groups` | Anggota grup sensitif |
| 5 | `anomaly_score` | Skor anomali final (0-1) |
| 5 | `severity` | CRITICAL/HIGH/MEDIUM/LOW/NORMAL |
| 5 | `anomaly_votes` | Vote dari 3 model (0-3) |
| 5 | `is_anomaly` | 0 atau 1 |
| 5 | `if_score`, `lof_score`, `ee_score` | Skor per model |
| 5.5 | `shap_top_feature` | Fitur penyebab utama |
| 5.5 | `shap_top_feature_label` | Label Bahasa Indonesia |
| 5.5 | `shap_top_feature_value` | Nilai SHAP |
| 5.5 | `shap_top_feature_2`, `_3` | Penyebab 2 & 3 |
