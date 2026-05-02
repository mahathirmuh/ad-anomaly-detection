# Rule-Based Knowledge Engine for AD Anomaly Detection

## Overview

This document describes the 7 domain rules that form the **knowledge-based layer** between Neo4j graph and machine learning anomaly detection.

**Purpose**: Embed domain knowledge and security best practices into the graph database to provide context-aware features for Isolation Forest.

---

## Rule Design Principles

### 1. Domain-Grounded
- Based on AD security best practices
- Reflect organizational policies
- Informed by NIST, COBIT, ISO 27001 frameworks

### 2. Queryable in Neo4j
- Implemented as Cypher queries
- Results stored as node/relationship properties
- Efficient graph traversal

### 3. Interpretable
- Clear threshold definitions
- Documented rationale
- Explainable violations

### 4. Actionable
- Generate specific violations
- Identify which users violate which rules
- Provide remediation guidance

---

## Rule 1: Normal Login Baseline

### Concept

**Every user has normal login hostnames they use regularly. Deviation from this baseline indicates anomaly.**

### Definition

```
Normal: User logs in from same 1-3 devices (high concentration)
Anomaly: User suddenly logs in from 5+ different devices (dispersed)
```

### Implementation

```cypher
// R001: Normal Login Hosts
MATCH (u:User)-[r:LOGIN_FROM]->(h:Hostname)
WITH u, count(DISTINCT h) as unique_hosts, collect(DISTINCT h.name) as host_list

SET u.rule_R001_unique_hosts = unique_hosts,
    u.rule_R001_host_list = host_list,
    u.rule_R001_status = CASE 
        WHEN unique_hosts <= 2 THEN 'NORMAL'
        WHEN unique_hosts <= 5 THEN 'MEDIUM'
        ELSE 'ANOMALY'
    END,
    u.rule_R001_threshold = 3,
    u.rule_R001_violation = CASE WHEN unique_hosts > 3 THEN true ELSE false END

RETURN u.user_id, unique_hosts, u.rule_R001_violation
```

### Threshold Rationale

| Unique Hosts | Classification | Justification |
|---|---|---|
| 1-2 | Normal | User works from home or office consistently |
| 3-5 | Medium | User travels or works from multiple locations |
| > 5 | Anomaly | Unusual behavior, possible account compromise |

**Reference**: Best Practice - Users normally access 1-3 known devices daily

---

## Rule 2: Business Hours Pattern

### Concept

**Normal users login during business hours (8 AM - 6 PM, Monday-Friday). Off-hours activity may indicate automated attacks or privilege abuse.**

### Definition

```
Normal: >90% of logins during business hours
Anomaly: >10% of logins outside business hours
```

### Implementation

```cypher
// R002: Business Hours Login Pattern
MATCH (u:User)-[r:LOGIN_FROM]->(h:Hostname)
WITH u, 
     count(*) as total_logins,
     size([x IN collect(r) WHERE 
           hour(datetime(x.timestamp)) >= 8 
           AND hour(datetime(x.timestamp)) < 18 
           AND dayOfWeek(datetime(x.timestamp)) NOT IN [6,7]
     ]) as business_hours_logins

WITH u, total_logins, business_hours_logins,
     ROUND(1.0 * business_hours_logins / total_logins, 4) as business_hours_ratio

SET u.rule_R002_total_logins = total_logins,
    u.rule_R002_business_hours_logins = business_hours_logins,
    u.rule_R002_business_hours_ratio = business_hours_ratio,
    u.rule_R002_off_hours_ratio = ROUND(1.0 - business_hours_ratio, 4),
    u.rule_R002_violation = CASE 
        WHEN business_hours_ratio < 0.9 THEN true 
        ELSE false 
    END,
    u.rule_R002_status = CASE
        WHEN business_hours_ratio >= 0.95 THEN 'NORMAL'
        WHEN business_hours_ratio >= 0.90 THEN 'MEDIUM'
        ELSE 'ANOMALY'
    END

RETURN u.user_id, business_hours_ratio, u.rule_R002_violation
```

### Threshold Rationale

**Business Hours Definition**: 8 AM - 6 PM, Monday-Friday (09:00-18:00 in some regions)

