# Data Schema: AD Log & Neo4j Graph Model

## Part 1: Active Directory Log Schema

### Source Data Format

**File**: `data/raw_data/ad_events.csv`

**Format**: CSV with 7 required columns

```csv
user_id,hostname,server,event_type,timestamp,ip_address,group_role
```

### Field Specifications

#### 1. `user_id` (String, Required)
- **Description**: Unique user identifier in Active Directory
- **Format**: `U###` (e.g., U001, U999, U1234)
- **Constraints**: 
  - Not null
  - Unique within organization
  - Consistent across all logs
- **Example**: `U001`, `U042`, `U1652`
- **Purpose**: Primary key to identify users
- **Collection**: From AD `sAMAccountName` or custom ID

#### 2. `hostname` (String, Required)
- **Description**: Source device/computer that initiated the event
- **Format**: Device NETBIOS name or FQDN
- **Constraints**:
  - Not null
  - Valid computer name format
  - Consistent naming convention
- **Example**: `PC01`, `LAPTOP-XYZ`, `DESKTOP-USER01`, `WS-FINANCE-001`
- **Purpose**: Identify source device
- **Collection**: From AD computer object or Windows Event Viewer

#### 3. `server` (String, Required)
- **Description**: Target server/resource being accessed
- **Format**: Server NETBIOS name or service identifier
- **Constraints**:
  - Not null
  - Can be AD domain controller, file server, application server, etc.
- **Example**: `AD01`, `FILE_SERVER01`, `EXCHANGE_01`, `APP_SERVER_PROD`
- **Purpose**: Identify target resource
- **Collection**: From Event Viewer `Server` or `ComputerName` field

#### 4. `event_type` (String, Enum, Required)
- **Description**: Type of security event that occurred
- **Format**: Predefined enum values
- **Valid Values**:
  - `LOGIN` - Successful logon
  - `FAILED_LOGIN` - Failed logon attempt
  - `LOGOUT` - Logoff event
  - `PASSWORD_CHANGE` - Password changed
  - `ACCESS` - File/resource access
  - `PERMISSION_CHANGE` - Permission/ACL modified
  - `GROUP_CHANGE` - Group membership change
  - `ACCOUNT_UNLOCK` - Account unlocked
  - `ACCOUNT_LOCK` - Account locked
- **Example**: `LOGIN`, `FAILED_LOGIN`, `ACCESS`
- **Purpose**: Categorize type of activity
- **Collection**: From Windows Event ID mapping:
  - 4624 → LOGIN
  - 4625 → FAILED_LOGIN
  - 4634 → LOGOUT
  - 4723 → PASSWORD_CHANGE
  - etc.

#### 5. `timestamp` (DateTime, Required)
- **Description**: When the event occurred
- **Format**: ISO 8601 format with timezone
- **Constraints**:
  - Not null
  - Valid datetime
  - Chronologically consistent within log
  - UTC recommended for consistency
- **Example**: `2026-04-30T08:15:30Z`, `2026-04-30 02:30:00+00:00`
- **Purpose**: Temporal context for behavior analysis
- **Collection**: From Windows Event Viewer timestamp

#### 6. `ip_address` (String, Required)
- **Description**: Source IP address of the user/device
- **Format**: IPv4 or IPv6 address
- **Constraints**:
  - Not null
  - Valid IP format
  - Can include port if applicable
- **Example**: `192.168.1.101`, `10.0.50.50`, `2001:db8::1`
- **Purpose**: Network location tracking
- **Collection**: From Event Viewer `Client Address` field

#### 7. `group_role` (String, Semicolon-separated, Required)
- **Description**: User's group membership and role(s)
- **Format**: Semicolon-separated list of group names
- **Constraints**:
  - Not null
  - Can contain multiple groups
  - Use organization's standard group names
- **Example**: `DOMAIN_USERS`, `ADMINS;FINANCE_GROUP`, `IT_SUPPORT;DEVELOPERS;POWER_USERS`
- **Purpose**: Identify user's privilege level and department
- **Collection**: From AD `memberOf` attribute

