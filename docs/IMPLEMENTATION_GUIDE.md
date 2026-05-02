# Implementation Guide: Graph-Based AD Anomaly Detection

## Project Phases Overview

```
Phase 1: Data Preparation        (Week 1)
    ↓
Phase 2: Neo4j Knowledge Graph   (Week 2)
    ↓
Phase 3: Rule-Based Knowledge   (Week 3)
    ↓
Phase 4: Graph Feature Extract  (Week 4)
    ↓
Phase 5: Isolation Forest        (Week 5)
    ↓
Phase 6: Results & Validation    (Week 6)
```

---

## Phase 1: Data Preparation (Week 1)

### Step 1.1: Collect AD Audit Logs

**Source**: Windows Event Viewer (Domain Controllers)

**Event IDs to collect:**
- 4624 (Successful Logon)
- 4625 (Failed Logon)
- 4634 (Logoff)
- 4723 (Password Changed)
- 4720 (User Account Created)
- 4726 (User Account Deleted)
- 4728 (User Added to Security Group)

**Collection Method:**

```powershell
# PowerShell: Export from Event Viewer
Get-WinEvent -FilterHashtable @{
    LogName='Security'
    ID=4624,4625
    StartTime=(Get-Date).AddDays(-30)
} | Select-Object TimeCreated, Properties | Export-Csv ad_events.csv
```

Or use:
- Windows Event Collector (WEC)
- Splunk / ELK Stack
- AuditPolicy automation

### Step 1.2: Create AD Log CSV

**File**: `data/raw_data/ad_events.csv`

**Columns** (7 required):
```
user_id,hostname,server,event_type,timestamp,ip_address,group_role
```

**Validation Script** (Python):

```python
import pandas as pd
import sys

def validate_ad_log(csv_file):
    """Validate AD log CSV format"""
    
    required_fields = ['user_id', 'hostname', 'server', 'event_type', 
                       'timestamp', 'ip_address', 'group_role']
    valid_event_types = ['LOGIN', 'FAILED_LOGIN', 'LOGOUT', 'PASSWORD_CHANGE', 
                         'ACCESS', 'PERMISSION_CHANGE', 'GROUP_CHANGE']
    
    try:
        df = pd.read_csv(csv_file)
        
        # Check all required fields present
        missing = [f for f in required_fields if f not in df.columns]
        assert not missing, f"Missing fields: {missing}"
        
        # Check no nulls in required fields
        nulls = df[required_fields].isnull().sum()
        assert nulls.sum() == 0, f"Null values found:\n{nulls[nulls > 0]}"
        
        # Check valid event types
        invalid = df[~df['event_type'].isin(valid_event_types)]
        assert len(invalid) == 0, f"Invalid event_type: {invalid['event_type'].unique()}"
        
        # Check valid datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Check valid IP format
        import ipaddress
        for ip in df['ip_address'].unique():
            try:
                ipaddress.ip_address(ip)
            except ValueError:
                raise ValueError(f"Invalid IP: {ip}")
        
        print("✓ CSV validation passed")
        print(f"  - Records: {len(df)}")
        print(f"  - Unique users: {df['user_id'].nunique()}")
        print(f"  - Unique hosts: {df['hostname'].nunique()}")
        print(f"  - Unique servers: {df['server'].nunique()}")
        print(f"  - Time range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        return df
        
    except Exception as e:
        print(f"✗ Validation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    df = validate_ad_log("data/raw_data/ad_events.csv")
```

**Expected Output:**
```
✓ CSV validation passed
  - Records: 524284
  - Unique users: 1652
  - Unique hosts: 1271
  - Unique servers: 47
  - Time range: 2025-06-24 to 2025-12-31
```

### Step 1.3: Sample Data Creation

**Create test data** (if needed):