| Off-Hours % | Classification | Justification |
|---|---|---|
| 0-5% | Normal | Occasional after-hours work is normal |
| 5-10% | Medium | Elevated off-hours activity, monitor |
| > 10% | Anomaly | Significant off-hours activity, investigate |

**Reference**: NIST Best Practice - Unusual access times often indicate compromise

---

## Rule 3: Shared Device Detection

### Concept

**High-usage shared devices (many different users) are security risks. Detect users accessing these shared devices.**

### Definition

```
Shared Device: Used by >5 different users
Risk: User accessing high-use shared device increases compromise risk
```

### Implementation

```cypher
// R003: Shared Device Detection
MATCH (h:Hostname)<-[r:LOGIN_FROM]-(u:User)
WITH h, count(DISTINCT u) as user_count, collect(DISTINCT u.user_id) as users

WITH h, user_count, users,
     CASE WHEN user_count > 5 THEN 'HIGH_USAGE_SHARED' 
          WHEN user_count > 2 THEN 'SHARED' 
          ELSE 'PERSONAL' 
     END as device_type

SET h.device_type = device_type,
    h.user_count = user_count,
    h.users_on_device = users,
    h.is_shared = CASE WHEN user_count > 2 THEN true ELSE false END

// Now mark users on shared devices
MATCH (u:User)-[:LOGIN_FROM]->(h:Hostname)
WHERE h.is_shared = true AND h.user_count > 5

WITH u, count(DISTINCT h {is_shared: true, user_count: {gt: 5}}) as shared_devices_count

SET u.rule_R003_shared_devices = shared_devices_count,
    u.rule_R003_violation = CASE WHEN shared_devices_count > 0 THEN true ELSE false END,
    u.rule_R003_risk_level = CASE
        WHEN shared_devices_count >= 3 THEN 'HIGH'
        WHEN shared_devices_count >= 1 THEN 'MEDIUM'
        ELSE 'LOW'
    END

RETURN u.user_id, shared_devices_count, u.rule_R003_violation
```

### Threshold Rationale

| User Count on Device | Device Type | Risk Level |
|---|---|---|
| 1-2 | Personal | Low |
| 3-5 | Shared | Medium |
| > 5 | High-Usage Shared | High |

**Reference**: Security Practice - Shared devices reduce audit trail effectiveness (cannot distinguish which user performed action)

---

## Rule 4: Uncommon Server Access

### Concept

**Users normally access specific server types. Access to unusual servers (especially critical ones) indicates privilege escalation or lateral movement.**

### Definition

```
Normal: User accesses servers consistent with their role
Anomaly: User accesses critical servers (especially for non-admin users)
```

### Implementation

```cypher
// R004: Uncommon Server Access
MATCH (u:User)-[r:ACCESS]->(s:Server)
WITH u, count(DISTINCT s) as servers_accessed, 
     size([s IN collect(s) WHERE s.criticality = 'CRITICAL']) as critical_servers

WITH u, servers_accessed, critical_servers,
     [s IN collect(s) WHERE s.criticality = 'CRITICAL' | s.name] as critical_server_names

SET u.rule_R004_servers_accessed = servers_accessed,
    u.rule_R004_critical_servers = critical_servers,
    u.rule_R004_critical_server_list = critical_server_names,
    u.rule_R004_violation = CASE 
        WHEN critical_servers > 0 AND (u)-[:MEMBER_OF]->(:Group {privilege_level: 'LOW'}) 
        THEN true 
        ELSE false 
    END,
    u.rule_R004_status = CASE
        WHEN critical_servers = 0 THEN 'NORMAL'
        WHEN critical_servers = 1 THEN 'MEDIUM'
        ELSE 'ANOMALY'
    END

RETURN u.user_id, critical_servers, critical_server_names, u.rule_R004_violation
```

### Threshold Rationale

**Critical Servers**: Domain Controllers, Exchange, SQL Databases, Backup Systems

| Access Count | User Type | Status |
|---|---|---|
| 0 | Non-admin | Normal |
| 1 | Admin | Normal |
| > 1 | Non-admin | Anomaly - Privilege Escalation |
| Any | Non-admin user | Anomaly |

