# Phase 4: Graph Feature Extraction

## Overview

Extract 8 graph-based features dari Neo4j relationships. Setiap feature dihitung dari graph structure, bukan hanya behavioral statistics.

---

## 8 Graph-Based Features

### **Feature 1: Host Diversity Score**
```
Calculation: unique_hosts / average_hosts_per_user
Range: 0.0 - 5.0
Interpretation: How many different hosts does this user access?
- 0.5: Same host (very low diversity)
- 1.0: Normal (average diversity)
- 3.0+: High diversity (anomalous)
```

**Cypher Query:**
```cypher
MATCH (u:User)-[:LOGIN_FROM]->(h:Hostname)
WITH count(DISTINCT u) as total_users
MATCH (u:User)-[:LOGIN_FROM]->(h:Hostname)
WITH u, count(DISTINCT h) as unique_hosts, total_users
WITH u, unique_hosts, 
     avg(unique_hosts) as avg_unique_hosts
SET u.feature_host_diversity = ROUND(1.0 * unique_hosts / COALESCE(avg_unique_hosts, 1), 4)
RETURN u.user_id, unique_hosts, u.feature_host_diversity
ORDER BY u.feature_host_diversity DESC
```

---

### **Feature 2: Critical Server Access Ratio**
```
Calculation: critical_servers / total_servers_accessed
Range: 0.0 - 1.0
Interpretation: What % of accessed servers are critical?
- 0.0: No critical server access (normal)
- 0.5: 50% critical servers (suspicious)
- 1.0: All servers are critical (highly suspicious)
```

**Cypher Query:**
```cypher
MATCH (u:User)-[:AUTHENTICATED_VIA]->(s:Server)
WITH u, count(DISTINCT s) as total_servers,
     size([s WHERE s.type = 'DOMAIN_CONTROLLER' OR s.criticality IN ['CRITICAL', 'HIGH']]) as critical_count
SET u.feature_critical_server_ratio = CASE 
  WHEN total_servers > 0 THEN ROUND(1.0 * critical_count / total_servers, 4)
  ELSE 0 
END
RETURN u.user_id, total_servers, critical_count, u.feature_critical_server_ratio
ORDER BY u.feature_critical_server_ratio DESC
```

---

### **Feature 3: Failed Login Ratio**
```
Calculation: failed_logins / total_logins
Range: 0.0 - 1.0
Interpretation: How many login attempts fail?
- 0.0: All successful (normal)
- 0.1: 10% failures (slightly suspicious - password issues?)
- 0.5+: 50%+ failures (highly suspicious - brute force or compromised)
```

**Cypher Query:**
```cypher
MATCH (u:User)
OPTIONAL MATCH (u)-[r:LOGIN_FROM]->(h:Hostname)
WITH u, count(r) as total_logins
OPTIONAL MATCH (u)-[r2:FAILED_LOGIN]->(s:Server)
WITH u, total_logins, COALESCE(sum(r2.count), 0) as failed_logins
SET u.feature_failure_ratio = CASE
  WHEN total_logins > 0 THEN ROUND(1.0 * failed_logins / total_logins, 4)
  ELSE 0
END
RETURN u.user_id, total_logins, failed_logins, u.feature_failure_ratio
ORDER BY u.feature_failure_ratio DESC
```

---

### **Feature 4: Shared Device Risk Score**
```
Calculation: sum(users_per_device) / unique_devices
Range: 1.0 - N (higher = more risk)
Interpretation: How many other users share devices with this user?
- 1.0: All devices exclusive to user (low risk)
- 5.0: Average 5 users per device (medium risk)
- 20.0+: Many users per device (high risk - credential sharing)
```

**Cypher Query:**
```cypher
MATCH (u:User)-[:LOGIN_FROM]->(h:Hostname)
WITH u, count(DISTINCT h) as unique_devices,
     sum(h.user_count) as total_device_users
SET u.feature_shared_device_risk = CASE
  WHEN unique_devices > 0 THEN ROUND(1.0 * total_device_users / unique_devices, 4)
  ELSE 1.0
END
RETURN u.user_id, unique_devices, total_device_users, u.feature_shared_device_risk
ORDER BY u.feature_shared_device_risk DESC
```

---

### **Feature 5: IP Network Risk Score**
```
Calculation: unusual_ips / total_ips
Range: 0.0 - 1.0
Interpretation: What % of IPs are unusual/non-office?
- 0.0: All office IPs (low risk)
- 0.3: 30% unusual IPs (medium risk)
- 1.0: All unusual IPs (high risk)
```

**Cypher Query:**
```cypher
MATCH (u:User)-[:CONNECTED_FROM]->(ip:IPAddress)
WITH u, count(DISTINCT ip) as total_ips,
     size([ip WHERE ip.range_category NOT IN ['Office_Network', 'VPN']]) as unusual_count
SET u.feature_ip_network_risk = CASE
  WHEN total_ips > 0 THEN ROUND(1.0 * unusual_count / total_ips, 4)
  ELSE 0
END
RETURN u.user_id, total_ips, unusual_count, u.feature_ip_network_risk
ORDER BY u.feature_ip_network_risk DESC
```

---

### **Feature 6: Privilege Level**
```
Calculation: max(privilege_level) from user groups
Range: Categorical → Numeric
Interpretation: What's the highest privilege level?
- LOW (1): Regular user
- MEDIUM (2): Power user/specialist
- HIGH (3): Administrator
- ADMIN (4): Domain/Enterprise admin
```

