# Phase 3: Rule-Based Knowledge Engine

## Overview

Implement 7 domain-specific rules dalam Neo4j Cypher. Setiap rule akan:
1. Evaluate per user
2. Calculate violation status (true/false)
3. Store properties pada User node
4. Provide context untuk Phase 4 features

---

## 7 Domain Rules

### **R001: Normal Login Hosts**
```
Rule: User biasanya login dari hostname tertentu (3-5 hosts)
Violation: Login dari lebih dari 3 unique hosts = ANOMALY
Context: Indicates unusual device access pattern
```

**Cypher Query:**
```cypher
MATCH (u:User)-[:LOGIN_FROM]->(h:Hostname)
WITH u, count(DISTINCT h) as unique_hosts, collect(DISTINCT h.name) as host_list
SET u.rule_R001_unique_hosts = unique_hosts,
    u.rule_R001_hosts = host_list,
    u.rule_R001_violation = CASE WHEN unique_hosts > 3 THEN true ELSE false END,
    u.rule_R001_severity = CASE 
      WHEN unique_hosts > 10 THEN 'HIGH'
      WHEN unique_hosts > 5 THEN 'MEDIUM'
      WHEN unique_hosts > 3 THEN 'LOW'
      ELSE 'NONE'
    END
RETURN u.user_id, unique_hosts, u.rule_R001_violation
ORDER BY unique_hosts DESC
LIMIT 50
```

**Properties Set:**
- `rule_R001_unique_hosts` (Integer): Count of unique hosts
- `rule_R001_hosts` (List): Hostnames accessed
- `rule_R001_violation` (Boolean): Violation flag
- `rule_R001_severity` (String): Severity level

---

### **R002: Business Hours Pattern**
```
Rule: User logs in during business hours (8 AM - 6 PM, weekdays)
Violation: Off-hours logins > 10% = ANOMALY
Context: Indicates unusual access timing
```

**Cypher Query:**
```cypher
MATCH (u:User)-[r:LOGIN_FROM]->(h:Hostname)
WITH u, count(*) as total_logins,
     size([x IN collect(r) WHERE 
           hour(datetime(x.timestamp)) >= 8 
           AND hour(datetime(x.timestamp)) < 18
           AND dayOfWeek(datetime(x.timestamp)) IN [1,2,3,4,5]
     ]) as business_hours_logins
WITH u, total_logins, business_hours_logins,
     ROUND(1.0 * business_hours_logins / total_logins, 4) as business_ratio,
     ROUND(1.0 * (total_logins - business_hours_logins) / total_logins, 4) as off_hours_ratio
SET u.rule_R002_business_ratio = business_ratio,
    u.rule_R002_off_hours_ratio = off_hours_ratio,
    u.rule_R002_violation = CASE WHEN off_hours_ratio > 0.10 THEN true ELSE false END,
    u.rule_R002_severity = CASE
      WHEN off_hours_ratio > 0.50 THEN 'HIGH'
      WHEN off_hours_ratio > 0.25 THEN 'MEDIUM'
      WHEN off_hours_ratio > 0.10 THEN 'LOW'
      ELSE 'NONE'
    END
RETURN u.user_id, business_ratio, off_hours_ratio, u.rule_R002_violation
ORDER BY off_hours_ratio DESC
LIMIT 50
```

**Properties Set:**
- `rule_R002_business_ratio` (Float): % of business hours logins
- `rule_R002_off_hours_ratio` (Float): % of off-hours logins
- `rule_R002_violation` (Boolean): Violation flag
- `rule_R002_severity` (String): Severity level

---

### **R003: Shared Device Detection**
```
Rule: Hostname typically used by 1-3 users
Violation: Hostname used by > 5 users = ANOMALY (shared device)
Context: Indicates device sharing or credential sharing risk
```

**Cypher Query:**
```cypher
MATCH (h:Hostname)<-[:LOGIN_FROM]-(u:User)
WITH h, count(DISTINCT u) as user_count, collect(DISTINCT u.username) as users
SET h.user_count = user_count,
    h.is_shared = CASE WHEN user_count > 5 THEN true ELSE false END

WITH h, user_count, users
MATCH (u:User)-[:LOGIN_FROM]->(h)
WITH u, count(DISTINCT (u)-[:LOGIN_FROM]->()) as hosts_used,
     size([h IN collect(DISTINCT h) WHERE h.user_count > 5]) as shared_device_count
SET u.rule_R003_shared_devices = shared_device_count,
    u.rule_R003_violation = CASE WHEN shared_device_count > 0 THEN true ELSE false END,
    u.rule_R003_severity = CASE
      WHEN shared_device_count > 5 THEN 'HIGH'
      WHEN shared_device_count > 2 THEN 'MEDIUM'
      WHEN shared_device_count > 0 THEN 'LOW'
      ELSE 'NONE'
    END
RETURN u.user_id, shared_device_count, u.rule_R003_violation
ORDER BY shared_device_count DESC
LIMIT 50
```

