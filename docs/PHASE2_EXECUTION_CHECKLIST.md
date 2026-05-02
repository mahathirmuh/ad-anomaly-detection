# Phase 2 Execution Checklist

## Pre-Execution Verification

### 1. Neo4j Status
```bash
# Check if Neo4j is running
docker ps | grep neo4j
# or
curl http://localhost:7474  # Should return 200 OK
```

**Expected:** Neo4j container running, port 7687 accessible

- [ ] Neo4j running on bolt://localhost:7687
- [ ] Username: neo4j
- [ ] Password: password
- [ ] Can connect from Python

### 2. Data File Verification
```bash
# Check unified_logon_events.csv exists
ls -lh data/restructured_data/unified_logon_events.csv
```

**Expected:**
```
-rw-r--r--  1  user  group  ~200MB  2026-04-30  unified_logon_events.csv
1,833,353 rows (1,833,352 data + 1 header)
```

- [ ] File exists
- [ ] File size ~200MB
- [ ] Row count 1,833,353

### 3. Python Dependencies
```bash
pip install neo4j pandas
```

**Expected:**
```
Successfully installed neo4j-5.x.x pandas-2.x.x
```

- [ ] neo4j package installed
- [ ] pandas package installed

### 4. Script Verification
```bash
# Check script exists and is readable
cat neo4j_ingest_phase2.py | head -20
```

**Expected:** Script contains Neo4jIngestor class

- [ ] Script exists
- [ ] Script is valid Python (no syntax errors)
- [ ] CSV_PATH points to correct file

---

## Execution Phase

### Command to Run

```bash
cd /c/Users/itsupport/Documents/Apps/tdas_adauditv3
python neo4j_ingest_phase2.py
```

### What Will Happen (Timeline)

```
[0:00-0:05]   Creating Constraints & Indexes
[0:05-0:10]   Loading Data (1.8M rows into memory)
[0:10-1:00]   Creating Nodes:
              - User nodes (714)
              - Hostname nodes (1,270)
              - Server nodes (~50)
              - IPAddress nodes (1,270)
              - Service nodes (~10)
              - Group nodes (~1-2)
              - Event nodes (1,833,352) ← Most time spent here
              Progress: 100K, 200K, 300K... events
              
[1:00-2:30]   Creating Relationships:
              - LOGIN_FROM (1.8M)
              - AUTHENTICATED_VIA (1.8M)
              - FAILED_LOGIN (~635K)
              - CONNECTED_FROM (1.8M)
              - USED_IP (~2M)
              - USED_SERVICE (~500K)
              - MEMBER_OF (714)
              - REFERENCES (1.8M)
              Progress: 100K, 200K, 300K... relationships
              
[2:30-2:35]   Validation Statistics
[2:35-3:00]   Complete + Summary

Total Expected Duration: ~3 hours
```

### Monitoring Progress

Watch for these log outputs:

```
[OK] Creating constraints & indexes...
[OK] Loaded 1,833,352 rows
[1/7] Creating User nodes...
[2/7] Creating Hostname nodes...
[3/7] Creating Server nodes...
[4/7] Creating IPAddress nodes...
[5/7] Creating Service nodes...
[6/7] Creating Group nodes...
[7/7] Creating Event nodes...
     ...processed 100,000 events
     ...processed 200,000 events
     ...processed 300,000 events
     [OK] Created 1,833,352 Event nodes
     
[Creating relationships...]
     ...processed 100,000 relationships
     ...processed 200,000 relationships
     
VALIDATION STATISTICS
  User nodes:                  714
  Hostname nodes:             1,270
  Server nodes:                 50
  IPAddress nodes:           1,270
  Service nodes:               10
  Group nodes:                  2
  Event nodes:           1,833,352
  LOGIN_FROM relationships: 1,833,352
  AUTHENTICATED_VIA:       1,833,352
  FAILED_LOGIN:              635K
  CONNECTED_FROM:          1,833,352
  USED_IP:                 ~2,000K
  USED_SERVICE:              500K
  MEMBER_OF:                 714
  REFERENCES:              1,833,352
```

---

## Post-Execution Validation

### Quick Neo4j Query Check

```bash
# Open Neo4j Browser at http://localhost:7474
# Or use neo4j-cli if available

# Test Query 1: Count all nodes
MATCH (n) RETURN count(n) as total_nodes

# Expected: ~6M nodes total

# Test Query 2: Sample user with relationships
MATCH (u:User {username: "denny.arifin"})-[r]->(n)
RETURN u.username, type(r), count(r) as count
LIMIT 10

# Expected: User connected to multiple nodes via different relationships

# Test Query 3: Failed login pattern
MATCH (u:User)-[r:FAILED_LOGIN]->(s:Server)
WHERE r.count > 100
RETURN u.username, s.name, r.count
ORDER BY r.count DESC
LIMIT 5

# Expected: Users with high failure rates
```

### Expected Issues & Solutions

| Issue | Solution |
|-------|----------|
| "Connection refused" | Check Neo4j is running: `docker ps` |
| "File not found" | Check CSV path: `ls data/restructured_data/unified_logon_events.csv` |
| "Out of memory" | Neo4j memory config: `docker inspect neo4j \| grep -i memory` |
| "Timeout after 30s" | Increase timeout in script or restart Neo4j |
| Relationship counts don't match | Check constraint violations in logs |

---

## Phase 2 Completion Criteria

- [ ] Script runs without errors
- [ ] All nodes created (User: 714, Hostname: 1270, Server: ~50, IP: 1270, Service: ~10, Group: 1-2)
- [ ] All relationships created (~10M+ total)
- [ ] Validation statistics match expected counts
- [ ] Can query single user and see relationships
- [ ] Can query failed login patterns
- [ ] Neo4j Browser accessible at localhost:7474

---

## What's Next After Phase 2

Once execution complete and validated:

1. **Phase 3: Rule-Based Knowledge**
   - Implement 7 domain rules in Cypher
   - Calculate rule violations
   - Store on User nodes

2. **Phase 4: Graph Feature Extraction**
   - Extract 8 graph-derived features
   - Run Cypher queries for metrics
   - Export to CSV for ML

3. **Phase 5: Isolation Forest**
   - Load feature CSV
   - Train model
   - Generate anomaly scores

4. **Phase 6: Results & Validation**
   - Create final report
   - Validate findings

---

## Troubleshooting

### If script hangs at "Creating Event nodes..."
- This is normal - it's processing 1.8M events
- Each progress message (every 100K) takes ~5 minutes
- Total for event creation: ~1 hour

### If script fails halfway
- **Do NOT restart and retry** (may create duplicates)
- Instead:
  1. Check error message
  2. Fix issue (memory, connection, etc)
  3. Delete Neo4j data: `docker exec neo4j cypher-shell 'MATCH (n) DETACH DELETE n'`
  4. Run script again

### If Neo4j runs out of memory
```bash
# Increase memory allocation
docker stop neo4j
docker rm neo4j
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  -e NEO4J_dbms_memory_heap_initial__size=2G \
  -e NEO4J_dbms_memory_heap_max__size=4G \
  neo4j:latest
```

---

## Notes

- Ingestion is idempotent: running twice will MERGE, not duplicate
- Progress messages printed every 100K operations
- Script will take 2.5-3 hours for full ingestion
- It's normal for Neo4j memory to spike during ingestion
- After completion, graph is ready for Phase 3