### Sample Data

```csv
user_id,hostname,server,event_type,timestamp,ip_address,group_role
U001,PC01,AD01,LOGIN,2026-04-30T08:15:30Z,192.168.1.101,DOMAIN_USERS
U001,PC01,FILE_SERVER01,ACCESS,2026-04-30T08:20:15Z,192.168.1.101,DOMAIN_USERS
U001,PC01,AD01,FAILED_LOGIN,2026-04-30T08:45:00Z,192.168.1.101,DOMAIN_USERS
U001,PC01,APP_SERVER01,ACCESS,2026-04-30T09:00:00Z,192.168.1.101,DOMAIN_USERS
U002,PC02,AD01,LOGIN,2026-04-30T08:30:00Z,192.168.1.102,DOMAIN_USERS
U002,PC02,FILE_SERVER01,ACCESS,2026-04-30T08:35:00Z,192.168.1.102,DOMAIN_USERS
U003,LAPTOP01,AD01,LOGIN,2026-04-30T08:45:00Z,192.168.2.50,FINANCE_GROUP
U003,LAPTOP01,EXCHANGE01,ACCESS,2026-04-30T09:00:00Z,192.168.2.50,FINANCE_GROUP
U999,PC01,AD01,LOGIN,2026-04-30T02:30:00Z,192.168.50.50,USERS
U999,PC01,SERVER_CRITICAL,ACCESS,2026-04-30T03:00:00Z,192.168.50.50,USERS
U999,PC01,AD01,FAILED_LOGIN,2026-04-30T03:15:00Z,192.168.50.50,USERS
U999,PC01,AD01,FAILED_LOGIN,2026-04-30T03:30:00Z,192.168.50.50,USERS
U999,PC01,AD01,FAILED_LOGIN,2026-04-30T03:45:00Z,192.168.50.50,USERS
```

### Data Quality Rules

1. **No Nulls**: All 7 fields must have values
2. **Valid Enums**: `event_type` must be in predefined list
3. **Valid Datetime**: `timestamp` must parse to valid datetime
4. **Valid IP**: `ip_address` must be valid IPv4 or IPv6
5. **Unique Events**: Combination of (user_id, hostname, server, event_type, timestamp) should be unique
6. **Chronological**: Within each user's log, timestamps should generally move forward

---

## Part 2: Neo4j Knowledge Graph Model

### Node Types

#### 1. User Node

```cypher
CREATE (u:User {
  user_id: "U001",              // Primary identifier
  username: "john.doe",          // Friendly name (optional)
  department: "Finance",         // Organizational unit
  title: "Senior Accountant",    // Job title
  created_timestamp: datetime()  // When ingested
})
```

**Properties**:
- `user_id` (String, Required): Unique identifier
- `username` (String, Optional): Display name
- `department` (String, Optional): Department
- `title` (String, Optional): Job title
- `is_admin` (Boolean, Optional): Admin flag
- `created_timestamp` (DateTime): Creation timestamp

**Purpose**: Represent AD user accounts

---

#### 2. Hostname Node

```cypher
CREATE (h:Hostname {
  hostname_id: "H001",           // Unique ID
  name: "PC01",                  // Computer name
  os: "Windows 10",              // Operating system
  department: "Finance",         // Department
  location: "Office Floor 3",    // Physical location
  is_shared: false,              // Shared device flag
  user_count: 1                  // How many users use it
})
```

**Properties**:
- `hostname_id` (String, Required): Unique identifier
- `name` (String, Required): Computer NETBIOS name
- `os` (String, Optional): Operating system type
- `department` (String, Optional): Department
- `location` (String, Optional): Physical location
- `is_shared` (Boolean): Whether device is shared among users
- `user_count` (Integer): Number of users accessing this device

**Purpose**: Represent user devices/workstations

---

#### 3. Server Node

