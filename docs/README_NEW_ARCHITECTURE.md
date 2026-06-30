# TDAS-AdAudit v3: Graph-Based Active Directory Anomaly Detection

## 🎯 Project Overview

This project implements a **novel, graph-centric architecture** for detecting anomalous Active Directory administrator behavior using:

1. **Neo4j Knowledge Graph** - Relationship intelligence at core
2. **Rule-Based Knowledge** - Domain expertise formalized
3. **Graph Feature Engineering** - Relationship metrics as ML input
4. **Isolation Forest** - Unsupervised anomaly detection
5. **Complete Traceability** - Full audit trail with academic references

---

## 📚 Documentation Structure

This project includes comprehensive markdown documentation organized by topic:

### 1. **[ARCHITECTURE.md](ARCHITECTURE.md)** 📐
**Main reference for understanding the design**

- Complete system architecture with diagrams
- Data flow walkthrough with real examples
- Key design principles
- Component responsibilities
- Comparison with alternatives
- Why this architecture is novel

**Read this first if you want to understand:** How the system works and why

---

### 2. **[DATA_SCHEMA.md](DATA_SCHEMA.md)** 📊
**Data structures and formats**

- AD Log CSV schema (7 required fields)
- Neo4j node types and properties (7 node types)
- Neo4j relationship types and properties (7 relationship types)
- Sample data with realistic examples
- Data quality rules and validation
- Query examples

**Read this when:** Setting up data collection or Neo4j graph

---

### 3. **[RULE_BASED_KNOWLEDGE.md](RULE_BASED_KNOWLEDGE.md)** 📋
**Domain knowledge engine**

- 7 domain rules with detailed specifications
- Threshold definitions with justification
- Cypher implementation for each rule
- Rule evaluation workflow
- Integration with Isolation Forest
- References from academic literature

**Read this when:** Understanding security rules or tuning thresholds

---

### 4. **[JUSTIFICATION.md](JUSTIFICATION.md)** ✅
**Technical justifications and advisor feedback**

- **Why Neo4j (not RDBMS)?** - Relationship intelligence
- **Why Neo4j (not Excel)?** - Streaming data and automation
- **Why not pure rules?** - Adaptability and novel detection
- **Why this architecture is novel** - 4 key contributions
- Detailed comparisons with alternatives
- Addresses common advisor concerns

**Read this when:** Defending your architecture to advisors

---

### 5. **[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)** ⚙️
**Step-by-step implementation (6 phases)**

**Phase 1: Data Preparation**
- Collect AD audit logs
- Create validated CSV
- Generate sample data

**Phase 2: Neo4j Knowledge Graph**
- Neo4j setup
- Create schema
- Ingest data
- Verify nodes & relationships

**Phase 3: Rule-Based Knowledge**
- Implement all 7 rules
- Store rule violations
- Create rule properties

**Phase 4: Graph Feature Extraction**
- Extract 8 graph-based features
- Calculate metrics
- Export to CSV

**Phase 5: Isolation Forest**
- Load features
- Train model
- Generate anomaly scores
- Classify severity

**Phase 6: Results & Validation**
- Generate reports
- Validate results
- Check quality

**Read this when:** Actually implementing the system

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    GRAPH-BASED ANOMALY DETECTION                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  [1] AD LOG DATA              →  [2] NEO4J KNOWLEDGE GRAPH         │
│  • 7 required fields             • 7 node types                     │
│  • Validated CSV                 • 7 relationship types             │
│  • Streaming ingestion           • Rich property metadata           │
│                                  • Core intelligence engine         │
│                             ↓                                       │
│                   [3] RULE-BASED KNOWLEDGE                          │
│                   • 7 domain rules (R001-R007)                     │
│                   • Formal thresholds                               │
│                   • Academic references                             │
│                   • Stored as node properties                       │
│                             ↓                                       │
│                   [4] GRAPH FEATURE EXTRACTION                      │
│                   • 8 relationship-based features                   │
│                   • Host diversity, criticality, connectivity       │
│                   • Rule violation counts                           │
│                   • Exported as CSV for ML                          │
│                             ↓                                       │
│                   [5] ISOLATION FOREST                              │
│                   • Unsupervised anomaly detection                  │
│                   • Graph-informed features                         │
│                   • Anomaly scores + confidence                     │
│                             ↓                                       │
│              [6] INTERPRETABLE RESULTS                              │
│              • Anomaly score + severity                             │
│              • Triggered rules with evidence                        │
│              • Contributing features                                │
│              • Complete audit trail with references                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔑 Key Innovation