**Cypher Query:**
```cypher
MATCH (u:User)-[:MEMBER_OF]->(g:Group)
WITH u, max(CASE 
  WHEN g.privilege_level = 'ADMIN' THEN 4
  WHEN g.privilege_level = 'HIGH' THEN 3
  WHEN g.privilege_level = 'MEDIUM' THEN 2
  ELSE 1
END) as max_privilege
SET u.feature_privilege_level = COALESCE(max_privilege, 1)
RETURN u.user_id, u.feature_privilege_level
ORDER BY u.feature_privilege_level DESC
```

---

### **Feature 7: Graph Connectivity (Degree Centrality)**
```
Calculation: total_relationships / max_possible_relationships
Range: 0.0 - 1.0 (but often 0.0-0.1)
Interpretation: How connected is this user in the graph?
- Low (0.01): Few relationships (normal user)
- Medium (0.05): Many relationships (power user)
- High (0.1+): Extremely connected (admin or anomaly)
```

**Cypher Query:**
```cypher
MATCH (u:User)
OPTIONAL MATCH (u)-[r]-()
WITH u, count(r) as total_relationships
OPTIONAL MATCH ()-[]-()
WITH u, total_relationships, count(*) as total_edges_in_graph
SET u.feature_connectivity = CASE
  WHEN total_edges_in_graph > 0 THEN ROUND(1.0 * total_relationships / total_edges_in_graph, 6)
  ELSE 0
END
RETURN u.user_id, total_relationships, u.feature_connectivity
ORDER BY u.feature_connectivity DESC
LIMIT 50
```

---

### **Feature 8: Rule Violations Count**
```
Calculation: sum of rule violations from Phase 3
Range: 0 - 7
Interpretation: How many domain rules violated?
- 0: No violations (normal)
- 1-2: Minor violations (low risk)
- 3-4: Multiple violations (medium risk)
- 5-7: Many violations (high risk)
```

**Cypher Query:**
```cypher
MATCH (u:User)
SET u.feature_rule_violations = COALESCE(u.rule_violations, 0)
RETURN u.user_id, u.feature_rule_violations
ORDER BY u.feature_rule_violations DESC
```

---

## Feature Extraction Pipeline

### Order of Execution
1. Features 1-7 (graph-based calculations)
2. Feature 8 (rule violations summary)
3. Export to CSV

### CSV Output Format

Expected CSV: `data/phase4_graph_features.csv`

```csv
user_id,username,host_diversity,critical_server_ratio,failure_ratio,shared_device_risk,ip_network_risk,privilege_level,connectivity,rule_violations
U_xxx,username1,1.25,0.5,0.1,2.3,0.2,1,0.0012,2
U_yyy,username2,0.8,0.0,0.95,1.0,1.0,4,0.0018,7
```

### Feature Normalization (for Isolation Forest)

Isolation Forest requires numeric features, preferably normalized:

```python
import pandas as pd
from sklearn.preprocessing import StandardScaler

df = pd.read_csv('data/phase4_graph_features.csv')

feature_cols = [
    'host_diversity', 'critical_server_ratio', 'failure_ratio',
    'shared_device_risk', 'ip_network_risk', 'privilege_level',
    'connectivity', 'rule_violations'
]

# Handle missing values
df[feature_cols] = df[feature_cols].fillna(0)

# Normalize
scaler = StandardScaler()
df_normalized = scaler.fit_transform(df[feature_cols])

# Export for ML
df_ml = pd.DataFrame(
    df_normalized,
    columns=feature_cols
)
df_ml['user_id'] = df['user_id'].values
df_ml.to_csv('data/phase4_features_normalized.csv', index=False)
```

---

## Validation Checklist

After feature extraction:
- [ ] All 714 users have 8 features calculated
- [ ] No null values in feature columns
- [ ] Feature ranges match expected values
- [ ] Can visualize feature distributions
- [ ] Outliers identified and explained

### Sample Validation Queries

```cypher
// Check feature completeness
MATCH (u:User)
RETURN 
  count(*) as total_users,
  count(CASE WHEN u.feature_host_diversity IS NOT NULL THEN 1 END) as has_f1,
  count(CASE WHEN u.feature_critical_server_ratio IS NOT NULL THEN 1 END) as has_f2,
  count(CASE WHEN u.feature_failure_ratio IS NOT NULL THEN 1 END) as has_f3,
  count(CASE WHEN u.feature_shared_device_risk IS NOT NULL THEN 1 END) as has_f4,
  count(CASE WHEN u.feature_ip_network_risk IS NOT NULL THEN 1 END) as has_f5,
  count(CASE WHEN u.feature_privilege_level IS NOT NULL THEN 1 END) as has_f6,
  count(CASE WHEN u.feature_connectivity IS NOT NULL THEN 1 END) as has_f7,
  count(CASE WHEN u.feature_rule_violations IS NOT NULL THEN 1 END) as has_f8
```

---

## Feature Interpretation for Anomaly Detection

| Feature | Low Risk | Medium Risk | High Risk |
|---------|----------|-------------|-----------|
| Host Diversity | <0.8 | 0.8-2.0 | >2.0 |
| Critical Server Ratio | 0.0-0.1 | 0.1-0.5 | >0.5 |
| Failure Ratio | 0.0-0.05 | 0.05-0.2 | >0.2 |
| Shared Device Risk | 1.0-2.0 | 2.0-5.0 | >5.0 |
| IP Network Risk | 0.0-0.2 | 0.2-0.7 | >0.7 |
| Privilege Level | 1 (LOW) | 2-3 (MEDIUM/HIGH) | 4 (ADMIN) |
| Connectivity | <0.01 | 0.01-0.05 | >0.05 |
| Rule Violations | 0 | 1-2 | 3+ |