**Reference**: MITRE ATT&CK - Privilege Escalation (TA0004), Lateral Movement (TA0008)

---

## Rule 5: Failed Login Spike

### Concept

**Sudden increase in failed login attempts indicates brute force attack, password guessing, or account compromise.**

### Definition

```
Baseline: User has average X failures per day
Spike: > 5X failures in 1-hour window
```

### Implementation

```cypher
// R005: Failed Login Spike
MATCH (u:User)-[r:FAILED_LOGIN]->(s:Server)
WITH u, count(*) as total_failures,
     max(r.timestamp) as last_failure,
     min(r.timestamp) as first_failure

// Calculate average failures per day
WITH u, total_failures, last_failure, first_failure,
     CASE WHEN (duration.inSeconds(first_failure, last_failure).seconds / 86400) > 0 
          THEN total_failures / (duration.inSeconds(first_failure, last_failure).seconds / 86400)
          ELSE 0
     END as avg_failures_per_day

SET u.rule_R005_total_failures = total_failures,
    u.rule_R005_avg_failures_per_day = ROUND(avg_failures_per_day, 2),
    u.rule_R005_last_failure = last_failure,
    u.rule_R005_violation = CASE 
        WHEN total_failures > 10 THEN true
        ELSE false
    END,
    u.rule_R005_status = CASE
        WHEN total_failures <= 2 THEN 'NORMAL'
        WHEN total_failures <= 5 THEN 'MEDIUM'
        WHEN total_failures <= 10 THEN 'HIGH'
        ELSE 'CRITICAL'
    END,
    u.rule_R005_interpretation = CASE
        WHEN total_failures > 50 THEN 'Likely brute force attack'
        WHEN total_failures > 20 THEN 'Possible password guessing'
        WHEN total_failures > 10 THEN 'Elevated failure rate'
        ELSE 'Normal failure rate'
    END

RETURN u.user_id, total_failures, avg_failures_per_day, u.rule_R005_violation
```

### Threshold Rationale

| Failure Count | Time Period | Interpretation | Risk Level |
|---|---|---|---|
| 0-2 | 24 hours | Normal (occasional typos) | Low |
| 3-5 | 24 hours | Elevated (user has password issues) | Medium |
| 6-10 | 24 hours | High (possible compromise) | High |
| > 10 | 1 hour | Critical (brute force attack) | Critical |

**Reference**: NIST SP 800-63B - Authentication Failure Thresholds

---

## Rule 6: Unusual IP Address

### Concept

**Users normally connect from office network or known VPN. Connection from non-standard IP ranges may indicate:
- Account compromise
- Malware infection
- Unauthorized access**

### Definition

```
Normal: Office network (10.x.x.x, 192.168.x.x) or VPN
Unusual: External IP, residential IP, datacenter IP, etc.
```

### Implementation

```cypher
// R006: Unusual IP Address
MATCH (u:User)-[r:CONNECTED_FROM]->(ip:IPAddress)
WITH u, count(DISTINCT ip) as total_ips,
     size([ip IN collect(ip) WHERE ip.range_category = 'Office_Network']) as office_ips,
     size([ip IN collect(ip) WHERE ip.is_vpn = true]) as vpn_ips,
     size([ip IN collect(ip) WHERE ip.range_category != 'Office_Network' AND ip.is_vpn = false]) as unusual_ips,
     collect(ip {address: ip.address, range_category: ip.range_category}) as ip_list

WITH u, total_ips, office_ips, vpn_ips, unusual_ips, ip_list,
     ROUND(1.0 * unusual_ips / total_ips, 4) as unusual_ip_ratio

SET u.rule_R006_total_ips = total_ips,
    u.rule_R006_office_ips = office_ips,
    u.rule_R006_vpn_ips = vpn_ips,
    u.rule_R006_unusual_ips = unusual_ips,
    u.rule_R006_unusual_ip_ratio = unusual_ip_ratio,
    u.rule_R006_ip_list = ip_list,
    u.rule_R006_violation = CASE 
        WHEN unusual_ips > 0 THEN true
        ELSE false
    END,
    u.rule_R006_status = CASE
        WHEN unusual_ip_ratio = 0 THEN 'NORMAL'
        WHEN unusual_ip_ratio <= 0.1 THEN 'MEDIUM'
        ELSE 'ANOMALY'
    END

RETURN u.user_id, unusual_ips, unusual_ip_ratio, ip_list, u.rule_R006_violation
```