```cypher
CREATE (s:Server {
  server_id: "S001",             // Unique ID
  name: "AD01",                  // Server name
  type: "DOMAIN_CONTROLLER",     // Server type
  criticality: "CRITICAL",       // CRITICAL, HIGH, MEDIUM, LOW
  owner: "IT_Department",        // Owning department
  created_timestamp: datetime()
})
```

**Properties**:
- `server_id` (String, Required): Unique identifier
- `name` (String, Required): Server NETBIOS name or FQDN
- `type` (String, Enum): Server type (DOMAIN_CONTROLLER, FILE_SERVER, EXCHANGE, APP_SERVER, etc.)
- `criticality` (String, Enum): CRITICAL, HIGH, MEDIUM, LOW
- `owner` (String, Optional): Owning department
- `function` (String, Optional): Server function description

**Purpose**: Represent target servers/resources

---

#### 4. IPAddress Node

```cypher
CREATE (ip:IPAddress {
  ip_id: "IP001",                // Unique ID
  address: "192.168.1.101",      // IP address
  range_category: "Office_Network", // Network category
  is_vpn: false,                 // VPN flag
  location: "Office",            // Physical/logical location
  organization: "HQ"             // Organization unit
})
```

**Properties**:
- `ip_id` (String, Required): Unique identifier
- `address` (String, Required): IP address (IPv4 or IPv6)
- `range_category` (String, Enum): Office_Network, VPN, Remote, Unknown, etc.
- `is_vpn` (Boolean): Whether IP is VPN endpoint
- `is_external` (Boolean): External to organization
- `location` (String, Optional): Physical location
- `organization` (String, Optional): Org unit

**Purpose**: Represent network locations

---

#### 5. Group Node

```cypher
CREATE (g:Group {
  group_id: "G001",              // Unique ID
  group_name: "DOMAIN_USERS",    // Group name
  privilege_level: "LOW",        // LOW, MEDIUM, HIGH, ADMIN
  group_type: "Security",        // Security or Distribution
  scope: "Global"                // Global or Domain Local
})
```

**Properties**:
- `group_id` (String, Required): Unique identifier
- `group_name` (String, Required): Group name
- `privilege_level` (String, Enum): LOW, MEDIUM, HIGH, ADMIN
- `group_type` (String, Enum): Security, Distribution
- `scope` (String, Enum): Global, Domain Local, Universal

**Purpose**: Represent AD groups and roles

---

#### 6. TimeWindow Node (Optional)

```cypher
CREATE (t:TimeWindow {
  hour: 8,                       // Hour of day (0-23)
  day_of_week: 3,                // Day of week (1=Monday, 7=Sunday)
  is_business_hours: true,       // 8 AM - 6 PM flag
  is_weekend: false,             // Weekend flag
  is_holiday: false              // Holiday flag
})
```

**Properties**:
- `hour` (Integer): Hour of day (0-23)
- `day_of_week` (Integer): Day of week (1-7)
- `is_business_hours` (Boolean): 8 AM - 6 PM weekdays
- `is_weekend` (Boolean): Saturday or Sunday
- `is_holiday` (Boolean): Holiday flag

**Purpose**: Temporal context for behavior

---

#### 7. Event Node (Optional)

```cypher
CREATE (e:Event {
  event_id: "E001",              // Unique event ID
  event_type: "LOGIN",           // Event type
  timestamp: datetime(),         // When it occurred
  source: "WINDOWS_EVENT_VIEWER" // Data source
})
```

**Properties**:
- `event_id` (String): Unique event identifier
- `event_type` (String): Type of event
- `timestamp` (DateTime): Event timestamp
- `source` (String): Data source
- `raw_data` (String): Raw event data (optional)

**Purpose**: Audit trail of individual events

---

### Relationship Types

#### 1. LOGIN_FROM

```cypher
MATCH (u:User), (h:Hostname)
CREATE (u)-[r:LOGIN_FROM {
  timestamp: datetime(),
  event_type: "LOGIN",
  frequency: 1,
  first_seen: datetime(),
  last_seen: datetime()
}]->(h)
```

