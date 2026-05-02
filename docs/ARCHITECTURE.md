# Architecture: Graph-Based Anomaly Detection for Active Directory

## Overview

This document describes the novel architecture for Active Directory anomaly detection using Neo4j knowledge graphs combined with machine learning.

## Problem Statement

**Previous Approach (Problematic):**
```
AD Log → Preprocessing → Behavioral Features → Isolation Forest → Neo4j (Visualization)
```

**Issue:** Neo4j used only as visualization/storage, not as core intelligence component. Isolation Forest juga tidak menghasilkan penjelasan — hanya label anomali tanpa konteks KENAPA.

---

## Proposed Architecture (Novel)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    AD ANOMALY DETECTION PIPELINE                         │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  [1] AD LOG DATA          [2] NEO4J KNOWLEDGE GRAPH                     │
│  ─────────────────────────────────────────────────────                  │
│  • User ID                • User Node                                    │
│  • Hostname               • Hostname Node                                │
│  • Server                 • Server Node                                  │
│  • Event Type             • IP Address Node                              │
│  • Timestamp              • Group Node                                   │
│  • IP Address             • TimeWindow Node                              │
│  • Group/Role             • Event Node                                   │
│                           │                                              │
│                           ├─ LOGIN_FROM relationship                     │
│                           ├─ ACCESS relationship                         │
│                           ├─ FAILED_LOGIN relationship                   │
│                           ├─ USED_IP relationship                        │
│                           ├─ MEMBER_OF relationship                      │
│                           └─ CONNECTED_FROM relationship                 │
│                                                                          │
│              ↓ CORE INTELLIGENCE (Graph-based)                          │
│                                                                          │
│  [3] RULE-BASED KNOWLEDGE ENGINE                                        │
│  ────────────────────────────────                                       │
│  Rule 1: Normal login baseline (specific hostnames)                     │
│  Rule 2: Business hours pattern (8 AM - 6 PM, weekdays)               │
│  Rule 3: Shared device detection (devices used by many users)          │
│  Rule 4: Uncommon server access (critical servers)                     │
│  Rule 5: Failed login spike (brute force detection)                    │
│  Rule 6: Unusual IP address (non-office networks)                      │
│  Rule 7: After-hours privileged access (sensitive timing)              │
│                                                                          │
│              ↓ CONTEXT-AWARE FEATURES                                   │
│                                                                          │
│  [4] GRAPH FEATURE EXTRACTION                                           │
│  ──────────────────────────────                                         │
│  Feature 1: Host Diversity Score                                        │
│  Feature 2: Critical Server Access Ratio                                │
│  Feature 3: Failed Login Ratio                                          │
│  Feature 4: Shared Device Risk Score                                    │
│  Feature 5: IP Network Risk Score                                       │
│  Feature 6: Privilege Escalation Risk                                   │
│  Feature 7: Graph Connectivity (Degree Centrality)                      │
│  Feature 8: Rule Violation Count                                        │
│                                                                          │
│              ↓ MACHINE LEARNING (Graph-informed)                        │
│                                                                          │
│  [5] ISOLATION FOREST ANOMALY DETECTION                                 │
│  ────────────────────────────────────────                               │
│  Input: Graph-based features (8 dimensions)                             │
│  Method: Ensemble unsupervised (IF + LOF + Elliptic Envelope)          │
│  Output: Anomaly scores + severity classification + ensemble voting     │
│                                                                          │
│              ↓ EXPLAINABILITY LAYER                                     │
│                                                                          │
│  [5.5] SHAP EXPLAINABILITY                                              │
│  ──────────────────────────                                             │
│  Method: TreeExplainer (native Isolation Forest support)                │
│  Per-user SHAP values for all 8 features                                │
│  Output: Feature contribution score per anomalous user                  │
│  Example: "failure_ratio (+0.31), ip_network_risk (+0.24), ..."        │
│                                                                          │
│              ↓ INTERPRETABLE RESULTS                                    │
│                                                                          │
│  [6] ANOMALY DETECTION OUTPUT                                           │
│  ─────────────────────────────────                                      │
│  • Anomaly Score (continuous)                                           │
│  • Severity Level (CRITICAL, HIGH, MEDIUM, LOW)                        │
│  • Reasoning (which rules triggered, which features anomalous)          │
│  • SHAP Values (quantified feature contributions per user)              │
│  • Graph Evidence (relationships that contributed)                      │
│  • Audit Trail (calculation chain, references)                          │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Key Design Principles