### Threshold Rationale

| Unusual IP % | Classification | Action |
|---|---|---|
| 0% | Normal | No action |
| 1-10% | Medium | Monitor for patterns |
| 11-50% | High | Investigate source |
| > 50% | Critical | Account compromise likely |

**Reference**: Insider Threat Detection - Springer 2025

---

## Rule 7: After-Hours Privileged Access

### Concept

**High-privilege users accessing critical systems outside business hours is highest risk pattern. Indicates:**
- Unauthorized privilege escalation
- Lateral movement
- Data exfiltration preparation**

### Definition

```
High-Risk: 
  - User has ADMIN or HIGH privilege
  - Accesses CRITICAL or HIGH importance servers
  - Outside business hours (before 8 AM or after 6 PM, or weekends)
```

### Implementation

```cypher
// R007: After-Hours Privileged Access
MATCH (u:User)-[:MEMBER_OF]->(g:Group)
WHERE g.privilege_level IN ['HIGH', 'ADMIN']

WITH u

MATCH (u)-[a:ACCESS]->(s:Server)
WHERE s.criticality IN ['CRITICAL', 'HIGH']
  AND (hour(datetime(a.timestamp)) < 8 
       OR hour(datetime(a.timestamp)) >= 18 
       OR dayOfWeek(datetime(a.timestamp)) IN [6,7])

WITH u, count(*) as after_hours_access_count,
     collect({server: s.name, timestamp: a.timestamp, criticality: s.criticality}) as access_events

SET u.rule_R007_after_hours_access = after_hours_access_count,
    u.rule_R007_access_events = access_events,
    u.rule_R007_violation = CASE 
        WHEN after_hours_access_count > 0 THEN true
        ELSE false
    END,
    u.rule_R007_status = CASE
        WHEN after_hours_access_count = 0 THEN 'NORMAL'
        WHEN after_hours_access_count = 1 THEN 'MEDIUM'
        ELSE 'CRITICAL'
    END,
    u.rule_R007_risk_justification = 'High-privilege after-hours access to critical systems is highest risk pattern'

RETURN u.user_id, after_hours_access_count, access_events, u.rule_R007_violation
```

### Threshold Rationale

**Highest Risk Pattern**: This rule triggers on ANY after-hours critical access by privileged user

| After-Hours Access Count | Risk Level | Action |
|---|---|---|
| 0 | Low | Normal |
| 1 | High | Review justification |
| > 1 | Critical | Immediate investigation |

**Reference**: 
- DCSA Insider Threat Framework
- NIST SP 800-53 - Account Monitoring and Controls
- Privilege Abuse Case Studies

---

## Rule Summary Table

| Rule ID | Name | Threshold | Violation Criteria | Reference |
|---------|------|-----------|---|---|
| R001 | Normal Login Hosts | 3 hosts | > 3 unique hosts | Best Practice |
| R002 | Business Hours | 90% | < 90% business hours | NIST 2024 |
| R003 | Shared Device | 5 users | Device used by > 5 users | Security Practice |
| R004 | Uncommon Server | Critical | Non-admin accessing critical server | MITRE ATT&CK TA0004 |
| R005 | Failed Login Spike | 10 failures | > 10 failures in 24h | NIST SP 800-63B |
| R006 | Unusual IP | Any | Non-office IP address | Insider Threat Framework |
| R007 | After-Hours Priv Access | 0 | High-priv + Critical server + Off-hours | DCSA Framework |

---

## Rule Storage in Neo4j

Each rule is stored as a separate Neo4j node:

