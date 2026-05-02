# Phase 2: Neo4j Knowledge Graph Schema (Adapted for Rich Data)

## Overview

Data mapping dari unified_logon_events.csv (12 columns) ke Neo4j graph structure.

---

## Data Source Columns

```
event_source      → Event source (dc_logon, member_logon, logon_failure)
username          → User identifier
hostname          → Source device/hostname
ip_address        → Source IP address
dc_name           → Domain Controller name (authentication server)
server_name       → Member Server name (alternative auth server)
timestamp         → Event timestamp
success           → Success flag (True/False)
event_type        → Event type (success, failure)
failure_reason    → Reason for failure (if applicable)
domain            → Active Directory domain
logon_service     → Kerberos service used (krbtgt/MBMA, etc)
```

---

## Node Types (7 types)

### 1. User Node
```cypher
CREATE (u:User {
  user_id: "U001",                    // From username
  username: "denny.arifin",           // Actual username
  created_timestamp: datetime()
})
```

**Properties:**
- `user_id` (String, PK): Normalized user identifier
- `username` (String): Actual username from logs
- `created_timestamp` (DateTime): When ingested
- Rule violation properties (added in Phase 3):
  - `rule_R001_violation`, `rule_R002_violation`, etc.

---

### 2. Hostname Node
```cypher
CREATE (h:Hostname {
  hostname_id: "H001",                // Generated ID
  name: "DESKTOP-USER01",             // From hostname column
  ip_address: "10.60.10.100",        // Primary IP if available
  is_shared: false,                   // Calculated in Phase 3
  user_count: 0,                      // Calculated in Phase 3
  created_timestamp: datetime()
})
```

**Properties:**
- `hostname_id` (String, PK): Unique identifier
- `name` (String): Computer name
- `ip_address` (String): Associated IP address
- `is_shared` (Boolean): Whether used by multiple users
- `user_count` (Integer): Number of users accessing

---

### 3. Server Node
```cypher
CREATE (s:Server {
  server_id: "S001",                  // Generated ID
  name: "MBMMRWDC01.mbma.com",       // From dc_name or server_name
  type: "DOMAIN_CONTROLLER",          // DC or MEMBER_SERVER
  domain: "mbma.com",                 // From domain column
  criticality: "CRITICAL",            // Default to CRITICAL for DCs
  created_timestamp: datetime()
})
```

**Properties:**
- `server_id` (String, PK): Unique identifier
- `name` (String): Server FQDN
- `type` (String): DOMAIN_CONTROLLER | MEMBER_SERVER
- `domain` (String): AD domain
- `criticality` (String): CRITICAL | HIGH | MEDIUM | LOW

**Note:** Servers created from `dc_name` OR `server_name` (whichever is present in row)

---

### 4. IPAddress Node
```cypher
CREATE (ip:IPAddress {
  ip_id: "IP001",                     // Generated ID
  address: "10.60.10.100",            // From ip_address column
  range_category: "Office_Network",   // VALIDATED in Phase 1
  is_vpn: false,
  location: "Office",
  organization: "MBMA",
  created_timestamp: datetime()
})
```

**Properties:**
- `ip_id` (String, PK): Unique identifier
- `address` (String): IP address
- `range_category` (String): From IP analysis (Phase 1)
- `is_vpn` (Boolean): Default false
- `location` (String, Optional): Physical location

**Data from Phase 1 IP Analysis:**
- Private vs Public distinction
- Suspicious IPs: 10.60.10.46, 10.60.10.56, 10.60.20.195

---

### 5. Group Node
```cypher
CREATE (g:Group {
  group_id: "G001",                   // Generated ID
  group_name: "DOMAIN_USERS",         // From domain analysis
  privilege_level: "LOW",             // Inferred from context
  created_timestamp: datetime()
})
```

**Properties:**
- `group_id` (String, PK): Unique identifier
- `group_name` (String): AD group name
- `privilege_level` (String): LOW | MEDIUM | HIGH | ADMIN

**Note:** Group derived from `domain` context (not explicit group_role in logs)

---

### 6. Service Node (NEW - specific to Option B)
```cypher
CREATE (svc:Service {
  service_id: "SVC001",               // Generated ID
  service_name: "krbtgt/MBMA",        // From logon_service column
  service_type: "KERBEROS",           // Type of service
  security_context: "AUTHENTICATION", // Context: AUTH, ENCRYPTION, etc
  created_timestamp: datetime()
})
```

**Properties:**
- `service_id` (String, PK): Unique identifier
- `service_name` (String): Service name from logs
- `service_type` (String): KERBEROS | OTHER
- `security_context` (String): Security context