**Properties Set:**
- `rule_R003_shared_devices` (Integer): Count of shared devices accessed
- `rule_R003_violation` (Boolean): Violation flag
- `rule_R003_severity` (String): Severity level

---

### **R004: Uncommon Server Access**
```
Rule: User accesses servers they normally access
Violation: Access to critical/uncommon servers = ANOMALY
Context: Indicates privilege escalation attempt or unusual access
```

**Cypher Query:**
```cypher
MATCH (u:User)-[r:AUTHENTICATED_VIA]->(s:Server)
WITH u, s, count(*) as access_count
WHERE s.type = 'DOMAIN_CONTROLLER' OR s.criticality IN ['CRITICAL', 'HIGH']

WITH u, count(DISTINCT s) as critical_servers, 
     collect(DISTINCT s.name) as critical_server_names
SET u.rule_R004_critical_servers = critical_servers,
    u.rule_R004_critical_server_list = critical_server_names,
    u.rule_R004_violation = CASE WHEN critical_servers > 0 THEN true ELSE false END,
    u.rule_R004_severity = CASE
      WHEN critical_servers > 5 THEN 'HIGH'
      WHEN critical_servers > 2 THEN 'MEDIUM'
      WHEN critical_servers > 0 THEN 'LOW'
      ELSE 'NONE'
    END
RETURN u.user_id, critical_servers, u.rule_R004_violation
ORDER BY critical_servers DESC
LIMIT 50
```

**Properties Set:**
- `rule_R004_critical_servers` (Integer): Count of critical servers accessed
- `rule_R004_critical_server_list` (List): Server names
- `rule_R004_violation` (Boolean): Violation flag
- `rule_R004_severity` (String): Severity level

---

### **R005: Failed Login Spike**
```
Rule: User has normal failed login baseline
Violation: > 50 failed logins in 1 hour OR > 10 failures in 5 minutes = BRUTE FORCE
Context: Indicates password guessing or compromised account
```

**Cypher Query:**
```cypher
MATCH (u:User)-[r:FAILED_LOGIN]->(s:Server)
WITH u, count(*) as total_failures,
     max(r.count) as max_single_relation_failures

// Check for spike patterns
MATCH (u)-[r:FAILED_LOGIN]->(s:Server)
WITH u, total_failures, max_single_relation_failures,
     size([x IN collect(r) WHERE x.count > 10]) as high_failure_relations

SET u.rule_R005_total_failures = total_failures,
    u.rule_R005_max_spike = max_single_relation_failures,
    u.rule_R005_violation = CASE 
      WHEN total_failures > 50 THEN true
      WHEN max_single_relation_failures > 10 THEN true
      ELSE false 
    END,
    u.rule_R005_severity = CASE
      WHEN total_failures > 500 THEN 'HIGH'
      WHEN total_failures > 100 THEN 'MEDIUM'
      WHEN total_failures > 50 THEN 'LOW'
      ELSE 'NONE'
    END
RETURN u.user_id, total_failures, max_single_relation_failures, u.rule_R005_violation
ORDER BY total_failures DESC
LIMIT 50
```

**Properties Set:**
- `rule_R005_total_failures` (Integer): Total failed logins
- `rule_R005_max_spike` (Integer): Maximum failures in single relation
- `rule_R005_violation` (Boolean): Violation flag
- `rule_R005_severity` (String): Severity level

---

### **R006: Unusual IP Address**
```
Rule: User connects from office/expected IP ranges
Violation: Connection from non-office IP = ANOMALY
Context: Indicates off-network access or VPN usage
```

**Cypher Query:**
```cypher
MATCH (u:User)-[r:CONNECTED_FROM]->(ip:IPAddress)
WITH u, ip, count(*) as connection_count
WHERE ip.range_category NOT IN ['Office_Network', 'VPN']

WITH u, count(DISTINCT ip) as unusual_ips,
     collect(DISTINCT ip.address) as unusual_ip_list,
     sum(connection_count) as total_unusual_connections
SET u.rule_R006_unusual_ips = unusual_ips,
    u.rule_R006_unusual_ip_list = unusual_ip_list,
    u.rule_R006_violation = CASE WHEN unusual_ips > 0 THEN true ELSE false END,
    u.rule_R006_severity = CASE
      WHEN unusual_ips > 5 THEN 'HIGH'
      WHEN unusual_ips > 2 THEN 'MEDIUM'
      WHEN unusual_ips > 0 THEN 'LOW'
      ELSE 'NONE'
    END
RETURN u.user_id, unusual_ips, unusual_ip_list, u.rule_R006_violation
ORDER BY unusual_ips DESC
LIMIT 50
```