```cypher
CREATE (rule:Rule {
  rule_id: "R001",
  rule_name: "Normal Login Hosts",
  description: "User logs in from specific hostnames",
  threshold_value: 3,
  threshold_unit: "unique_hosts",
  violation_criteria: "unique_hosts > 3",
  
  // Domain knowledge
  domain_principle: "Users normally access 1-3 known devices daily",
  risk_category: "Account Compromise",
  
  // Implementation
  cypher_query: "MATCH (u:User)-[:LOGIN_FROM]->...",
  property_prefix: "rule_R001",
  
  // References
  reference_standard: "Best Practice",
  reference_doc: "AD Security Guidelines",
  reference_year: 2024,
  
  // Metadata
  created_timestamp: datetime(),
  last_updated: datetime(),
  version: "1.0",
  author: "Security Team",
  status: "ACTIVE"
})
```

---

## Rule Evaluation Workflow

```
For each User node:

┌─────────────────────────────────────────────────────────────┐
│ 1. Evaluate Rule R001 (Normal Login Hosts)                 │
│    → Extract unique_hosts                                   │
│    → Check: unique_hosts > 3?                               │
│    → Set: rule_R001_violation = true/false                  │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Evaluate Rule R002 (Business Hours)                      │
│    → Calculate business_hours_ratio                         │
│    → Check: business_hours_ratio < 0.9?                    │
│    → Set: rule_R002_violation = true/false                  │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 3-7. Evaluate Remaining Rules (R003-R007)                  │
│    (Similar pattern for each rule)                          │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 8. Aggregate Rule Violations                                │
│    → Count total violations per user                         │
│    → Collect violation types                                │
│    → Create rule_violation_array                            │
│    → Set anomaly_flags based on violations                  │
└─────────────────────────────────────────────────────────────┘
                           ↓
           (Rules become input features for Isolation Forest)
```

---

## Integration with Isolation Forest

Rules generate features for ML:

```python
# Feature derived from rules
def extract_rule_features(user_node):
    return {
        'rule_R001_violation': user.rule_R001_violation,        # Boolean
        'rule_R002_off_hours_ratio': user.rule_R002_off_hours_ratio,  # Float
        'rule_R003_shared_devices': user.rule_R003_shared_devices,    # Integer
        'rule_R004_critical_servers': user.rule_R004_critical_servers, # Integer
        'rule_R005_total_failures': user.rule_R005_total_failures,    # Integer
        'rule_R006_unusual_ips': user.rule_R006_unusual_ips,        # Integer
        'rule_R007_after_hours_access': user.rule_R007_after_hours_access,  # Integer
        'rule_violation_count': sum([
            user.rule_R001_violation,
            user.rule_R002_violation,
            user.rule_R003_violation,
            user.rule_R004_violation,
            user.rule_R005_violation,
            user.rule_R006_violation,
            user.rule_R007_violation
        ])  # Integer (0-7)
    }
```

---

## Maintenance & Updates

### Rule Tuning

If rule generates too many false positives/negatives:

```cypher
// Example: Adjust Rule R001 threshold from 3 to 5 hosts
MATCH (u:User)
SET u.rule_R001_threshold = 5,  // Changed from 3
    u.rule_R001_violation = CASE 
        WHEN u.rule_R001_unique_hosts > 5 THEN true  // Changed from > 3
        ELSE false 
    END
```

### Adding New Rules

Template for adding Rule R008:

```cypher
CREATE (u:User)-[r:PROPERTY]->()
SET u.rule_R008_<property> = value,
    u.rule_R008_violation = condition,
    u.rule_R008_status = classification
```

---

## References

1. **NIST Special Publications**:
   - SP 800-30 Rev. 1: Guide for Conducting Risk Assessments
   - SP 800-53: Security and Privacy Controls
   - SP 800-63B: Authentication and Lifecycle Management

2. **Insider Threat Detection** (Springer, 2025):
   - User behavioral-based insider threat detection systematic review
   - Journal: International Journal of Information Security
   - DOI: 10.1007/s10207-025-01002-6

3. **MITRE ATT&CK Framework**:
   - TA0004: Privilege Escalation
   - TA0008: Lateral Movement

4. **DCSA Framework**:
   - Insider Threat Program Standards

5. **Microsoft AD Security Best Practices**:
   - Active Directory Security Hardening
   - Privileged Access Workstations (PAW)
