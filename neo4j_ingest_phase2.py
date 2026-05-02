#!/usr/bin/env python3
"""
Phase 2: Neo4j Knowledge Graph Ingestion
Ingest unified_logon_events.csv into Neo4j with rich relationships
"""

import pandas as pd
from neo4j import GraphDatabase
import hashlib
from datetime import datetime
import os

class Neo4jIngestor:
    def __init__(self, uri, user, password):
        """Initialize Neo4j connection"""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.session = None

    def close(self):
        """Close connection"""
        if self.session:
            self.session.close()
        self.driver.close()

    def create_constraints_and_indexes(self):
        """Create constraints and indexes"""
        print("\n" + "="*70)
        print("CREATING CONSTRAINTS & INDEXES")
        print("="*70)

        with self.driver.session() as session:
            constraints = [
                'CREATE CONSTRAINT user_unique IF NOT EXISTS FOR (u:User) REQUIRE u.user_id IS UNIQUE',
                'CREATE CONSTRAINT hostname_unique IF NOT EXISTS FOR (h:Hostname) REQUIRE h.hostname_id IS UNIQUE',
                'CREATE CONSTRAINT server_unique IF NOT EXISTS FOR (s:Server) REQUIRE s.server_id IS UNIQUE',
                'CREATE CONSTRAINT ip_unique IF NOT EXISTS FOR (ip:IPAddress) REQUIRE ip.ip_id IS UNIQUE',
                'CREATE CONSTRAINT service_unique IF NOT EXISTS FOR (svc:Service) REQUIRE svc.service_id IS UNIQUE',
                'CREATE CONSTRAINT group_unique IF NOT EXISTS FOR (g:Group) REQUIRE g.group_id IS UNIQUE',
                'CREATE CONSTRAINT event_unique IF NOT EXISTS FOR (e:Event) REQUIRE e.event_id IS UNIQUE',
            ]

            indexes = [
                'CREATE INDEX user_lookup IF NOT EXISTS FOR (u:User) ON (u.username)',
                'CREATE INDEX hostname_lookup IF NOT EXISTS FOR (h:Hostname) ON (h.name)',
                'CREATE INDEX server_lookup IF NOT EXISTS FOR (s:Server) ON (s.name)',
                'CREATE INDEX ip_lookup IF NOT EXISTS FOR (ip:IPAddress) ON (ip.address)',
                'CREATE INDEX service_lookup IF NOT EXISTS FOR (svc:Service) ON (svc.service_name)',
                'CREATE INDEX group_lookup IF NOT EXISTS FOR (g:Group) ON (g.group_name)',
                'CREATE INDEX event_lookup IF NOT EXISTS FOR (e:Event) ON (e.event_source, e.timestamp)',
            ]

            for constraint in constraints:
                try:
                    session.run(constraint)
                    print(f"  [OK] {constraint.split('FOR')[0]}")
                except Exception as e:
                    print(f"  [SKIP] Already exists: {str(e)[:50]}")

            print("\n  Creating indexes...")
            for index in indexes:
                try:
                    session.run(index)
                except Exception as e:
                    print(f"  [SKIP] {str(e)[:50]}")

            print("  [OK] Constraints & indexes created")

    def generate_id(self, prefix, value):
        """Generate consistent IDs"""
        hash_val = hashlib.md5(str(value).encode()).hexdigest()[:6]
        return f"{prefix}_{hash_val}"

    def load_data(self, csv_path):
        """Load CSV data"""
        print("\n" + "="*70)
        print("LOADING DATA")
        print("="*70)

        df = pd.read_csv(csv_path)
        print(f"[OK] Loaded {len(df):,} rows from {csv_path}")
        print(f"     Columns: {list(df.columns)}")

        return df

    def generate_event_id(self, username, hostname, timestamp, event_source, event_type):
        """Generate unique event ID using full MD5 hash"""
        event_signature = f"{username}|{hostname}|{timestamp}|{event_source}|{event_type}"
        full_hash = hashlib.md5(event_signature.encode()).hexdigest()
        return f"E_{full_hash}"

    def clean_timestamp(self, ts):
        """Validate timestamp string; return None if malformed or year < 2000"""
        if pd.isna(ts):
            return None
        try:
            parsed = pd.to_datetime(str(ts))
            if parsed.year < 2000:
                return None
            return str(ts)
        except Exception:
            return None

    def _prepare_records(self, df):
        """Precompute all IDs and fields for batch processing"""
        print("\n[Phase 2] Precomputing record fields...")
        records = []
        for row in df.itertuples(index=False):
            user_id     = self.generate_id('U', row.username)
            hostname_id = self.generate_id('H', row.hostname)
            ip_id       = self.generate_id('IP', row.ip_address)

            server_id = None
            if pd.notna(row.dc_name):
                server_id = self.generate_id('S', row.dc_name)
            elif pd.notna(row.server_name):
                server_id = self.generate_id('S', row.server_name)

            service_id = self.generate_id('SVC', row.logon_service) if pd.notna(row.logon_service) else None

            group_id = None
            if pd.notna(row.domain):
                group_name = f"{row.domain.split('.')[0].upper()}_USERS"
                group_id = self.generate_id('G', group_name)

            event_id = self.generate_event_id(
                row.username, row.hostname, row.timestamp, row.event_source, row.event_type
            )
            ts = self.clean_timestamp(row.timestamp)

            records.append({
                'user_id':      user_id,
                'hostname_id':  hostname_id,
                'ip_id':        ip_id,
                'server_id':    server_id,
                'service_id':   service_id,
                'group_id':     group_id,
                'event_id':     event_id,
                'event_type':   row.event_type,
                'event_source': row.event_source,
                'timestamp':    ts,
                'success':      bool(row.success),
                'failure_reason': row.failure_reason if pd.notna(row.failure_reason) else None,
            })

        print(f"  [OK] Precomputed {len(records):,} records")
        return records

    def _run_batches(self, session, query, records, batch_size=500):
        """Send records to Neo4j in batches using UNWIND"""
        for i in range(0, len(records), batch_size):
            session.run(query, rows=records[i:i + batch_size])

    def create_nodes(self, df):
        """Create all nodes from data"""
        print("\n" + "="*70)
        print("CREATING NODES")
        print("="*70)

        BATCH = 500

        with self.driver.session() as session:
            # 1. User nodes
            print("  [1/7] Creating User nodes...")
            users = [{'user_id': self.generate_id('U', u), 'username': u}
                     for u in df['username'].dropna().unique()]
            self._run_batches(session, """
                UNWIND $rows AS row
                MERGE (u:User {user_id: row.user_id})
                ON CREATE SET u.username = row.username, u.created_timestamp = datetime()
            """, users, BATCH)
            print(f"     [OK] Created {len(users):,} User nodes")

            # 2. Hostname nodes
            print("  [2/7] Creating Hostname nodes...")
            hostnames = [{'hostname_id': self.generate_id('H', h), 'hostname': h}
                         for h in df['hostname'].dropna().unique()]
            self._run_batches(session, """
                UNWIND $rows AS row
                MERGE (h:Hostname {hostname_id: row.hostname_id})
                ON CREATE SET h.name = row.hostname, h.created_timestamp = datetime()
            """, hostnames, BATCH)
            print(f"     [OK] Created {len(hostnames):,} Hostname nodes")

            # 3. Server nodes
            print("  [3/7] Creating Server nodes...")
            servers_set = set()
            for row in df.itertuples(index=False):
                if pd.notna(row.dc_name):
                    servers_set.add((row.dc_name, 'DOMAIN_CONTROLLER', row.domain))
                if pd.notna(row.server_name):
                    servers_set.add((row.server_name, 'MEMBER_SERVER', row.domain))
            servers = [{'server_id': self.generate_id('S', n), 'server_name': n,
                        'server_type': t, 'domain': d} for n, t, d in servers_set]
            self._run_batches(session, """
                UNWIND $rows AS row
                MERGE (s:Server {server_id: row.server_id})
                ON CREATE SET s.name = row.server_name, s.type = row.server_type,
                              s.domain = row.domain, s.criticality = 'CRITICAL',
                              s.created_timestamp = datetime()
            """, servers, BATCH)
            print(f"     [OK] Created {len(servers):,} Server nodes")

            # 4. IPAddress nodes
            print("  [4/7] Creating IPAddress nodes...")
            ips = [{'ip_id': self.generate_id('IP', ip), 'ip_address': ip}
                   for ip in df['ip_address'].dropna().unique()]
            self._run_batches(session, """
                UNWIND $rows AS row
                MERGE (ip:IPAddress {ip_id: row.ip_id})
                ON CREATE SET ip.address = row.ip_address, ip.range_category = 'Office_Network',
                              ip.created_timestamp = datetime()
            """, ips, BATCH)
            print(f"     [OK] Created {len(ips):,} IPAddress nodes")

            # 5. Service nodes
            print("  [5/7] Creating Service nodes...")
            services = [{'service_id': self.generate_id('SVC', s), 'service_name': s}
                        for s in df['logon_service'].dropna().unique()]
            self._run_batches(session, """
                UNWIND $rows AS row
                MERGE (svc:Service {service_id: row.service_id})
                ON CREATE SET svc.service_name = row.service_name, svc.service_type = 'KERBEROS',
                              svc.security_context = 'AUTHENTICATION', svc.created_timestamp = datetime()
            """, services, BATCH)
            print(f"     [OK] Created {len(services):,} Service nodes")

            # 6. Group nodes
            print("  [6/7] Creating Group nodes...")
            groups = []
            for d in df['domain'].dropna().unique():
                gname = f"{d.split('.')[0].upper()}_USERS"
                groups.append({'group_id': self.generate_id('G', gname), 'group_name': gname})
            self._run_batches(session, """
                UNWIND $rows AS row
                MERGE (g:Group {group_id: row.group_id})
                ON CREATE SET g.group_name = row.group_name, g.privilege_level = 'LOW',
                              g.created_timestamp = datetime()
            """, groups, BATCH)
            print(f"     [OK] Created {len(groups):,} Group nodes")

            # 7. Event nodes — batch UNWIND (1.8M rows)
            print("  [7/7] Creating Event nodes...")
            total = len(df)
            event_batch = []
            processed = 0
            for row in df.itertuples(index=False):
                event_id = self.generate_event_id(
                    row.username, row.hostname, row.timestamp, row.event_source, row.event_type
                )
                event_batch.append({
                    'event_id':     event_id,
                    'event_type':   row.event_type,
                    'event_source': row.event_source,
                    'timestamp':    row.timestamp,
                    'success':      bool(row.success),
                    'failure_reason': row.failure_reason if pd.notna(row.failure_reason) else None,
                })
                if len(event_batch) == BATCH:
                    session.run("""
                        UNWIND $rows AS row
                        MERGE (e:Event {event_id: row.event_id})
                        ON CREATE SET e.event_type = row.event_type, e.event_source = row.event_source,
                                      e.timestamp = row.timestamp, e.success = row.success,
                                      e.failure_reason = row.failure_reason, e.created_timestamp = datetime()
                    """, rows=event_batch)
                    processed += len(event_batch)
                    event_batch = []
                    if processed % 100000 == 0:
                        pct = processed / total * 100
                        print(f"     ...processed {processed:,} / {total:,} events ({pct:.1f}%)")

            if event_batch:
                session.run("""
                    UNWIND $rows AS row
                    MERGE (e:Event {event_id: row.event_id})
                    ON CREATE SET e.event_type = row.event_type, e.event_source = row.event_source,
                                  e.timestamp = row.timestamp, e.success = row.success,
                                  e.failure_reason = row.failure_reason, e.created_timestamp = datetime()
                """, rows=event_batch)

            print(f"     [OK] Created {total:,} Event nodes")

    def create_relationships(self, df):
        """Create relationships between nodes using batch UNWIND"""
        print("\n" + "="*70)
        print("CREATING RELATIONSHIPS")
        print("="*70)

        records = self._prepare_records(df)
        total = len(records)
        BATCH = 500

        with self.driver.session() as session:
            for i in range(0, total, BATCH):
                batch = records[i:i + BATCH]

                # 1. LOGIN_FROM (always)
                session.run("""
                    UNWIND $rows AS row
                    MATCH (u:User {user_id: row.user_id})
                    MATCH (h:Hostname {hostname_id: row.hostname_id})
                    MERGE (u)-[r:LOGIN_FROM]->(h)
                    ON CREATE SET r.timestamp = row.timestamp, r.success = row.success,
                                  r.event_source = row.event_source, r.frequency = 1,
                                  r.first_seen = row.timestamp, r.last_seen = row.timestamp
                    ON MATCH SET r.frequency = r.frequency + 1, r.last_seen = row.timestamp
                """, rows=batch)

                # 2. AUTHENTICATED_VIA (if server_id exists)
                session.run("""
                    UNWIND $rows AS row
                    WITH row WHERE row.server_id IS NOT NULL
                    MATCH (u:User {user_id: row.user_id})
                    MATCH (s:Server {server_id: row.server_id})
                    MERGE (u)-[r:AUTHENTICATED_VIA]->(s)
                    ON CREATE SET r.timestamp = row.timestamp, r.success = row.success,
                                  r.failure_reason = row.failure_reason, r.frequency = 1,
                                  r.first_seen = row.timestamp, r.last_seen = row.timestamp
                    ON MATCH SET r.frequency = r.frequency + 1, r.last_seen = row.timestamp
                """, rows=batch)

                # 3. FAILED_LOGIN (if not success AND server_id exists)
                session.run("""
                    UNWIND $rows AS row
                    WITH row WHERE row.server_id IS NOT NULL AND row.success = false
                    MATCH (u:User {user_id: row.user_id})
                    MATCH (s:Server {server_id: row.server_id})
                    MERGE (u)-[r:FAILED_LOGIN]->(s)
                    ON CREATE SET r.timestamp = row.timestamp, r.failure_reason = row.failure_reason,
                                  r.count = 1, r.event_source = row.event_source, r.last_failure = row.timestamp
                    ON MATCH SET r.count = r.count + 1, r.last_failure = row.timestamp
                """, rows=batch)

                # 4. CONNECTED_FROM (always)
                session.run("""
                    UNWIND $rows AS row
                    MATCH (u:User {user_id: row.user_id})
                    MATCH (ip:IPAddress {ip_id: row.ip_id})
                    MERGE (u)-[r:CONNECTED_FROM]->(ip)
                    ON CREATE SET r.timestamp = row.timestamp, r.frequency = 1,
                                  r.event_source = row.event_source,
                                  r.first_seen = row.timestamp, r.last_seen = row.timestamp
                    ON MATCH SET r.frequency = r.frequency + 1, r.last_seen = row.timestamp
                """, rows=batch)

                # 5. USED_IP (always)
                session.run("""
                    UNWIND $rows AS row
                    MATCH (h:Hostname {hostname_id: row.hostname_id})
                    MATCH (ip:IPAddress {ip_id: row.ip_id})
                    MERGE (h)-[r:USED_IP]->(ip)
                    ON CREATE SET r.timestamp = row.timestamp, r.frequency = 1,
                                  r.first_seen = row.timestamp, r.last_seen = row.timestamp
                    ON MATCH SET r.frequency = r.frequency + 1, r.last_seen = row.timestamp
                """, rows=batch)

                # 6. USED_SERVICE (if service_id exists)
                session.run("""
                    UNWIND $rows AS row
                    WITH row WHERE row.service_id IS NOT NULL
                    MATCH (u:User {user_id: row.user_id})
                    MATCH (svc:Service {service_id: row.service_id})
                    MERGE (u)-[r:USED_SERVICE]->(svc)
                    ON CREATE SET r.timestamp = row.timestamp, r.frequency = 1,
                                  r.first_seen = row.timestamp, r.last_seen = row.timestamp
                    ON MATCH SET r.frequency = r.frequency + 1, r.last_seen = row.timestamp
                """, rows=batch)

                # 7. REFERENCES (always)
                session.run("""
                    UNWIND $rows AS row
                    MATCH (e:Event {event_id: row.event_id})
                    MATCH (u:User {user_id: row.user_id})
                    MERGE (e)-[r:REFERENCES]->(u)
                    ON CREATE SET r.timestamp = row.timestamp
                """, rows=batch)

                # 8. MEMBER_OF (if group_id exists)
                session.run("""
                    UNWIND $rows AS row
                    WITH row WHERE row.group_id IS NOT NULL
                    MATCH (u:User {user_id: row.user_id})
                    MATCH (g:Group {group_id: row.group_id})
                    MERGE (u)-[r:MEMBER_OF]->(g)
                    ON CREATE SET r.since = row.timestamp
                """, rows=batch)

                processed = i + len(batch)
                if processed % 100000 == 0 or processed == total:
                    pct = processed / total * 100
                    print(f"  ...processed {processed:,} / {total:,} ({pct:.1f}%)")

        print(f"  [OK] Created relationships for {total:,} events")

    def ingest_lockouts(self, path='data/restructured_data/account_lockouts.csv'):
        """Ingest account lockout events as User-LOCKED_OUT->Server relationships"""
        print("\n" + "="*70)
        print("INGESTING LOCKOUTS")
        print("="*70)

        if not os.path.exists(path):
            print(f"  [SKIP] {path} not found")
            return

        df = pd.read_csv(path, low_memory=False)
        print(f"  [OK] Loaded {len(df):,} lockout events")

        records = []
        for row in df.itertuples(index=False):
            if pd.isna(row.username) or pd.isna(row.dc_name):
                continue
            records.append({
                'user_id':   self.generate_id('U', row.username),
                'username':  row.username,
                'server_id': self.generate_id('S', row.dc_name),
                'dc_name':   row.dc_name,
                'timestamp': str(row.timestamp) if pd.notna(row.timestamp) else None,
            })

        BATCH = 500
        total_users_created = 0
        with self.driver.session() as session:
            for i in range(0, len(records), BATCH):
                batch = records[i:i + BATCH]
                # Ensure User exists (some lockout users may not have logon events)
                session.run("""
                    UNWIND $rows AS row
                    MERGE (u:User {user_id: row.user_id})
                    ON CREATE SET u.username = row.username, u.created_timestamp = datetime()
                """, rows=batch)
                # Ensure Server exists
                session.run("""
                    UNWIND $rows AS row
                    MERGE (s:Server {server_id: row.server_id})
                    ON CREATE SET s.name = row.dc_name, s.type = 'DOMAIN_CONTROLLER',
                                  s.criticality = 'CRITICAL', s.created_timestamp = datetime()
                """, rows=batch)
                # Create LOCKED_OUT relationship with count
                session.run("""
                    UNWIND $rows AS row
                    MATCH (u:User {user_id: row.user_id})
                    MATCH (s:Server {server_id: row.server_id})
                    MERGE (u)-[r:LOCKED_OUT]->(s)
                    ON CREATE SET r.count = 1, r.first_lockout = row.timestamp, r.last_lockout = row.timestamp
                    ON MATCH SET r.count = r.count + 1, r.last_lockout = row.timestamp
                """, rows=batch)
                total_users_created += len(batch)

        print(f"  [OK] Ingested {len(records):,} LOCKED_OUT relationships")

    def ingest_privileged_actions(self, path='data/restructured_data/privileged_actions.csv'):
        """Ingest admin actions and group changes"""
        print("\n" + "="*70)
        print("INGESTING PRIVILEGED ACTIONS")
        print("="*70)

        if not os.path.exists(path):
            print(f"  [SKIP] {path} not found")
            return

        df = pd.read_csv(path, low_memory=False)
        print(f"  [OK] Loaded {len(df):,} privileged actions")
        print(f"      Breakdown: {df['action_type'].value_counts().to_dict()}")

        # 1. ADMIN ACTIONS — User (actor) -[ADMIN_ACTION_ON]-> User (target)
        admin = df[df['action_type'] == 'admin_action'].copy()
        admin_records = []
        for row in admin.itertuples(index=False):
            if pd.isna(row.actor_username) or pd.isna(row.target_username):
                continue
            admin_records.append({
                'actor_id':    self.generate_id('U', row.actor_username),
                'actor_name':  row.actor_username,
                'target_id':   self.generate_id('U', row.target_username),
                'target_name': row.target_username,
                'timestamp':   str(row.timestamp) if pd.notna(row.timestamp) else None,
                'description': row.description if pd.notna(row.description) else None,
            })

        BATCH = 500
        with self.driver.session() as session:
            for i in range(0, len(admin_records), BATCH):
                batch = admin_records[i:i + BATCH]
                # Ensure both actor and target users exist
                session.run("""
                    UNWIND $rows AS row
                    MERGE (a:User {user_id: row.actor_id})
                    ON CREATE SET a.username = row.actor_name, a.created_timestamp = datetime()
                    MERGE (t:User {user_id: row.target_id})
                    ON CREATE SET t.username = row.target_name, t.created_timestamp = datetime()
                """, rows=batch)
                # Create ADMIN_ACTION_ON
                session.run("""
                    UNWIND $rows AS row
                    MATCH (a:User {user_id: row.actor_id})
                    MATCH (t:User {user_id: row.target_id})
                    MERGE (a)-[r:ADMIN_ACTION_ON]->(t)
                    ON CREATE SET r.count = 1, r.first_action = row.timestamp, r.last_action = row.timestamp,
                                  r.last_description = row.description
                    ON MATCH SET r.count = r.count + 1, r.last_action = row.timestamp,
                                 r.last_description = row.description
                """, rows=batch)
        print(f"  [OK] Ingested {len(admin_records):,} ADMIN_ACTION_ON relationships")

        # 2. GROUP CHANGES — User (target) -[REAL_MEMBER_OF]-> Group
        group_chg = df[df['action_type'] == 'group_change'].copy()
        group_records = []
        for row in group_chg.itertuples(index=False):
            if pd.isna(row.target_username) or pd.isna(row.group_name):
                continue
            gname = str(row.group_name).strip()
            # Determine privilege level from group name
            gname_upper = gname.upper()
            if any(k in gname_upper for k in ['ADMIN', 'DOMAIN ADMIN', 'ENTERPRISE', 'SCHEMA']):
                priv = 'ADMIN'
            elif any(k in gname_upper for k in ['VPN', 'POWER', 'BACKUP', 'ACCOUNT OPERATOR']):
                priv = 'HIGH'
            elif 'ACL' in gname_upper or 'PRIV' in gname_upper:
                priv = 'MEDIUM'
            else:
                priv = 'LOW'

            group_records.append({
                'user_id':    self.generate_id('U', row.target_username),
                'username':   row.target_username,
                'group_id':   self.generate_id('G', gname),
                'group_name': gname,
                'priv':       priv,
                'timestamp':  str(row.timestamp) if pd.notna(row.timestamp) else None,
            })

        with self.driver.session() as session:
            for i in range(0, len(group_records), BATCH):
                batch = group_records[i:i + BATCH]
                # Ensure user and group exist (group may have richer privilege now)
                session.run("""
                    UNWIND $rows AS row
                    MERGE (u:User {user_id: row.user_id})
                    ON CREATE SET u.username = row.username, u.created_timestamp = datetime()
                """, rows=batch)
                session.run("""
                    UNWIND $rows AS row
                    MERGE (g:Group {group_id: row.group_id})
                    ON CREATE SET g.group_name = row.group_name, g.privilege_level = row.priv,
                                  g.created_timestamp = datetime()
                    ON MATCH SET g.group_name = row.group_name, g.privilege_level = row.priv
                """, rows=batch)
                session.run("""
                    UNWIND $rows AS row
                    MATCH (u:User {user_id: row.user_id})
                    MATCH (g:Group {group_id: row.group_id})
                    MERGE (u)-[r:REAL_MEMBER_OF]->(g)
                    ON CREATE SET r.added_at = row.timestamp
                """, rows=batch)
        print(f"  [OK] Ingested {len(group_records):,} REAL_MEMBER_OF relationships")

    def validate_ingestion(self):
        """Validate ingestion statistics"""
        print("\n" + "="*70)
        print("VALIDATION STATISTICS")
        print("="*70)

        with self.driver.session() as session:
            queries = {
                "User nodes": "MATCH (u:User) RETURN count(u) as count",
                "Hostname nodes": "MATCH (h:Hostname) RETURN count(h) as count",
                "Server nodes": "MATCH (s:Server) RETURN count(s) as count",
                "IPAddress nodes": "MATCH (ip:IPAddress) RETURN count(ip) as count",
                "Service nodes": "MATCH (svc:Service) RETURN count(svc) as count",
                "Group nodes": "MATCH (g:Group) RETURN count(g) as count",
                "Event nodes": "MATCH (e:Event) RETURN count(e) as count",
                "LOGIN_FROM relationships": "MATCH ()-[r:LOGIN_FROM]->() RETURN count(r) as count",
                "AUTHENTICATED_VIA relationships": "MATCH ()-[r:AUTHENTICATED_VIA]->() RETURN count(r) as count",
                "FAILED_LOGIN relationships": "MATCH ()-[r:FAILED_LOGIN]->() RETURN count(r) as count",
                "CONNECTED_FROM relationships": "MATCH ()-[r:CONNECTED_FROM]->() RETURN count(r) as count",
                "USED_IP relationships": "MATCH ()-[r:USED_IP]->() RETURN count(r) as count",
                "USED_SERVICE relationships": "MATCH ()-[r:USED_SERVICE]->() RETURN count(r) as count",
                "MEMBER_OF relationships": "MATCH ()-[r:MEMBER_OF]->() RETURN count(r) as count",
                "REFERENCES relationships": "MATCH ()-[r:REFERENCES]->() RETURN count(r) as count",
                "LOCKED_OUT relationships": "MATCH ()-[r:LOCKED_OUT]->() RETURN count(r) as count",
                "ADMIN_ACTION_ON relationships": "MATCH ()-[r:ADMIN_ACTION_ON]->() RETURN count(r) as count",
                "REAL_MEMBER_OF relationships": "MATCH ()-[r:REAL_MEMBER_OF]->() RETURN count(r) as count",
            }

            for label, query in queries.items():
                result = session.run(query).single()
                count = result['count']
                print(f"  {label:<35}: {count:,}")

    def ingest(self, csv_path):
        """Run complete ingestion pipeline"""
        print("\n" + "="*70)
        print("PHASE 2: NEO4J INGESTION")
        print("="*70)
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            # Step 1: Create schema
            self.create_constraints_and_indexes()

            # Step 2: Load data
            df = self.load_data(csv_path)

            # Step 3: Create nodes
            self.create_nodes(df)

            # Step 4: Create relationships
            self.create_relationships(df)

            # Step 5: Ingest auxiliary datasets (lockouts, admin actions, group changes)
            self.ingest_lockouts()
            self.ingest_privileged_actions()

            # Step 6: Validate
            self.validate_ingestion()

            print("\n" + "="*70)
            print("INGESTION COMPLETE")
            print("="*70)
            print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("\nNext steps:")
            print("  1. Run Phase 3: Rule-Based Knowledge")
            print("  2. Implement 7 domain rules in Cypher")
            print("  3. Store rule violations on User nodes")

        except Exception as e:
            print(f"\n[ERROR] Ingestion failed: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    # Configuration
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "lalarasa"
    CSV_PATH = "data/restructured_data/unified_logon_events.csv"

    # Run ingestion
    ingestor = Neo4jIngestor(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    try:
        ingestor.ingest(CSV_PATH)
    finally:
        ingestor.close()