### 1. **Neo4j as Core Intelligence (Not Visualization)**

Neo4j serves as:
- **Knowledge Base**: Stores structured relationships between AD entities
- **Feature Engine**: Extracts meaningful features from graph structure
- **Rule Engine**: Implements domain rules with full context
- **Audit Trail**: Maintains traceable calculation history

### 2. **Multi-Stage Feature Engineering**

```
Stage 1: Raw Data Collection
  ↓
Stage 2: Graph Ingestion (Neo4j)
  ↓
Stage 3: Rule-Based Context (Domain Intelligence)
  ↓
Stage 4: Graph Feature Extraction (Relationship Metrics)
  ↓
Stage 5: ML-Ready Features (Isolation Forest Input)
  ↓
Stage 5.5: SHAP Explainability (Feature Contribution per User)
  ↓
Stage 6: Anomaly Detection (With Full Traceability + Explanation)
```

### 3. **Traceable & Auditable**

Every anomaly detection decision includes:
- Calculation formula
- Data sources
- Rule triggers
- Academic references
- Confidence scores

### 4. **Domain Knowledge Integration**

Rules are not arbitrary thresholds but based on:
- AD security best practices
- Organization-specific baselines
- Behavioral analysis literature
- Graph-based security research

---

## Component Details

### Component 1: AD Log Data

**Source**: Active Directory audit logs (Windows Event Viewer)

**Required Fields**:
- `user_id`: User identifier (e.g., U001)
- `hostname`: Source device (e.g., PC01, LAPTOP-XYZ)
- `server`: Target server/resource (e.g., AD01, FILE_SERVER)
- `event_type`: Activity type (LOGIN, FAILED_LOGIN, ACCESS, LOGOUT, PASSWORD_CHANGE)
- `timestamp`: Event datetime (ISO 8601 format)
- `ip_address`: Source IP address (e.g., 192.168.1.101)
- `group_role`: User's group membership (e.g., DOMAIN_USERS, ADMINS)

**Data Quality Requirements**:
- No null user_id or timestamp
- Valid IP address format
- Event type from predefined enum
- Timestamp should be chronologically consistent

---

### Component 2: Neo4j Knowledge Graph

**Node Types** (7 types):
1. `User` - AD user account
2. `Hostname` - Source device/computer
3. `Server` - Target resource/server
4. `IPAddress` - Network IP address
5. `Group` - User group/role
6. `TimeWindow` - Temporal context (hour, day)
7. `Event` - Audit event record

**Relationship Types** (7 types):
1. `LOGIN_FROM` - User login from hostname
2. `ACCESS` - User/Device access to server
3. `FAILED_LOGIN` - Failed login attempt
4. `USED_IP` - Hostname using IP address
5. `CONNECTED_FROM` - User connection from IP
6. `MEMBER_OF` - User in group
7. `ACCESSED_AT` - Event temporal context

**Graph Metrics**:
- Degree Centrality: Number of relationships per node
- Betweenness Centrality: How often node is in shortest paths
- Community Detection: Identify clusters of related entities
- Path Analysis: Detect attack chains

---

### Component 3: Rule-Based Knowledge Engine

**7 Domain Rules** implemented in Cypher:

| Rule ID | Name | Description | Threshold |
|---------|------|-------------|-----------|
| R001 | Normal Login Hosts | User logs in from specific hostnames | Deviation > 3 hosts |
| R002 | Business Hours Pattern | Login during business hours (8 AM - 6 PM, weekdays) | Off-hours > 10% |
| R003 | Shared Device Detection | Device used by multiple users | Users > 5 per device |
| R004 | Uncommon Server Access | Access to servers user doesn't normally access | Critical server access |
| R005 | Failed Login Spike | Sudden increase in failed attempts | > 10 failures in 1 hour |
| R006 | Unusual IP Address | Login from non-standard IP ranges | Non-office IP + VPN=false |
| R007 | After-Hours Privileged Access | High-privilege access outside business hours | Privilege=HIGH + Off-hours |