**Properties**:
- `timestamp` (DateTime): When login occurred
- `event_type` (String): LOGIN, FAILED_LOGIN, LOGOUT
- `frequency` (Integer): Number of occurrences
- `first_seen` (DateTime): First occurrence
- `last_seen` (DateTime): Latest occurrence

**Purpose**: User logging in from hostname

---

#### 2. ACCESS

```cypher
MATCH (u:User), (s:Server)
CREATE (u)-[r:ACCESS {
  timestamp: datetime(),
  access_type: "Read",
  frequency: 1,
  first_accessed: datetime(),
  last_accessed: datetime()
}]->(s)
```

**Properties**:
- `timestamp` (DateTime): Access time
- `access_type` (String): Read, Write, Execute
- `frequency` (Integer): Number of accesses
- `first_accessed` (DateTime): First access
- `last_accessed` (DateTime): Latest access

**Purpose**: User/device accessing server

---

#### 3. FAILED_LOGIN

```cypher
MATCH (u:User), (s:Server)
CREATE (u)-[r:FAILED_LOGIN {
  timestamp: datetime(),
  failure_reason: "Invalid password",
  count: 1,
  last_failure: datetime()
}]->(s)
```

**Properties**:
- `timestamp` (DateTime): When failure occurred
- `failure_reason` (String): Reason for failure
- `count` (Integer): Number of failed attempts
- `last_failure` (DateTime): Latest failure

**Purpose**: Failed login attempts

---

#### 4. USED_IP

```cypher
MATCH (h:Hostname), (ip:IPAddress)
CREATE (h)-[r:USED_IP {
  timestamp: datetime(),
  first_seen: datetime(),
  last_seen: datetime()
}]->(ip)
```

**Properties**:
- `timestamp` (DateTime): When IP was used
- `first_seen` (DateTime): First observation
- `last_seen` (DateTime): Latest observation

**Purpose**: Device using IP address

---

#### 5. CONNECTED_FROM

```cypher
MATCH (u:User), (ip:IPAddress)
CREATE (u)-[r:CONNECTED_FROM {
  timestamp: datetime(),
  connection_count: 1
}]->(ip)
```

**Properties**:
- `timestamp` (DateTime): Connection time
- `connection_count` (Integer): How many times

**Purpose**: User connecting from IP address

---

#### 6. MEMBER_OF

```cypher
MATCH (u:User), (g:Group)
CREATE (u)-[r:MEMBER_OF {
  since: datetime(),
  added_by: "ADMIN",
  added_timestamp: datetime()
}]->(g)
```

**Properties**:
- `since` (DateTime): When membership started
- `added_by` (String): Who added the user
- `added_timestamp` (DateTime): When added

**Purpose**: User group membership

---

#### 7. ACCESSED_AT

```cypher
MATCH (r:LOGIN_FROM), (t:TimeWindow)
CREATE (r)-[:ACCESSED_AT]->(t)
```

**Purpose**: Relate events to time windows

---

### Graph Structure Example

```
Graph for User U999 (Anomalous):

(User:U999)
├─[LOGIN_FROM]→(Hostname:PC01)
│                ├─[USED_IP]→(IPAddress:192.168.50.50)
│                │             └─[range_category: "Unusual"]
│                └─[ACCESSED_AT]→(TimeWindow:02:30 AM)
│                                 └─[is_business_hours: false]
│
├─[ACCESS]→(Server:SERVER_CRITICAL)
│           └─[criticality: "CRITICAL"]
│
├─[FAILED_LOGIN {count: 95}]→(Server:AD01)
│
├─[CONNECTED_FROM]→(IPAddress:192.168.50.50)
│                   └─[range_category: "Unusual"]
│
└─[MEMBER_OF]→(Group:USERS)
              └─[privilege_level: "LOW"]
```

---

## Part 3: Data Ingestion Process

### Step 1: Validate Raw Data