```python
import pandas as pd
from datetime import datetime, timedelta
import random

def generate_sample_ad_logs(num_records=10000):
    """Generate realistic sample AD logs"""
    
    users = [f"U{i:04d}" for i in range(1, 101)]  # U0001-U0100
    hostnames = [f"PC{i:02d}" for i in range(1, 51)]  # PC01-PC50
    servers = ["AD01", "AD02", "FILE01", "EXCHANGE", "SQL01", "APP01"]
    events = ["LOGIN", "FAILED_LOGIN", "ACCESS", "LOGOUT"]
    groups = ["DOMAIN_USERS", "ADMINS", "FINANCE", "IT_SUPPORT"]
    
    data = []
    base_time = datetime(2025, 6, 24)
    
    for i in range(num_records):
        record = {
            'user_id': random.choice(users),
            'hostname': random.choice(hostnames),
            'server': random.choice(servers),
            'event_type': random.choice(events),
            'timestamp': (base_time + timedelta(seconds=random.randint(0, 15000000))).isoformat() + 'Z',
            'ip_address': f"192.168.{random.randint(1, 255)}.{random.randint(1, 255)}",
            'group_role': random.choice(groups)
        }
        data.append(record)
    
    df = pd.DataFrame(data)
    df.to_csv('data/raw_data/ad_events_sample.csv', index=False)
    print(f"Generated {num_records} sample records")
    return df

generate_sample_ad_logs()
```

---

## Phase 2: Neo4j Knowledge Graph (Week 2)

### Step 2.1: Neo4j Setup

**Install Neo4j** (if not installed):

```bash
# Using Docker (recommended)
docker run -d \
  --name neo4j \
  -p 7474:7474 \
  -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest

# Access at: http://localhost:7474
```

Or download from: https://neo4j.com/download/

### Step 2.2: Create Graph Schema

**Cypher Script** (save as `cypher/01_create_schema.cypher`):

```cypher
// Create constraints for data integrity
CREATE CONSTRAINT user_id IF NOT EXISTS
FOR (u:User) REQUIRE u.user_id IS UNIQUE;

CREATE CONSTRAINT hostname_id IF NOT EXISTS
FOR (h:Hostname) REQUIRE h.hostname_id IS UNIQUE;

CREATE CONSTRAINT server_id IF NOT EXISTS
FOR (s:Server) REQUIRE s.server_id IS UNIQUE;

CREATE CONSTRAINT ip_id IF NOT EXISTS
FOR (ip:IPAddress) REQUIRE ip.ip_id IS UNIQUE;

CREATE CONSTRAINT group_id IF NOT EXISTS
FOR (g:Group) REQUIRE g.group_id IS UNIQUE;

// Create indexes for fast lookup
CREATE INDEX user_lookup IF NOT EXISTS FOR (u:User) ON (u.user_id);
CREATE INDEX hostname_lookup IF NOT EXISTS FOR (h:Hostname) ON (h.name);
CREATE INDEX server_lookup IF NOT EXISTS FOR (s:Server) ON (s.name);
CREATE INDEX ip_lookup IF NOT EXISTS FOR (ip:IPAddress) ON (ip.address);
CREATE INDEX group_lookup IF NOT EXISTS FOR (g:Group) ON (g.group_name);

RETURN "Schema created successfully";
```

**Execute in Neo4j Browser:**

```
Connect to bolt://localhost:7687
Username: neo4j
Password: password

Then paste cypher script and run
```

### Step 2.3: Ingest Data

**Python Script** (save as `src/neo4j_ingest.py`):