**Previous Approach** (problematic):
```
Data → Features → ML → Neo4j (visualization only)
```

**Novel Approach** (this project):
```
Data → NEO4J GRAPH → Rules → Features → ML
       ↑─────────────────────────────↑
          Core Intelligence Engine
```

**Why it matters:**
- ✅ Graph relationships are primary feature source
- ✅ Domain rules embedded in graph structure
- ✅ ML informed by relationship intelligence
- ✅ Every decision traceable and auditable

---

## 📊 Data Structures

### Active Directory Log (CSV)

```
7 Required Fields:
┌──────────────┬──────────────┬──────────────┬──────────────┐
│ user_id      │ hostname     │ server       │ event_type   │
├──────────────┼──────────────┼──────────────┼──────────────┤
│ timestamp    │ ip_address   │ group_role   │              │
└──────────────┴──────────────┴──────────────┴──────────────┘

Example: U001,PC01,AD01,LOGIN,2026-04-30T08:15:30Z,192.168.1.101,DOMAIN_USERS
```

### Neo4j Graph Model

```
7 Node Types:  User, Hostname, Server, IPAddress, Group, TimeWindow, Event
7 Rel Types:   LOGIN_FROM, ACCESS, FAILED_LOGIN, USED_IP, MEMBER_OF, 
               CONNECTED_FROM, ACCESSED_AT

Graph Example:
(User:U001)-[LOGIN_FROM {timestamp}]->(Hostname:PC01)
          -[MEMBER_OF]->(Group:DOMAIN_USERS)
(User:U001)-[ACCESS]->(Server:AD01)
(Hostname:PC01)-[USED_IP]->(IPAddress:192.168.1.101)
```

### Graph-Based Features

```
8 Features (extracted from relationships):
1. Host Diversity - unique hosts per user
2. Critical Server Access - access to critical resources
3. Failed Login Ratio - proportion of failed attempts
4. Shared Device Risk - access to high-usage shared devices
5. IP Network Risk - unusual IP connections
6. Privilege Level - user's privilege from groups
7. Graph Connectivity - degree centrality
8. Rule Violations - count of triggered rules
```

---

## 🎓 For Your Thesis/Paper

### Title (final — paper IJIES)

> "Explainable Anomaly Detection in Active Directory: Integrating a Rule-Based Knowledge Engine, Ensemble Learning, and SHAP for Human-Readable Reasoning"

### Key Novelties to Highlight

1. **Neo4j-Centric Architecture**
   - Graph relationships are primary intelligence source
   - Not just visualization/storage
   - Enables graph algorithms native to Neo4j

2. **Formal Rule-Based Knowledge Integration**
   - 7 rules with documented thresholds
   - Academic references for each rule
   - Cypher implementations stored in graph
   - Version control and audit trails

3. **Graph-Informed Feature Engineering**
   - 8 relationship-based features
   - Structural metrics (centrality, connectivity)
   - Domain context from rules
   - Not just behavioral statistics

4. **Complete Traceability & Interpretability**
   - Every anomaly decision explainable
   - Triggered rules explicitly shown
   - Contributing features identified
   - Full calculation chain documented

---

## 🔍 Quick Start

### 1. Read First
- [ ] **ARCHITECTURE.md** - Understand the design
- [ ] **JUSTIFICATION.md** - Defend your approach

### 2. Setup Phase
- [ ] Follow **IMPLEMENTATION_GUIDE.md** Phase 1-2
- [ ] Prepare AD logs
- [ ] Create Neo4j knowledge graph

### 3. Implementation
- [ ] Follow **IMPLEMENTATION_GUIDE.md** Phase 3-5
- [ ] Implement rules
- [ ] Extract features
- [ ] Train Isolation Forest

### 4. Reference
- [ ] Check **DATA_SCHEMA.md** for field specifications
- [ ] Check **RULE_BASED_KNOWLEDGE.md** for rule details

---

## 📖 References Used

### Academic Papers

1. **Insider Threat Detection (Springer 2025)**
   - Title: *Insights into user behavioral-based insider threat detection: systematic review*
   - Journal: International Journal of Information Security
   - DOI: 10.1007/s10207-025-01002-6
   - Topics: Behavioral analysis, feature extraction

2. **Cybersecurity Threat Hunting with Neo4j (arXiv 2301.12013)**
   - Title: *Cybersecurity Threat Hunting and Vulnerability Analysis Using a Neo4j Graph Database*
   - Year: 2023
   - Topics: Graph-based security analysis, threat hunting