**Purpose:** Capture security context that `logon_service` provides

---

### 7. Event Node
```cypher
CREATE (e:Event {
  event_id: "E001",                   // Generated from row hash
  event_type: "LOGIN",                // From event_type column
  event_source: "dc_logon",           // From event_source column
  timestamp: datetime(),              // From timestamp column
  success: true,                      // From success column
  failure_reason: null,               // From failure_reason column
  created_timestamp: datetime()
})
```

**Properties:**
- `event_id` (String, PK): Unique event identifier
- `event_type` (String): SUCCESS | FAILURE
- `event_source` (String): dc_logon | member_logon | logon_failure
- `timestamp` (DateTime): When event occurred
- `success` (Boolean): Success or failure
- `failure_reason` (String, Optional): Why failed if applicable

**Purpose:** Audit trail - keep every event for traceability

---

## Relationship Types (8 types)

### 1. LOGIN_FROM
```cypher
MATCH (u:User), (h:Hostname)
CREATE (u)-[r:LOGIN_FROM {
  timestamp: datetime(),
  success: true,
  frequency: 1,
  event_source: "dc_logon",      // NEW: preserve source
  first_seen: datetime(),
  last_seen: datetime()
}]->(h)
```

**Properties:**
- `timestamp` (DateTime): When login occurred
- `success` (Boolean): Success or failure
- `frequency` (Integer): Number of occurrences
- `event_source` (String): Source of event
- `first_seen`, `last_seen`: Temporal boundaries

---

### 2. AUTHENTICATED_VIA
```cypher
MATCH (u:User), (s:Server)
CREATE (u)-[r:AUTHENTICATED_VIA {
  timestamp: datetime(),
  success: true,
  failure_reason: null,          // NEW: preserve failure context
  frequency: 1,
  first_seen: datetime(),
  last_seen: datetime()
}]->(s)
```

**Properties:**
- `timestamp` (DateTime): Authentication timestamp
- `success` (Boolean): Authentication success/failure
- `failure_reason` (String, Optional): Why failed
- `frequency` (Integer): Count of authentications
- `first_seen`, `last_seen`: Temporal boundaries

**Purpose:** Distinguish from generic ACCESS - specifically for authentication events

---

### 3. FAILED_LOGIN
```cypher
MATCH (u:User), (s:Server)
CREATE (u)-[r:FAILED_LOGIN {
  timestamp: datetime(),
  failure_reason: "Bad password", // NEW: specific reason
  count: 1,
  event_source: "logon_failure", // NEW: source
  last_failure: datetime()
}]->(s)
```

**Properties:**
- `timestamp` (DateTime): When failure occurred
- `failure_reason` (String): Specific failure reason
- `count` (Integer): Number of failures
- `event_source` (String): Source
- `last_failure` (DateTime): Latest failure

**Purpose:** Focused on failed attempts with detailed failure context

---

### 4. CONNECTED_FROM
```cypher
MATCH (u:User), (ip:IPAddress)
CREATE (u)-[r:CONNECTED_FROM {
  timestamp: datetime(),
  frequency: 1,
  event_source: "dc_logon",
  first_seen: datetime(),
  last_seen: datetime()
}]->(ip)
```

**Properties:**
- `timestamp` (DateTime): Connection timestamp
- `frequency` (Integer): Number of connections
- `event_source` (String): Source
- `first_seen`, `last_seen`: Temporal boundaries

---

### 5. USED_IP
```cypher
MATCH (h:Hostname), (ip:IPAddress)
CREATE (h)-[r:USED_IP {
  timestamp: datetime(),
  frequency: 1,
  first_seen: datetime(),
  last_seen: datetime()
}]->(ip)
```

**Properties:**
- `timestamp` (DateTime): Usage timestamp
- `frequency` (Integer): Times used
- `first_seen`, `last_seen`: Temporal boundaries

---

### 6. USED_SERVICE
```cypher
MATCH (u:User), (svc:Service)
CREATE (u)-[r:USED_SERVICE {
  timestamp: datetime(),
  frequency: 1,
  first_seen: datetime(),
  last_seen: datetime()
}]->(svc)
```

**Properties:**
- `timestamp` (DateTime): Service usage timestamp
- `frequency` (Integer): Times used
- `first_seen`, `last_seen`: Temporal boundaries

**Purpose:** Track which Kerberos services users utilize

---

### 7. MEMBER_OF
```cypher
MATCH (u:User), (g:Group)
CREATE (u)-[r:MEMBER_OF {
  since: datetime(),
  created_timestamp: datetime()
}]->(g)
```

**Properties:**
- `since` (DateTime): Membership start
- `created_timestamp` (DateTime): When discovered