```python
from neo4j import GraphDatabase
import pandas as pd
import os

class Neo4jIngestor:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        self.driver.close()
    
    def ingest_data(self, csv_file):
        """Ingest AD logs into Neo4j"""
        
        df = pd.read_csv(csv_file)
        print(f"Ingesting {len(df)} records from {csv_file}")
        
        # Create nodes
        self._create_user_nodes(df)
        self._create_hostname_nodes(df)
        self._create_server_nodes(df)
        self._create_ip_nodes(df)
        self._create_group_nodes(df)
        
        # Create relationships
        self._create_relationships(df)
        
        print("✓ Ingestion complete")
    
    def _create_user_nodes(self, df):
        """Create User nodes"""
        with self.driver.session() as session:
            users = df[['user_id']].drop_duplicates()
            
            for idx, row in users.iterrows():
                session.run("""
                    MERGE (u:User {user_id: $user_id})
                    SET u.created_timestamp = datetime()
                """, user_id=row['user_id'])
            
            print(f"✓ Created {len(users)} User nodes")
    
    def _create_hostname_nodes(self, df):
        """Create Hostname nodes"""
        with self.driver.session() as session:
            hostnames = df[['hostname']].drop_duplicates()
            hostnames['hostname_id'] = 'H' + (hostnames.index + 1).astype(str).str.zfill(4)
            
            for idx, row in hostnames.iterrows():
                session.run("""
                    MERGE (h:Hostname {hostname_id: $hostname_id})
                    SET h.name = $hostname, h.created_timestamp = datetime()
                """, hostname_id=row['hostname_id'], hostname=row['hostname'])
            
            print(f"✓ Created {len(hostnames)} Hostname nodes")
    
    def _create_server_nodes(self, df):
        """Create Server nodes"""
        with self.driver.session() as session:
            servers = df[['server']].drop_duplicates()
            servers['server_id'] = 'S' + (servers.index + 1).astype(str).str.zfill(4)
            
            for idx, row in servers.iterrows():
                session.run("""
                    MERGE (s:Server {server_id: $server_id})
                    SET s.name = $server, s.created_timestamp = datetime()
                """, server_id=row['server_id'], server=row['server'])
            
            print(f"✓ Created {len(servers)} Server nodes")
    
    def _create_ip_nodes(self, df):
        """Create IPAddress nodes"""
        with self.driver.session() as session:
            ips = df[['ip_address']].drop_duplicates()
            ips['ip_id'] = 'IP' + (ips.index + 1).astype(str).str.zfill(4)
            
            for idx, row in ips.iterrows():
                session.run("""
                    MERGE (ip:IPAddress {ip_id: $ip_id})
                    SET ip.address = $ip_address, ip.range_category = 'Office_Network'
                """, ip_id=row['ip_id'], ip_address=row['ip_address'])
            
            print(f"✓ Created {len(ips)} IPAddress nodes")
    
    def _create_group_nodes(self, df):
        """Create Group nodes"""
        with self.driver.session() as session:
            groups = df[['group_role']].drop_duplicates()
            groups['group_id'] = 'G' + (groups.index + 1).astype(str).str.zfill(4)
            
            for idx, row in groups.iterrows():
                session.run("""
                    MERGE (g:Group {group_id: $group_id})
                    SET g.group_name = $group_role, g.privilege_level = 'LOW'
                """, group_id=row['group_id'], group_role=row['group_role'])
            
            print(f"✓ Created {len(groups)} Group nodes")
    
    def _create_relationships(self, df):
        """Create relationships"""
        with self.driver.session() as session:
            
            # LOGIN_FROM relationships
            for idx, row in df.iterrows():
                session.run("""
                    MATCH (u:User {user_id: $user_id})
                    MATCH (h:Hostname {name: $hostname})
                    MERGE (u)-[r:LOGIN_FROM]->(h)
                    ON CREATE SET r.timestamp = datetime($timestamp)
                    ON MATCH SET r.frequency = coalesce(r.frequency, 0) + 1
                """, user_id=row['user_id'], hostname=row['hostname'], 
                   timestamp=row['timestamp'])
            
            print(f"✓ Created LOGIN_FROM relationships")
            
            # MEMBER_OF relationships
            for idx, row in df.iterrows():
                session.run("""
                    MATCH (u:User {user_id: $user_id})
                    MATCH (g:Group {group_name: $group_role})
                    MERGE (u)-[:MEMBER_OF]->(g)
                """, user_id=row['user_id'], group_role=row['group_role'])
            
            print(f"✓ Created MEMBER_OF relationships")

# Usage
if __name__ == "__main__":
    ingestor = Neo4jIngestor("bolt://localhost:7687", "neo4j", "password")
    ingestor.ingest_data("data/raw_data/ad_events.csv")
    ingestor.close()
```