**Rule Execution**:
- Rules evaluated for each user
- Violations stored as properties on User node
- Context maintained (threshold, status, rule_ref)
- Anomaly flags aggregated

---

### Component 4: Graph Feature Extraction

**8 Graph-Derived Features**:

| Feature | Type | Calculation | Interpretation |
|---------|------|-------------|-----------------|
| Host Diversity | Numeric | Unique hosts / total logins | Host access concentration |
| Critical Server Access | Count | # of critical servers accessed | Privilege escalation risk |
| Failed Login Ratio | Ratio | Failed logins / total logins | Brute force/account compromise |
| Shared Device Risk | Count | # of high-usage shared devices | Shared credential risk |
| IP Network Risk | Ratio | Unusual IPs / total IPs | Non-standard network usage |
| Privilege Level | Categorical | User's max group privilege | Access control level |
| Graph Connectivity | Numeric | Degree centrality in graph | Activity intensity |
| Rule Violations | Count | Number of triggered rules | Domain rule compliance |

**Output Format**: CSV table with one row per user, ready for Isolation Forest

---

### Component 5: Isolation Forest Anomaly Detection

**Algorithm**: Ensemble-based anomaly detection (3 methods)

**Input**: 8 graph-derived features (normalized)

**Methods**:

- **Isolation Forest (IF)**: Primary — isolates anomalies via random partitioning
- **Local Outlier Factor (LOF)**: Detects density-based local anomalies
- **Elliptic Envelope (EE)**: Identifies outliers via robust covariance

**Ensemble Voting**:

- User flagged anomalous if 2+ methods agree, OR final score > 0.75
- Final score = 60% ensemble votes + 40% rule violations

**Parameters (IF)**:

- Contamination: 0.05 (expect 5% anomalies)
- Estimators: 100 decision trees
- Random State: 42 (reproducible)

**Output**:

- Anomaly Score: Continuous value (0–1, higher = more anomalous)
- Binary Classification: Anomaly vs. Normal
- Ensemble Votes: How many methods flagged the user (0–3)
- Severity: CRITICAL / HIGH / MEDIUM / LOW / NORMAL

**Why Isolation Forest?**

- Unsupervised (no labeled training data needed)
- Efficient with many features
- Detects novel patterns (not just rule violations)
- Compatible with SHAP TreeExplainer (native support)

---

### Component 5.5: SHAP Explainability

**Purpose**: Explain WHY each user was flagged as anomalous

**Method**: `shap.TreeExplainer` — native support for Isolation Forest (tree-based)

**Input**: Trained Isolation Forest model + 8 graph features per user

**Output per anomalous user**:
```
User: john.doe  |  Anomaly Score: 0.87  |  Severity: CRITICAL

SHAP Contributions:
  failure_ratio          +0.31  ← paling dominan
  ip_network_risk        +0.24
  host_diversity         +0.18
  rule_violations        +0.12
  shared_device_risk     +0.08
  privilege_level        +0.05
  critical_server_ratio  +0.02
  connectivity           -0.01
```

**Why SHAP?**

- Transforms black-box IF output into quantified per-feature explanations
- Enables auditor-friendly narrative: "User flagged mainly due to failure_ratio"
- Additive: SHAP values sum to final anomaly score
- Applied only to IF (TreeExplainer) for efficiency on 714 users × 8 features

---

### Component 6: Anomaly Detection Output

**Per-User Anomaly Report Includes**:

1. **Anomaly Score**: Continuous metric (0–1)
2. **Severity Level**: CRITICAL, HIGH, MEDIUM, LOW
3. **Triggered Rules**: Which of 7 rules were violated
4. **SHAP Values**: Quantified contribution of each feature to anomaly score
5. **Reasoning**: Textual explanation of why user is anomalous
6. **Graph Evidence**: Specific relationships that triggered alert
7. **Audit Trail**: Complete calculation history with references

---

## Data Flow Example

**Scenario: Detect User U999 with Anomalous Behavior**

