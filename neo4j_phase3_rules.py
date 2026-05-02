#!/usr/bin/env python3
"""
Phase 3: Rule-Based Knowledge Engine
Implement 7 domain rules in Neo4j Cypher
"""

from neo4j import GraphDatabase
from datetime import datetime

class RuleEngine:
    def __init__(self, uri, user, password):
        """Initialize Neo4j connection"""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        """Close connection"""
        self.driver.close()

    def implement_rule_R001(self):
        """Rule 1: Normal Login Hosts"""
        print("\n[Phase 3] Implementing Rule R001: Normal Login Hosts...")

        with self.driver.session() as session:
            result = session.run("""
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
                RETURN count(u) as updated_users
            """)

            count = result.single()['updated_users']
            print(f"  [OK] Updated {count:,} users with R001")
            return count

    def implement_rule_R002(self):
        """Rule 2: Business Hours Pattern"""
        print("\n[Phase 3] Implementing Rule R002: Business Hours Pattern...")

        with self.driver.session() as session:
            result = session.run("""
                MATCH (u:User)-[r:LOGIN_FROM]->(h:Hostname)
                WITH u, count(*) as total_logins,
                     size([x IN collect(r) WHERE
                           x.timestamp IS NOT NULL
                           AND x.timestamp =~ '^[0-9]{4}-.*'
                           AND datetime(replace(x.timestamp, ' ', 'T')).hour >= 8
                           AND datetime(replace(x.timestamp, ' ', 'T')).hour < 18
                           AND datetime(replace(x.timestamp, ' ', 'T')).dayOfWeek IN [1,2,3,4,5]
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
                RETURN count(u) as updated_users
            """)

            count = result.single()['updated_users']
            print(f"  [OK] Updated {count:,} users with R002")
            return count

    def implement_rule_R003(self):
        """Rule 3: Shared Device Detection"""
        print("\n[Phase 3] Implementing Rule R003: Shared Device Detection...")

        with self.driver.session() as session:
            # First, mark shared devices
            session.run("""
                MATCH (h:Hostname)<-[:LOGIN_FROM]-(u:User)
                WITH h, count(DISTINCT u) as user_count, collect(DISTINCT u.username) as users
                SET h.user_count = user_count,
                    h.is_shared = CASE WHEN user_count > 5 THEN true ELSE false END
            """)

            # Then, set rule violations for users
            result = session.run("""
                MATCH (u:User)-[:LOGIN_FROM]->(h:Hostname)
                WITH u, size([h IN collect(DISTINCT h) WHERE h.user_count > 5]) as shared_device_count
                SET u.rule_R003_shared_devices = shared_device_count,
                    u.rule_R003_violation = CASE WHEN shared_device_count > 0 THEN true ELSE false END,
                    u.rule_R003_severity = CASE
                      WHEN shared_device_count > 5 THEN 'HIGH'
                      WHEN shared_device_count > 2 THEN 'MEDIUM'
                      WHEN shared_device_count > 0 THEN 'LOW'
                      ELSE 'NONE'
                    END
                RETURN count(u) as updated_users
            """)

            count = result.single()['updated_users']
            print(f"  [OK] Updated {count:,} users with R003")
            return count

    def implement_rule_R004(self):
        """Rule 4: Uncommon Server Access"""
        print("\n[Phase 3] Implementing Rule R004: Uncommon Server Access...")

        with self.driver.session() as session:
            result = session.run("""
                MATCH (u:User)-[r:AUTHENTICATED_VIA]->(s:Server)
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
                RETURN count(u) as updated_users
            """)

            count = result.single()['updated_users']
            print(f"  [OK] Updated {count:,} users with R004")
            return count

    def implement_rule_R005(self):
        """Rule 5: Failed Login Spike"""
        print("\n[Phase 3] Implementing Rule R005: Failed Login Spike...")

        with self.driver.session() as session:
            result = session.run("""
                MATCH (u:User)-[r:FAILED_LOGIN]->(s:Server)
                WITH u, count(*) as total_failures,
                     max(r.count) as max_single_relation_failures
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
                RETURN count(u) as updated_users
            """)

            count = result.single()['updated_users']
            print(f"  [OK] Updated {count:,} users with R005")
            return count

    def implement_rule_R006(self):
        """Rule 6: Unusual IP Address"""
        print("\n[Phase 3] Implementing Rule R006: Unusual IP Address...")

        with self.driver.session() as session:
            result = session.run("""
                MATCH (u:User)-[r:CONNECTED_FROM]->(ip:IPAddress)
                WHERE NOT ip.range_category IN ['Office_Network', 'VPN']
                WITH u, count(DISTINCT ip) as unusual_ips,
                     collect(DISTINCT ip.address) as unusual_ip_list
                SET u.rule_R006_unusual_ips = unusual_ips,
                    u.rule_R006_unusual_ip_list = unusual_ip_list,
                    u.rule_R006_violation = CASE WHEN unusual_ips > 0 THEN true ELSE false END,
                    u.rule_R006_severity = CASE
                      WHEN unusual_ips > 5 THEN 'HIGH'
                      WHEN unusual_ips > 2 THEN 'MEDIUM'
                      WHEN unusual_ips > 0 THEN 'LOW'
                      ELSE 'NONE'
                    END
                RETURN count(u) as updated_users
            """)

            count = result.single()['updated_users']
            print(f"  [OK] Updated {count:,} users with R006")
            return count

    def implement_rule_R007(self):
        """Rule 7: After-Hours Privileged Access"""
        print("\n[Phase 3] Implementing Rule R007: After-Hours Privileged Access...")

        with self.driver.session() as session:
            result = session.run("""
                MATCH (u:User)-[r:MEMBER_OF]->(g:Group)
                WHERE g.privilege_level IN ['HIGH', 'ADMIN']
                MATCH (u)-[r2:AUTHENTICATED_VIA]->(s:Server)
                WHERE (s.type = 'DOMAIN_CONTROLLER' OR s.criticality = 'CRITICAL')
                  AND r2.timestamp IS NOT NULL
                  AND r2.timestamp =~ '^[0-9]{4}-.*'
                  AND (datetime(replace(r2.timestamp, ' ', 'T')).hour < 8 OR datetime(replace(r2.timestamp, ' ', 'T')).hour >= 18
                       OR NOT datetime(replace(r2.timestamp, ' ', 'T')).dayOfWeek IN [1,2,3,4,5])
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
                RETURN count(u) as updated_users
            """)

            count = result.single()['updated_users']
            print(f"  [OK] Updated {count:,} users with R007")
            return count

    def implement_rule_R008(self):
        """Rule 8: Frequent Account Lockouts (>= 3 lockout events)"""
        print("\n[Phase 3] Implementing Rule R008: Frequent Lockouts...")

        with self.driver.session() as session:
            result = session.run("""
                MATCH (u:User)
                OPTIONAL MATCH (u)-[r:LOCKED_OUT]->()
                WITH u, COALESCE(sum(r.count), 0) as total_lockouts
                SET u.rule_R008_lockouts = total_lockouts,
                    u.rule_R008_violation = total_lockouts >= 3,
                    u.rule_R008_severity = CASE
                      WHEN total_lockouts >= 10 THEN 'HIGH'
                      WHEN total_lockouts >= 5  THEN 'MEDIUM'
                      WHEN total_lockouts >= 3  THEN 'LOW'
                      ELSE 'NONE'
                    END
                RETURN count(u) as updated_users
            """)
            count = result.single()['updated_users']
            print(f"  [OK] Updated {count:,} users with R008")
            return count

    def implement_rule_R009(self):
        """Rule 9: Excessive Admin Actions (actor performing too many)"""
        print("\n[Phase 3] Implementing Rule R009: Excessive Admin Actions...")

        with self.driver.session() as session:
            result = session.run("""
                MATCH (u:User)
                OPTIONAL MATCH (u)-[r:ADMIN_ACTION_ON]->()
                WITH u, COALESCE(sum(r.count), 0) as actions_performed
                SET u.rule_R009_admin_actions = actions_performed,
                    u.rule_R009_violation = actions_performed >= 50,
                    u.rule_R009_severity = CASE
                      WHEN actions_performed >= 200 THEN 'HIGH'
                      WHEN actions_performed >= 100 THEN 'MEDIUM'
                      WHEN actions_performed >= 50  THEN 'LOW'
                      ELSE 'NONE'
                    END
                RETURN count(u) as updated_users
            """)
            count = result.single()['updated_users']
            print(f"  [OK] Updated {count:,} users with R009")
            return count

    def implement_rule_R010(self):
        """Rule 10: Sensitive Group Membership (ADMIN/HIGH privilege groups)"""
        print("\n[Phase 3] Implementing Rule R010: Sensitive Group Membership...")

        with self.driver.session() as session:
            result = session.run("""
                MATCH (u:User)
                OPTIONAL MATCH (u)-[:REAL_MEMBER_OF]->(g:Group)
                WHERE g.privilege_level IN ['ADMIN', 'HIGH']
                WITH u, count(DISTINCT g) as sensitive_groups
                SET u.rule_R010_sensitive_groups = sensitive_groups,
                    u.rule_R010_violation = sensitive_groups >= 1,
                    u.rule_R010_severity = CASE
                      WHEN sensitive_groups >= 3 THEN 'HIGH'
                      WHEN sensitive_groups >= 2 THEN 'MEDIUM'
                      WHEN sensitive_groups >= 1 THEN 'LOW'
                      ELSE 'NONE'
                    END
                RETURN count(u) as updated_users
            """)
            count = result.single()['updated_users']
            print(f"  [OK] Updated {count:,} users with R010")
            return count

    def aggregate_violations(self):
        """Aggregate all rule violations into summary"""
        print("\n[Phase 3] Aggregating rule violations...")

        with self.driver.session() as session:
            result = session.run("""
                MATCH (u:User)
                SET u.rule_violations =
                    (CASE WHEN u.rule_R001_violation THEN 1 ELSE 0 END) +
                    (CASE WHEN u.rule_R002_violation THEN 1 ELSE 0 END) +
                    (CASE WHEN u.rule_R003_violation THEN 1 ELSE 0 END) +
                    (CASE WHEN u.rule_R004_violation THEN 1 ELSE 0 END) +
                    (CASE WHEN u.rule_R005_violation THEN 1 ELSE 0 END) +
                    (CASE WHEN u.rule_R006_violation THEN 1 ELSE 0 END) +
                    (CASE WHEN u.rule_R007_violation THEN 1 ELSE 0 END) +
                    (CASE WHEN u.rule_R008_violation THEN 1 ELSE 0 END) +
                    (CASE WHEN u.rule_R009_violation THEN 1 ELSE 0 END) +
                    (CASE WHEN u.rule_R010_violation THEN 1 ELSE 0 END),
                    u.max_rule_severity = CASE
                      WHEN u.rule_R001_severity = 'HIGH' OR u.rule_R002_severity = 'HIGH' OR u.rule_R003_severity = 'HIGH'
                           OR u.rule_R004_severity = 'HIGH' OR u.rule_R005_severity = 'HIGH'
                           OR u.rule_R006_severity = 'HIGH' OR u.rule_R007_severity = 'HIGH'
                           OR u.rule_R008_severity = 'HIGH' OR u.rule_R009_severity = 'HIGH'
                           OR u.rule_R010_severity = 'HIGH' THEN 'HIGH'
                      WHEN u.rule_R001_severity = 'MEDIUM' OR u.rule_R002_severity = 'MEDIUM' OR u.rule_R003_severity = 'MEDIUM'
                           OR u.rule_R004_severity = 'MEDIUM' OR u.rule_R005_severity = 'MEDIUM'
                           OR u.rule_R006_severity = 'MEDIUM' OR u.rule_R007_severity = 'MEDIUM'
                           OR u.rule_R008_severity = 'MEDIUM' OR u.rule_R009_severity = 'MEDIUM'
                           OR u.rule_R010_severity = 'MEDIUM' THEN 'MEDIUM'
                      ELSE 'LOW'
                    END
                RETURN count(u) as total_users
            """)

            total = result.single()['total_users']
            print(f"  [OK] Aggregated violations for {total:,} users")

    def validate_rules(self):
        """Validate rule implementation"""
        print("\n[Phase 3] Validating rules...")

        with self.driver.session() as session:
            queries = {
                "Users with R001 violation": "MATCH (u:User) WHERE u.rule_R001_violation = true RETURN count(u) as count",
                "Users with R002 violation": "MATCH (u:User) WHERE u.rule_R002_violation = true RETURN count(u) as count",
                "Users with R003 violation": "MATCH (u:User) WHERE u.rule_R003_violation = true RETURN count(u) as count",
                "Users with R004 violation": "MATCH (u:User) WHERE u.rule_R004_violation = true RETURN count(u) as count",
                "Users with R005 violation": "MATCH (u:User) WHERE u.rule_R005_violation = true RETURN count(u) as count",
                "Users with R006 violation": "MATCH (u:User) WHERE u.rule_R006_violation = true RETURN count(u) as count",
                "Users with R007 violation": "MATCH (u:User) WHERE u.rule_R007_violation = true RETURN count(u) as count",
                "Users with R008 violation": "MATCH (u:User) WHERE u.rule_R008_violation = true RETURN count(u) as count",
                "Users with R009 violation": "MATCH (u:User) WHERE u.rule_R009_violation = true RETURN count(u) as count",
                "Users with R010 violation": "MATCH (u:User) WHERE u.rule_R010_violation = true RETURN count(u) as count",
                "Users with 0 violations": "MATCH (u:User) WHERE u.rule_violations = 0 RETURN count(u) as count",
                "Users with 1-2 violations": "MATCH (u:User) WHERE u.rule_violations IN [1,2] RETURN count(u) as count",
                "Users with 3+ violations": "MATCH (u:User) WHERE u.rule_violations >= 3 RETURN count(u) as count",
                "Users with HIGH severity": "MATCH (u:User) WHERE u.max_rule_severity = 'HIGH' RETURN count(u) as count",
                "Users with MEDIUM severity": "MATCH (u:User) WHERE u.max_rule_severity = 'MEDIUM' RETURN count(u) as count",
                "Users with LOW severity": "MATCH (u:User) WHERE u.max_rule_severity = 'LOW' RETURN count(u) as count",
            }

            for label, query in queries.items():
                result = session.run(query).single()
                count = result['count'] if result else 0
                print(f"  {label:<35}: {count:,}")

    def run_all_rules(self):
        """Execute all rules in order"""
        print("\n" + "="*70)
        print("PHASE 3: RULE-BASED KNOWLEDGE ENGINE")
        print("="*70)
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            # Execute rules in dependency order
            self.implement_rule_R001()
            self.implement_rule_R002()
            self.implement_rule_R006()
            self.implement_rule_R003()
            self.implement_rule_R004()
            self.implement_rule_R005()
            self.implement_rule_R007()
            self.implement_rule_R008()
            self.implement_rule_R009()
            self.implement_rule_R010()

            # Aggregate violations
            self.aggregate_violations()

            # Validate
            self.validate_rules()

            print("\n" + "="*70)
            print("PHASE 3 COMPLETE")
            print("="*70)
            print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("\nNext steps:")
            print("  1. Run Phase 4: Graph Feature Extraction")
            print("  2. Extract 8 graph-based features from relationships")
            print("  3. Export features to CSV for Isolation Forest")

        except Exception as e:
            print(f"\n[ERROR] Rule implementation failed: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    # Configuration
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "lalarasa"

    # Run rules
    engine = RuleEngine(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    try:
        engine.run_all_rules()
    finally:
        engine.close()