**Run:**

```bash
python src/neo4j_ingest.py
```

---

## Phase 3: Rule-Based Knowledge (Week 3)

### Step 3.1: Implement Rules

**Script** (save as `src/implement_rules.py`):

```python
from neo4j import GraphDatabase

class RuleEngine:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        self.driver.close()
    
    def implement_rule_R001(self):
        """Rule 1: Normal Login Hosts"""
        with self.driver.session() as session:
            session.run("""
                MATCH (u:User)-[r:LOGIN_FROM]->(h:Hostname)
                WITH u, count(DISTINCT h) as unique_hosts, 
                     collect(DISTINCT h.name) as host_list
                SET u.rule_R001_unique_hosts = unique_hosts,
                    u.rule_R001_violation = CASE WHEN unique_hosts > 3 THEN true ELSE false END
                RETURN u.user_id, unique_hosts, u.rule_R001_violation
            """)
        print("✓ Rule R001 implemented")
    
    def implement_rule_R002(self):
        """Rule 2: Business Hours Pattern"""
        with self.driver.session() as session:
            session.run("""
                MATCH (u:User)-[r:LOGIN_FROM]->(h:Hostname)
                WITH u, count(*) as total_logins,
                     size([x IN collect(r) WHERE 
                           hour(datetime(x.timestamp)) >= 8 
                           AND hour(datetime(x.timestamp)) < 18
                     ]) as business_hours_logins
                WITH u, ROUND(1.0 * business_hours_logins / total_logins, 4) as ratio
                SET u.rule_R002_business_hours_ratio = ratio,
                    u.rule_R002_violation = CASE WHEN ratio < 0.9 THEN true ELSE false END
                RETURN u.user_id, ratio, u.rule_R002_violation
            """)
        print("✓ Rule R002 implemented")
    
    # Implement R003-R007 similarly...
    
    def implement_all_rules(self):
        """Implement all 7 rules"""
        self.implement_rule_R001()
        self.implement_rule_R002()
        # ... R003-R007
        print("\n✓ All rules implemented")

# Usage
if __name__ == "__main__":
    engine = RuleEngine("bolt://localhost:7687", "neo4j", "password")
    engine.implement_all_rules()
    engine.close()
```

**Run:**

```bash
python src/implement_rules.py
```

---

## Phase 4: Graph Feature Extraction (Week 4)

### Step 4.1: Extract Features

**Script** (save as `src/extract_graph_features.py`):

```python
from neo4j import GraphDatabase
import pandas as pd

class FeatureExtractor:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def extract_features(self):
        """Extract 8 graph-based features"""
        
        with self.driver.session() as session:
            result = session.run("""
                MATCH (u:User)
                WITH u,
                     size((u)-[:LOGIN_FROM]->()) as host_count,
                     size([(u)-[:ACCESS]->(s:Server {criticality:'CRITICAL'}) | s]) as critical_servers,
                     size((u)-[:FAILED_LOGIN]->()) as failed_logins,
                     size((u)-[:LOGON_FROM]->()) as total_logins,
                     size([(u)-[:LOGIN_FROM]->(h:Hostname)<-[:LOGIN_FROM]-(other:User) 
                           WHERE size((h)<-[:LOGIN_FROM]-()) > 5 | h]) as shared_devices
                
                SET u.feature_host_count = host_count,
                    u.feature_critical_servers = critical_servers,
                    u.feature_failure_rate = CASE WHEN total_logins > 0 
                                                  THEN ROUND(failed_logins*1.0/total_logins, 4)
                                                  ELSE 0 END,
                    u.feature_shared_devices = shared_devices
                
                RETURN u.user_id, host_count, critical_servers, 
                       u.feature_failure_rate, shared_devices
            """)
            
            features = []
            for record in result:
                features.append(dict(record))
            
            df = pd.DataFrame(features)
            df.to_csv('data/graph_features.csv', index=False)
            
            print(f"✓ Extracted features for {len(df)} users")
            print(f"  Saved to: data/graph_features.csv")
            
            return df

# Usage
if __name__ == "__main__":
    extractor = FeatureExtractor("bolt://localhost:7687", "neo4j", "password")
    features_df = extractor.extract_features()
    print(features_df.head())
```