### Step 1: Raw Event
```
User: U999
Hostname: PC01
Server: SERVER_CRITICAL
Event: ACCESS
Timestamp: 2026-04-30 02:30:00  ← Off-hours!
IP: 192.168.50.50               ← Unusual IP!
Group: USERS                    ← Non-admin
```

### Step 2: Graph Ingestion
```cypher
MATCH (u:User {user_id: "U999"})-[r:LOGIN_FROM]->(h:Hostname)
MATCH (u)-[a:ACCESS]->(s:Server)
// Graph relationships created/updated
```

### Step 3: Rule Evaluation
```
Rule R002 (Business Hours): VIOLATION
  - Login at 2:30 AM (outside 8 AM - 6 PM)
  
Rule R004 (Uncommon Server): VIOLATION
  - Access to SERVER_CRITICAL (not normal for USERS group)
  
Rule R006 (Unusual IP): VIOLATION
  - IP from 192.168.50.x (non-office range)
  
Rule R007 (After-Hours Privileged): N/A
  - User not high-privilege
```

### Step 4: Feature Extraction
```
host_count: 5                    ← High (normal: 1-3)
critical_server_count: 3         ← High (normal: 0)
failure_rate: 0.95               ← Very high (normal: 0.1)
shared_devices: 5                ← High (normal: 0-2)
unusual_ip_ratio: 1.0            ← All IPs unusual (normal: 0.0)
privilege_flag: 0                ← Low privilege
connectivity_score: 128          ← Very high activity
rule_violations: 3               ← Multiple violations
```

### Step 5: Isolation Forest
```
Features passed to IF model
↓
Computed anomaly score: -0.78    ← Highly anomalous
↓
Binary classification: ANOMALY = -1
```

### Step 6: Final Output
```
User ID: U999
Anomaly Score: -0.78
Severity: CRITICAL

Triggered Rules:
  ✓ R002: Off-hours activity (2:30 AM)
  ✓ R004: Critical server access by non-admin
  ✓ R006: Login from unusual IP (192.168.50.50)

Contributing Features:
  1. failure_rate (95%) - Highest impact
  2. critical_server_count (3 servers)
  3. unusual_ip_ratio (100%)

Reasoning:
  "User U999 exhibits critical anomalies: (1) Multiple failed 
   login attempts (95% failure rate), (2) Access to critical 
   servers from non-admin account, (3) Activity from unusual 
   IP address outside office network, (4) Access during 
   off-business hours (2:30 AM). Combination of factors indicates 
   potential account compromise or malicious activity."

Graph Evidence:
  - (U999)-[ACCESS {timestamp: 2026-04-30 02:30}]->(SERVER_CRITICAL)
  - (U999)-[CONNECTED_FROM {is_unusual: true}]->(IPAddress: 192.168.50.50)
  - 95 failed login events in 24 hours
  
References:
  - Insider Threat Detection (Springer 2025)
  - Cybersecurity Threat Hunting with Neo4j (arXiv 2301.12013)
```

---

## Why This Architecture is Novel

### 1. **Neo4j-First Approach**
- ✅ Graph as primary intelligence, not secondary storage
- ✅ Relationship analysis before ML
- ✅ Domain rules embedded in graph structure
- ❌ Previous work: ML-first with graph visualization

### 2. **Multi-Stage Feature Engineering**
- ✅ Raw data → Graph context → Domain rules → ML features
- ✅ Each stage adds intelligence
- ✅ Traceable decision chain
- ❌ Previous work: Direct data → ML features

### 3. **Graph-Informed Machine Learning**
- ✅ ML uses relationship metrics (not just behavioral stats)
- ✅ Reduced false positives through domain context
- ✅ Better explains anomalies (not black-box)
- ❌ Previous work: Pure behavioral features to pure ML

### 4. **Traceable & Auditable**
- ✅ Every decision has documented calculation chain
- ✅ Academic references for all formulas
- ✅ Rule violations explicitly tracked
- ✅ Confidence scores for all outputs
- ❌ Previous work: Black-box anomaly scores

---

## Comparison with Alternatives

### vs. Pure Rule-Based (If-Else Only)