---

### 8. REFERENCES
```cypher
MATCH (e:Event), (u:User)
CREATE (e)-[r:REFERENCES {
  timestamp: datetime()
}]->(u)
```

**Purpose:** Link individual events to users for audit trail

---

## Data Mapping Strategy

### CSV Row → Neo4j Nodes & Relationships

**Example Row:**
```
event_source: "dc_logon"
username: "denny.arifin"
hostname: "DESKTOP-USER01"
ip_address: "10.60.10.100"
dc_name: "MBMMRWDC01.mbma.com"
server_name: (null)
timestamp: "2025-06-24 07:02:20"
success: True
event_type: "success"
failure_reason: (null)
domain: "mbma.com"
logon_service: "krbtgt/MBMA"
```

**Creates:**
1. User node: `(u:User {user_id: "U_denny.arifin", username: "denny.arifin"})`
2. Hostname node: `(h:Hostname {hostname_id: "H001", name: "DESKTOP-USER01"})`
3. Server node: `(s:Server {server_id: "S001", name: "MBMMRWDC01.mbma.com", type: "DOMAIN_CONTROLLER"})`
4. IPAddress node: `(ip:IPAddress {ip_id: "IP001", address: "10.60.10.100"})`
5. Service node: `(svc:Service {service_id: "SVC001", service_name: "krbtgt/MBMA"})`
6. Event node: `(e:Event {event_id: "E001", event_source: "dc_logon", ...})`

**Creates Relationships:**
1. `(u)-[LOGIN_FROM]->(h)` with `event_source: "dc_logon"`
2. `(u)-[AUTHENTICATED_VIA]->(s)` with `success: True`
3. `(u)-[CONNECTED_FROM]->(ip)`
4. `(h)-[USED_IP]->(ip)`
5. `(u)-[USED_SERVICE]->(svc)`
6. `(e)-[REFERENCES]->(u)`
7. `(u)-[MEMBER_OF]->(g)` (Group inferred from domain)

---

## Constraints & Indexes

```cypher
// Uniqueness constraints
CREATE CONSTRAINT user_unique IF NOT EXISTS
FOR (u:User) REQUIRE u.user_id IS UNIQUE;

CREATE CONSTRAINT hostname_unique IF NOT EXISTS
FOR (h:Hostname) REQUIRE h.hostname_id IS UNIQUE;

CREATE CONSTRAINT server_unique IF NOT EXISTS
FOR (s:Server) REQUIRE s.server_id IS UNIQUE;

CREATE CONSTRAINT ip_unique IF NOT EXISTS
FOR (ip:IPAddress) REQUIRE ip.ip_id IS UNIQUE;

CREATE CONSTRAINT service_unique IF NOT EXISTS
FOR (svc:Service) REQUIRE svc.service_id IS UNIQUE;

CREATE CONSTRAINT event_unique IF NOT EXISTS
FOR (e:Event) REQUIRE e.event_id IS UNIQUE;

// Indexes for fast lookup
CREATE INDEX user_lookup IF NOT EXISTS FOR (u:User) ON (u.username);
CREATE INDEX hostname_lookup IF NOT EXISTS FOR (h:Hostname) ON (h.name);
CREATE INDEX server_lookup IF NOT EXISTS FOR (s:Server) ON (s.name);
CREATE INDEX ip_lookup IF NOT EXISTS FOR (ip:IPAddress) ON (ip.address);
CREATE INDEX service_lookup IF NOT EXISTS FOR (svc:Service) ON (svc.service_name);
CREATE INDEX event_lookup IF NOT EXISTS FOR (e:Event) ON (e.event_source, e.timestamp);
```

---

## Key Differences from Original Plan

| Aspect | Original Plan | Option B Adaptation |
|--------|---|---|
| **Nodes** | 7 types | 7 types (added Service, refined) |
| **Relationships** | 7 types | 8 types (added USED_SERVICE) |
| **Event tracking** | Event node optional | Event node mandatory (audit trail) |
| **Failure context** | Not captured | Preserved in FAILED_LOGIN.failure_reason |
| **Service context** | Not captured | Preserved via USED_SERVICE relationship |
| **Authentication path** | Not distinguished | Captured via AUTHENTICATED_VIA properties |
| **Relationship properties** | Basic | Enhanced with failure_reason, event_source |

---

## Ready for Phase 2 Implementation

Next steps:
1. Install Neo4j (Docker recommended)
2. Create schema (constraints + indexes)
3. Write ingestion script (CSV → Neo4j)
4. Validate ingestion (count nodes/relationships)
5. Run sample queries to verify graph structure