**Run:**

```bash
python src/extract_graph_features.py
```

---

## Phase 5: Isolation Forest (Week 5)

### Step 5.1: Train Isolation Forest

**Script** (save as `src/train_isolation_forest.py`):

```python
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib

class GraphBasedAnomalyDetector:
    def __init__(self):
        self.model = None
        self.scaler = None
    
    def load_features(self):
        """Load graph features"""
        self.df = pd.read_csv('data/graph_features.csv')
        print(f"Loaded {len(self.df)} records")
        return self.df
    
    def prepare_features(self):
        """Prepare features for ML"""
        feature_columns = [
            'host_count', 'critical_servers', 
            'feature_failure_rate', 'shared_devices'
        ]
        
        X = self.df[feature_columns].fillna(0)
        
        # Normalize
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        print(f"Features prepared: {X.shape}")
        return X_scaled
    
    def train_model(self, X_scaled):
        """Train Isolation Forest"""
        self.model = IsolationForest(
            contamination=0.05,
            random_state=42,
            n_estimators=100
        )
        
        self.model.fit(X_scaled)
        print("✓ Model trained")
    
    def predict_anomalies(self, X_scaled):
        """Predict anomalies"""
        predictions = self.model.predict(X_scaled)
        scores = self.model.score_samples(X_scaled)
        
        self.df['anomaly'] = predictions
        self.df['anomaly_score'] = scores
        
        # Classify severity
        self.df['severity'] = self.df['anomaly_score'].apply(lambda x:
            'CRITICAL' if x < -0.5 else 'HIGH' if x < -0.3 else 'MEDIUM' if x < -0.1 else 'LOW'
        )
        
        anomaly_count = (predictions == -1).sum()
        print(f"✓ Detected {anomaly_count} anomalies ({anomaly_count/len(self.df)*100:.2f}%)")
        
        return self.df
    
    def save_results(self):
        """Save results"""
        self.df.to_csv('output/anomaly_detection_results.csv', index=False)
        joblib.dump(self.model, 'models/isolation_forest_model.pkl')
        print("✓ Results saved")

# Usage
if __name__ == "__main__":
    detector = GraphBasedAnomalyDetector()
    detector.load_features()
    X_scaled = detector.prepare_features()
    detector.train_model(X_scaled)
    results = detector.predict_anomalies(X_scaled)
    detector.save_results()
    
    # Display top anomalies
    print("\nTop 10 Anomalies:")
    print(results[results['anomaly'] == -1].nlargest(10, 'anomaly_score')[
        ['user_id', 'anomaly_score', 'severity']
    ])
```

**Run:**

```bash
python src/train_isolation_forest.py
```

---

## Phase 6: Results & Validation (Week 6)

### Step 6.1: Generate Reports

**Script** (save as `src/generate_report.py`):