| Aspect | Pure Rules | Graph + Rules + ML |
|--------|-----------|---|
| Known Patterns | ✅ Excellent | ✅ Excellent |
| Novel Anomalies | ❌ Miss | ✅ Detects |
| Threshold Tuning | ❌ Manual/Tedious | ✅ Automatic Learning |
| False Positives | ❌ High | ✅ Low |
| Adaptation | ❌ Static | ✅ Adaptive |

**Problem with Pure Rules:**
- What if normal user = 15 failures, malicious = 5?
- Rules cannot adapt to normal behavior variance
- Many edge cases difficult to express as rules

### vs. RDBMS (SQL Database)

| Aspect | RDBMS | Neo4j Graph |
|--------|-------|------------|
| Join Cost | Expensive (N joins) | O(1) traversal |
| Pattern Detection | Nested queries | Native patterns |
| Anomaly Context | Data isolation | Rich relationships |
| Graph Algorithms | Must implement | Built-in (centrality, paths) |
| Scalability | Slows with relationships | Scales with relationships |

**Problem with RDBMS:**
- Cannot efficiently query "find users accessing unusual servers from strange IPs"
- Would require complex JOINs
- No built-in graph algorithms

### vs. Excel

| Aspect | Excel | Neo4j |
|--------|-------|-------|
| Data Volume | Max 1M rows | Millions of relationships |
| Pattern Search | Manual/VLOOKUP | Graph queries |
| Real-time Update | Static export | Live data |
| Audit Trail | None | Queryable logs |
| Automation | Macros (unreliable) | Scheduled Cypher jobs |
| Compliance | Hard to audit | Fully traceable |

**Problem with Excel:**
- Cannot handle dynamic streaming AD logs
- No support for relationship-based analysis
- No automation for continuous monitoring

---

## Implementation Phases

### Phase 1: Data Preparation
- Collect AD logs from Event Viewer
- Validate schema (7 required fields)
- Create CSV with clean data

### Phase 2: Neo4j Graph Building
- Create nodes (7 types)
- Create relationships (7 types)
- Ingest data with Cypher

### Phase 3: Rule-Based Knowledge
- Implement 7 domain rules in Cypher
- Store rule violations on User nodes
- Create rule violation flags

### Phase 4: Graph Feature Extraction
- Extract 8 graph-derived features
- Calculate from relationships (centrality, diversity, etc.)
- Export to CSV for ML

### Phase 5: Anomaly Detection (Ensemble)
- Load graph features CSV
- Train Isolation Forest + LOF + Elliptic Envelope
- Ensemble voting: 60% ML + 40% rule violations
- Generate anomaly scores + severity classification

### Phase 5.5: SHAP Explainability

- Apply `shap.TreeExplainer` to trained Isolation Forest
- Calculate SHAP values per user per feature
- Export per-user feature contribution scores
- Identify dominant factor driving each anomaly

### Phase 6: Result Interpretation & Reporting

- Combine IF scores + SHAP values + rule violations
- Generate reasoning explanations with SHAP evidence
- Create human-readable text report
- Create detailed JSON report with full evidence
- Create audit trail

---

## Expected Outcomes

### For Research Paper

1. **Novel Architecture**: Neo4j-centric, not ML-centric
2. **Graph Intelligence**: Relationship-based features, not just behavioral
3. **Domain Integration**: Rules + ML, not pure statistical
4. **Traceability**: Every decision auditable with references

### For Security Operations

1. **Interpretable Results**: Know WHY user is anomalous
2. **Actionable Alerts**: Specific rule violations + contributing features
3. **Reduced False Positives**: Graph context + ML learning
4. **Compliance Ready**: Full audit trail for investigations

---

## References

- Hubbard, D. W., & Seiersen, R. (2009). The FAIR Model. *How to Measure Anything in Cybersecurity Risk*.
- Springer Nature (2025). *Insider Threat Detection Using Behavioural Analysis*. International Journal of Information Security.
- arXiv 2301.12013 (2023). *Cybersecurity Threat Hunting Using Neo4j Graph Database*.
- NIST SP 800-30 Rev. 1. *Guide for Conducting Risk Assessments*.
- MITRE ATT&CK Framework. *Privilege Escalation (TA0004)*.