```python
# Validate CSV fields
required_fields = ['user_id', 'hostname', 'server', 'event_type', 'timestamp', 'ip_address', 'group_role']
valid_event_types = ['LOGIN', 'FAILED_LOGIN', 'LOGOUT', 'PASSWORD_CHANGE', 'ACCESS', 'PERMISSION_CHANGE', 'GROUP_CHANGE']

def validate_ad_log(csv_file):
    df = pd.read_csv(csv_file)
    
    # Check all fields present
    assert all(f in df.columns for f in required_fields), "Missing required fields"
    
    # Check no nulls
    assert df[required_fields].isnull().sum().sum() == 0, "Null values found"
    
    # Check valid enum
    assert df['event_type'].isin(valid_event_types).all(), "Invalid event_type"
    
    # Check valid datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    return df
```

---

### Step 2: Create Neo4j Nodes

```cypher
// Load CSV and create User nodes
LOAD CSV WITH HEADERS FROM 'file:///ad_events.csv' AS row
CREATE (u:User {user_id: row.user_id})
ON CREATE SET u.created_timestamp = datetime()
```

---

### Step 3: Create Relationships

```cypher
// Create LOGIN_FROM relationships
LOAD CSV WITH HEADERS FROM 'file:///ad_events.csv' AS row
WHERE row.event_type IN ['LOGIN', 'FAILED_LOGIN']
MATCH (u:User {user_id: row.user_id})
MATCH (h:Hostname {name: row.hostname})
MERGE (u)-[r:LOGIN_FROM]->(h)
ON CREATE SET r.timestamp = datetime(row.timestamp)
ON MATCH SET r.frequency = r.frequency + 1
```

---

## Part 4: Query Examples

### Find All Users' Activities

```cypher
MATCH (u:User)-[r:LOGIN_FROM]->(h:Hostname)
RETURN u.user_id, h.name, count(*) as login_count
ORDER BY login_count DESC
```

### Find Unusual IP Usage

```cypher
MATCH (u:User)-[:CONNECTED_FROM]->(ip:IPAddress)
WHERE ip.range_category != 'Office_Network'
RETURN u.user_id, ip.address, ip.range_category
```

### Find Off-Hours Activity

```cypher
MATCH (u:User)-[r:LOGIN_FROM]->(h:Hostname)-[:ACCESSED_AT]->(t:TimeWindow)
WHERE t.is_business_hours = false
RETURN u.user_id, h.name, t.hour, count(*) as off_hours_count
```

### Find Critical Server Access

```cypher
MATCH (u:User)-[:ACCESS]->(s:Server)
WHERE s.criticality = 'CRITICAL'
RETURN u.user_id, s.name, count(*) as access_count
```

---

## Part 5: Data Standards & Conventions

### Naming Conventions

- **Node Properties**: snake_case (e.g., `user_id`, `created_timestamp`)
- **Relationships**: UPPER_CASE (e.g., `LOGIN_FROM`, `FAILED_LOGIN`)
- **Labels**: PascalCase (e.g., `User`, `Hostname`, `Server`)

### ID Formats

- **User IDs**: `U###` (e.g., U001, U999)
- **Hostname IDs**: `H###` (e.g., H001, H050)
- **Server IDs**: `S###` (e.g., S001, S100)
- **IP IDs**: `IP###` (e.g., IP001)
- **Group IDs**: `G###` (e.g., G001, G038)

### Timestamps

- Format: ISO 8601 (e.g., `2026-04-30T08:15:30Z`)
- Timezone: UTC preferred
- Neo4j format: `datetime()` function

---

## Part 6: Data Completeness Checklist

- [ ] All 7 required CSV fields present
- [ ] No null values in required fields
- [ ] Event types valid and consistent
- [ ] Timestamps valid and in ISO 8601 format
- [ ] IP addresses valid format
- [ ] User IDs unique and consistent
- [ ] Group names standardized
- [ ] Hostname names consistent
- [ ] Server names consistent
- [ ] Neo4j nodes created for all unique entities
- [ ] Relationships created with proper properties
- [ ] No duplicate relationships
- [ ] Timestamps chronologically reasonable
- [ ] All queries returning expected results