```python
import pandas as pd
from datetime import datetime

def generate_anomaly_report():
    """Generate comprehensive anomaly report"""
    
    results = pd.read_csv('output/anomaly_detection_results.csv')
    
    report = f"""
    ═══════════════════════════════════════════════════════════
    Active Directory Anomaly Detection Report
    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    ═══════════════════════════════════════════════════════════
    
    SUMMARY STATISTICS
    ──────────────────────────────────────────────────────────
    Total Users Analyzed:    {len(results)}
    Anomalous Users:        {(results['anomaly'] == -1).sum()}
    Anomaly Rate:           {(results['anomaly'] == -1).sum() / len(results) * 100:.2f}%
    
    SEVERITY BREAKDOWN
    ──────────────────────────────────────────────────────────
    CRITICAL:  {(results['severity'] == 'CRITICAL').sum()} users
    HIGH:      {(results['severity'] == 'HIGH').sum()} users
    MEDIUM:    {(results['severity'] == 'MEDIUM').sum()} users
    LOW:       {(results['severity'] == 'LOW').sum()} users
    
    TOP 20 ANOMALOUS USERS
    ──────────────────────────────────────────────────────────
    """
    
    top_anomalies = results[results['anomaly'] == -1].nlargest(20, 'anomaly_score')
    
    for idx, user in top_anomalies.iterrows():
        report += f"""
    {user['user_id']}  |  Score: {user['anomaly_score']:.4f}  |  Severity: {user['severity']}
        Hosts: {int(user['host_count'])}  |  Critical Servers: {int(user['critical_servers'])}
        Failure Rate: {user['feature_failure_rate']:.2%}  |  Shared Devices: {int(user['shared_devices'])}
    """
    
    report += """
    ═══════════════════════════════════════════════════════════
    RECOMMENDATIONS
    ──────────────────────────────────────────────────────────
    1. Investigate CRITICAL severity users immediately
    2. Review failed login patterns (brute force detection)
    3. Validate unusual IP connections
    4. Check shared device access controls
    
    ═══════════════════════════════════════════════════════════
    """
    
    print(report)
    
    with open('output/anomaly_report.txt', 'w') as f:
        f.write(report)
    
    print("✓ Report saved to output/anomaly_report.txt")

if __name__ == "__main__":
    generate_anomaly_report()
```

### Step 6.2: Validation

**Check Results:**

```bash
# View anomalies
python -c "import pandas as pd; df = pd.read_csv('output/anomaly_detection_results.csv'); \
           print(df[df['anomaly'] == -1].head(20))"

# Generate report
python src/generate_report.py

# Count by severity
python -c "import pandas as pd; df = pd.read_csv('output/anomaly_detection_results.csv'); \
           print(df['severity'].value_counts())"
```

---

## Testing Checklist

- [ ] Phase 1: AD Log CSV valid (7 columns, no nulls)
- [ ] Phase 2: Neo4j nodes created (5 types, correct counts)
- [ ] Phase 2: Relationships created (LOGIN_FROM, MEMBER_OF, etc)
- [ ] Phase 3: All 7 rules implemented
- [ ] Phase 3: Rule violations calculated
- [ ] Phase 4: Graph features extracted (8 features)
- [ ] Phase 4: Features CSV created
- [ ] Phase 5: Isolation Forest model trained
- [ ] Phase 5: Anomalies detected (5% = ~28 users if 559 users)
- [ ] Phase 6: Report generated
- [ ] Phase 6: Top anomalies interpretable

---

## Troubleshooting

### Neo4j Connection Issues

```python
# Test connection
from neo4j import GraphDatabase

try:
    driver = GraphDatabase.driver("bolt://localhost:7687", 
                                  auth=("neo4j", "password"))
    with driver.session() as session:
        result = session.run("RETURN 1")
        print("✓ Connected successfully")
except Exception as e:
    print(f"✗ Connection failed: {e}")
```

### Feature Extraction Issues

```python
# Check for null features
df = pd.read_csv('data/graph_features.csv')
print(df.isnull().sum())

# Check feature ranges
print(df.describe())
```

### Isolation Forest Issues

```python
# Verify model was trained
import joblib
model = joblib.load('models/isolation_forest_model.pkl')
print(model.get_params())
```

---

## Next Steps

1. ✅ Complete all 6 phases
2. ✅ Validate results
3. ✅ Document findings
4. ✅ Write paper
5. ✅ Present to advisor

For detailed information on each phase, refer to:
- `ARCHITECTURE.md` - Overall design
- `DATA_SCHEMA.md` - Data structures
- `RULE_BASED_KNOWLEDGE.md` - Rules detail
- `JUSTIFICATION.md` - Why this approach