**Properties Set:**
- `rule_R006_unusual_ips` (Integer): Count of unusual IPs
- `rule_R006_unusual_ip_list` (List): IP addresses
- `rule_R006_violation` (Boolean): Violation flag
- `rule_R006_severity` (String): Severity level

---

### **R007: After-Hours Privileged Access**
```
Rule: Privileged users access critical resources during business hours
Violation: Critical server access outside 8 AM - 6 PM weekdays = ANOMALY
Context: Indicates possible unauthorized privileged activity
```

**Cypher Query:**
```cypher
MATCH (u:User)-[r:MEMBER_OF]->(g:Group)
WHERE g.privilege_level IN ['HIGH', 'ADMIN']

MATCH (u)-[r2:AUTHENTICATED_VIA]->(s:Server)
WHERE s.type = 'DOMAIN_CONTROLLER' OR s.criticality = 'CRITICAL'
  AND (hour(datetime(r2.timestamp)) < 8 OR hour(datetime(r2.timestamp)) >= 18
       OR dayOfWeek(datetime(r2.timestamp)) NOT IN [1,2,3,4,5])

WITH u, count(DISTINCT s) as off_hours_critical_access,
     collect(DISTINCT s.name) as critical_servers

SET u.rule_R007_off_hours_critical = off_hours_critical_access,
    u.rule_R007_critical_servers = critical_servers,
    u.rule_R007_violation = CASE WHEN off_hours_critical_access > 0 THEN true ELSE false END,
    u.rule_R007_severity = CASE
      WHEN off_hours_critical_access > 5 THEN 'HIGH'
      WHEN off_hours_critical_access > 2 THEN 'MEDIUM'
      WHEN off_hours_critical_access > 0 THEN 'LOW'
      ELSE 'NONE'
    END
RETURN u.user_id, off_hours_critical_access, u.rule_R007_violation
ORDER BY off_hours_critical_access DESC
LIMIT 50
```

**Properties Set:**
- `rule_R007_off_hours_critical` (Integer): Count of off-hours critical accesses
- `rule_R007_critical_servers` (List): Server names
- `rule_R007_violation` (Boolean): Violation flag
- `rule_R007_severity` (String): Severity level

---

## Rule Execution Strategy

### Order of Execution (Dependency)
1. R001, R002, R006 (independent - logon/IP patterns)
2. R003 (depends on host aggregation)
3. R004, R005, R007 (depends on server/auth data)

### Summary Aggregation

After all rules executed, create rule violation summary:

```cypher
MATCH (u:User)
SET u.rule_violations = 
    (CASE WHEN u.rule_R001_violation THEN 1 ELSE 0 END) +
    (CASE WHEN u.rule_R002_violation THEN 1 ELSE 0 END) +
    (CASE WHEN u.rule_R003_violation THEN 1 ELSE 0 END) +
    (CASE WHEN u.rule_R004_violation THEN 1 ELSE 0 END) +
    (CASE WHEN u.rule_R005_violation THEN 1 ELSE 0 END) +
    (CASE WHEN u.rule_R006_violation THEN 1 ELSE 0 END) +
    (CASE WHEN u.rule_R007_violation THEN 1 ELSE 0 END),
    u.max_rule_severity = CASE
      WHEN u.rule_R001_severity = 'HIGH' OR u.rule_R002_severity = 'HIGH' OR u.rule_R003_severity = 'HIGH' 
           OR u.rule_R004_severity = 'HIGH' OR u.rule_R005_severity = 'HIGH' 
           OR u.rule_R006_severity = 'HIGH' OR u.rule_R007_severity = 'HIGH' THEN 'HIGH'
      WHEN u.rule_R001_severity = 'MEDIUM' OR u.rule_R002_severity = 'MEDIUM' OR u.rule_R003_severity = 'MEDIUM'
           OR u.rule_R004_severity = 'MEDIUM' OR u.rule_R005_severity = 'MEDIUM'
           OR u.rule_R006_severity = 'MEDIUM' OR u.rule_R007_severity = 'MEDIUM' THEN 'MEDIUM'
      ELSE 'LOW'
    END

RETURN u.user_id, u.rule_violations, u.max_rule_severity
ORDER BY u.rule_violations DESC
```

---

## Query Validation Checklist

After executing all rules:
- [ ] All users have rule_violations count
- [ ] rule_violations range 0-7
- [ ] Users with violations > 3 marked as HIGH severity
- [ ] Can query: `MATCH (u:User) WHERE u.rule_violations > 2 RETURN u.user_id, u.rule_violations`
- [ ] Can query: `MATCH (u:User) RETURN u.rule_violations, count(u) ORDER BY u.rule_violations DESC`