### Standards & Frameworks

3. **NIST Special Publications**
   - SP 800-30 Rev. 1: Guide for Conducting Risk Assessments
   - SP 800-53: Security and Privacy Controls
   - SP 800-63B: Authentication and Lifecycle Management

4. **MITRE ATT&CK Framework**
   - TA0004: Privilege Escalation
   - TA0008: Lateral Movement

5. **DCSA Insider Threat Framework**
   - Insider threat program standards
   - Risk classification guidelines

6. **ISO/IEC 27001 & COBIT**
   - Information security standards
   - Governance frameworks

---

## 💡 Addressing Advisor Questions

### Q: "Why not just use RDBMS?"
**A:** Graph relationships are core to anomaly detection. Neo4j's native relationship traversal, graph algorithms (centrality, paths, community detection), and pattern matching are essential. SQL cannot efficiently express "find users accessing unusual servers from strange IPs" without complex nested joins. See **JUSTIFICATION.md** for detailed comparison.

### Q: "Why not just Excel?"
**A:** AD logs are continuous streams (7+ million events/year). Excel is static, manual, and doesn't scale. Neo4j enables real-time ingestion, automated rule evaluation, and scheduling. You cannot query relationships in Excel. See **JUSTIFICATION.md** for comparison.

### Q: "Why not pure rule-based (if-else)?"
**A:** Rules alone generate high false positives because thresholds vary by user. ML learns each user's baseline, reducing false positives while detecting novel patterns. Rules provide domain context, ML provides adaptability. Hybrid is stronger. See **JUSTIFICATION.md**.

### Q: "Is Neo4j just visualization?"
**A:** No! Neo4j is the intelligence engine. Rules are implemented in Neo4j. Features are extracted from Neo4j relationships. Graph algorithms run in Neo4j. The previous project's mistake was using Neo4j secondary to ML. We fixed this. See **ARCHITECTURE.md**.

---

## 📁 File Organization

```
tdas_adauditv3/
├── README_NEW_ARCHITECTURE.md      ← You are here
├── ARCHITECTURE.md                 ← System design
├── DATA_SCHEMA.md                  ← Data structures
├── RULE_BASED_KNOWLEDGE.md         ← Security rules
├── JUSTIFICATION.md                ← Why this approach
├── IMPLEMENTATION_GUIDE.md         ← Step-by-step setup
│
├── data/
│   ├── raw_data/
│   │   └── ad_events.csv          ← AD log data
│   ├── clean_data/                ← Processed data
│   └── graph_features.csv         ← ML features
│
├── src/
│   ├── neo4j_ingest.py            ← Graph ingestion
│   ├── implement_rules.py          ← Rule implementation
│   ├── extract_graph_features.py  ← Feature extraction
│   ├── train_isolation_forest.py  ← ML training
│   └── generate_report.py         ← Result reporting
│
├── cypher/
│   ├── 01_create_schema.cypher    ← Graph schema
│   ├── 02_implement_rules.cypher  ← Rule Cypher
│   └── 03_extract_features.cypher ← Feature queries
│
└── output/
    ├── anomaly_detection_results.csv
    ├── anomaly_report.txt
    └── visualizations/
```

---

## 🚀 Next Steps

1. **Study the architecture** - Read ARCHITECTURE.md
2. **Understand the justification** - Read JUSTIFICATION.md  
3. **Learn the data schema** - Read DATA_SCHEMA.md
4. **Review the rules** - Read RULE_BASED_KNOWLEDGE.md
5. **Implement Phase by Phase** - Follow IMPLEMENTATION_GUIDE.md
6. **Test and validate** - Check results
7. **Write your paper** - Use references provided

---

## ❓ Questions?

Refer to the appropriate markdown file:

- **"How does this work?"** → ARCHITECTURE.md
- **"Why this design?"** → JUSTIFICATION.md
- **"How do I set it up?"** → IMPLEMENTATION_GUIDE.md
- **"What are the data structures?"** → DATA_SCHEMA.md
- **"How do the rules work?"** → RULE_BASED_KNOWLEDGE.md

---

## 📝 Version History

- **v3.0** (2026-04-30): Graph-centric architecture with formal rules
- **v2.0** (2026-04-23): Pure ML approach (deprecated)
- **v1.0** (2026-04-01): Initial prototype

---

## 👤 Author
Mahathir Muhammad (mahathirmuhammad02@gmail.com)

## 📅 Last Updated
2026-04-30

---

**Ready to implement? Start with [ARCHITECTURE.md](ARCHITECTURE.md)** 🎯
