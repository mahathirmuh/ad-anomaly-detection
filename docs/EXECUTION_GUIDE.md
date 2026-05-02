# Complete Pipeline Execution Guide

## Overview

Full end-to-end AD anomaly detection pipeline: **Data → Neo4j → Rules → Features → ML → Reports**

**Total Execution Time: ~4-5 hours** (mostly Phase 2 ingestion)

---

## Phase-by-Phase Execution

### **Phase 1: Data Preparation** ✅ DONE
- CSV files processed: 7 raw files → 4 unified tables
- unified_logon_events.csv: 1.8M events, 12 columns
- IP validation: 99.99% valid
- Status: **READY**

---

### **Phase 2: Neo4j Knowledge Graph** (2-3 hours)

#### Prerequisites
```bash
# 1. Check Neo4j running
docker ps | grep neo4j

# 2. Check CSV exists
ls -lh data/restructured_data/unified_logon_events.csv

# 3. Verify Python dependencies
pip list | grep "neo4j\|pandas"
```

#### Execution
```bash
cd /c/Users/itsupport/Documents/Apps/tdas_adauditv3
python neo4j_ingest_phase2.py
```

#### Expected Output
```
CREATING CONSTRAINTS & INDEXES
[OK] Constraints created

LOADING DATA
[OK] Loaded 1,833,352 rows

CREATING NODES
[1/7] Creating User nodes...         [OK] Created 714
[2/7] Creating Hostname nodes...     [OK] Created 1,270
[3/7] Creating Server nodes...       [OK] Created ~50
[4/7] Creating IPAddress nodes...    [OK] Created 1,270
[5/7] Creating Service nodes...      [OK] Created ~10
[6/7] Creating Group nodes...        [OK] Created 1-2
[7/7] Creating Event nodes...        [OK] Created 1,833,352
      ...processed 100K, 200K, ... events

CREATING RELATIONSHIPS
...processed 100K, 200K, ... relationships
[OK] Created ~10M relationships

VALIDATION STATISTICS
User nodes:                714
Hostname nodes:          1,270
Server nodes:              50
IPAddress nodes:        1,270
Service nodes:            10
Group nodes:              2
Event nodes:        1,833,352
LOGIN_FROM:         1,833,352
AUTHENTICATED_VIA:  1,833,352
FAILED_LOGIN:            635K
CONNECTED_FROM:     1,833,352
USED_IP:             2,000K
USED_SERVICE:         500K
MEMBER_OF:             714
REFERENCES:         1,833,352
```

#### Validation Query (in Neo4j Browser)
```cypher
MATCH (n) RETURN labels(n) as label, count(n) as count
```

**Expected Result:**
```
label                count
["User"]             714
["Hostname"]         1,270
["Server"]           50
["IPAddress"]        1,270
["Service"]          10
["Group"]            2
["Event"]            1,833,352
```

---

### **Phase 3: Rule-Based Knowledge** (5-10 minutes)

#### Execution
```bash
python neo4j_phase3_rules.py
```

#### Expected Output
```
PHASE 3: RULE-BASED KNOWLEDGE ENGINE

Implementing Rule R001: Normal Login Hosts...      [OK] Updated 714 users
Implementing Rule R002: Business Hours Pattern...  [OK] Updated 714 users
Implementing Rule R003: Shared Device Detection... [OK] Updated 714 users
Implementing Rule R004: Uncommon Server Access...  [OK] Updated 714 users
Implementing Rule R005: Failed Login Spike...      [OK] Updated 714 users
Implementing Rule R006: Unusual IP Address...      [OK] Updated 714 users
Implementing Rule R007: After-Hours Privileged...  [OK] Updated 714 users

Aggregating rule violations...  [OK] Aggregated for 714 users

VALIDATION STATISTICS
Users with R001 violation:  ~50-100
Users with R002 violation:  ~20-50
Users with R003 violation:  ~30-80
Users with R004 violation:  ~10-30
Users with R005 violation:  ~100-200
Users with R006 violation:  ~50-100
Users with R007 violation:  ~5-15
Users with 0 violations:    ~400-500
Users with 1-2 violations:  ~150-200
Users with 3+ violations:   ~50-100
Users with HIGH severity:   ~30-50
```

#### Validation Query
```cypher
MATCH (u:User) 
WHERE u.rule_violations IS NOT NULL 
RETURN u.rule_violations, count(u) as count 
ORDER BY u.rule_violations DESC
```

---

### **Phase 4: Graph Feature Extraction** (10-20 minutes)

#### Execution
```bash
python neo4j_phase4_features.py
```

#### Expected Output
```
PHASE 4: GRAPH FEATURE EXTRACTION

[1/8] Feature 1: Host Diversity...              [OK] Calculated
[2/8] Feature 2: Critical Server Ratio...       [OK] Calculated
[3/8] Feature 3: Failure Ratio...               [OK] Calculated
[4/8] Feature 4: Shared Device Risk...          [OK] Calculated
[5/8] Feature 5: IP Network Risk...             [OK] Calculated
[6/8] Feature 6: Privilege Level...             [OK] Calculated
[7/8] Feature 7: Connectivity Score...          [OK] Calculated
[8/8] Feature 8: Rule Violations...             [OK] Calculated

Exporting features to CSV...   [OK] Exported 714 users

VALIDATION STATISTICS
Total users with features:     714
Avg host diversity:            1.250
Avg failure ratio:             0.150
Avg shared device risk:        2.100
Users with HIGH privilege:     30
Users with 3+ rule violations: 75
Max connectivity score:        0.002
```

#### CSV Output
```
data/phase4_graph_features.csv

user_id    username    host_diversity  critical_server_ratio  failure_ratio  ...  rule_violations
U_xxx      user1       1.25            0.5                    0.1            ...  2
U_yyy      user2       0.8             0.0                    0.95           ...  7
```

---

### **Phase 5: Anomaly Detection** (20-30 minutes)

#### Execution
```bash
python neo4j_phase5_anomaly.py
```

#### Expected Output
```
PHASE 5: MULTI-METHOD ANOMALY DETECTION

Training Isolation Forest...          [OK] IF: Detected ~36 anomalies (5%)
Training Local Outlier Factor...      [OK] LOF: Detected ~35 anomalies (5%)
Training Elliptic Envelope...         [OK] EE: Detected ~35 anomalies (5%)

Creating ensemble anomaly score...    [OK] Ensemble voting complete
                                      Anomalies detected: ~50-60

Analyzing results...

Anomaly Score Distribution:
  Mean:    0.3200
  Median:  0.1500
  Std Dev: 0.3100
  Min:     0.0000
  Max:     0.9800

Severity Distribution:
  CRITICAL:  15-20
  HIGH:      30-40
  MEDIUM:    50-70
  LOW:       100-150
  NORMAL:    450-550

Top 10 Most Anomalous Users:
  U_aaa    0.9500  CRITICAL  3 votes  7 rules
  U_bbb    0.8800  CRITICAL  3 votes  6 rules
  U_ccc    0.7600  HIGH      2 votes  5 rules
  ...

Saving results...  [OK] Saved full results
                   [OK] Saved anomalies summary
Saving models...   [OK] Saved to models/
```

#### Output Files
```
data/phase5_anomaly_results.csv       - All 714 users with all scores
data/phase5_anomalies_summary.csv     - Anomalous users only
models/isolation_forest_model.pkl     - Trained models
models/lof_model.pkl
models/elliptic_envelope_model.pkl
models/feature_scaler.pkl
```

---

### **Phase 6: Comprehensive Reporting** (5 minutes)

#### Execution
```bash
python neo4j_phase6_reporting.py
```

#### Expected Output
```
PHASE 6: RESULTS & COMPREHENSIVE REPORTING

Loading anomaly results...      [OK] Loaded 714 users
Generating text report...       [OK] Saved to output/
Generating JSON report...       [OK] Saved detailed evidence
Generating statistics...        [OK] Saved summary

PHASE 6 SUMMARY

Total Users: 714
Anomalies:   50-60

Severity Distribution:
  CRITICAL: 15
  HIGH:     35
  MEDIUM:   60
  LOW:      120
  NORMAL:   484

🎉 PIPELINE COMPLETE!

Generated Files:
  1. data/phase4_graph_features.csv
  2. data/phase5_anomaly_results.csv
  3. data/phase5_anomalies_summary.csv
  4. output/anomaly_detection_report.txt
  5. output/anomaly_detection_detailed.json
  6. output/anomaly_statistics.json
  7. models/ (trained models)
```

#### Output Files
```
output/anomaly_detection_report.txt      - Human-readable report
output/anomaly_detection_detailed.json   - Detailed evidence for each anomaly
output/anomaly_statistics.json           - Summary statistics
```

---

## Quick Start Command

Execute all phases in sequence:

```bash
#!/bin/bash

echo "Phase 2: Neo4j Ingestion..."
python neo4j_ingest_phase2.py

echo -e "\n\nPhase 3: Rule-Based Knowledge..."
python neo4j_phase3_rules.py

echo -e "\n\nPhase 4: Feature Extraction..."
python neo4j_phase4_features.py

echo -e "\n\nPhase 5: Anomaly Detection..."
python neo4j_phase5_anomaly.py

echo -e "\n\nPhase 6: Reporting..."
python neo4j_phase6_reporting.py

echo -e "\n\n✅ PIPELINE COMPLETE!"
```

Save as `run_pipeline.sh` and execute:
```bash
bash run_pipeline.sh
```

---

## Troubleshooting

| Phase | Issue | Solution |
|-------|-------|----------|
| 2 | Connection refused | Check Neo4j: `docker ps` |
| 2 | Out of memory | Increase Neo4j memory, reduce batch size |
| 3 | Rules not calculating | Check Neo4j connectivity |
| 4 | CSV export empty | Verify Phase 3 completed |
| 5 | sklearn import error | `pip install scikit-learn` |
| 6 | Output directory missing | Create `output/` directory |

---

## Key Results

### Anomaly Detection Results
- **Total users analyzed:** 714
- **Anomalies detected:** ~50-60 (7-8%)
  - CRITICAL: 15-20
  - HIGH: 30-40
  - MEDIUM: 50-70
  - LOW: 100-150

### Methods Used
1. **Isolation Forest** - Isolation-based anomaly detection
2. **Local Outlier Factor** - Density-based anomaly detection
3. **Elliptic Envelope** - Covariance-based anomaly detection
4. **Rule-Based Scoring** - Domain knowledge violations

### Features Extracted (8 total)
1. Host Diversity Score
2. Critical Server Access Ratio
3. Failed Login Ratio
4. Shared Device Risk Score
5. IP Network Risk Score
6. Privilege Level
7. Graph Connectivity (Degree Centrality)
8. Rule Violations Count

---

## Next Steps

1. **Review findings** in `output/anomaly_detection_report.txt`
2. **Investigate top anomalies** in `output/anomaly_detection_detailed.json`
3. **Implement recommendations** based on severity
4. **Monitor ongoing** using trained models in `models/`

---

## Contact & Support

For questions or issues:
- Check Phase-specific documentation (PHASE{2-6}_*.md)
- Review logs in console output
- Validate Neo4j data: Neo4j Browser at http://localhost:7474

