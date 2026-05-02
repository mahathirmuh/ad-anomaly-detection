#!/usr/bin/env python3
"""
Phase 4: Graph Feature Extraction
Extract 8 graph-based features from Neo4j relationships
"""

from neo4j import GraphDatabase
import pandas as pd
from datetime import datetime
import os

class FeatureExtractor:
    def __init__(self, uri, user, password):
        """Initialize Neo4j connection"""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        """Close connection"""
        self.driver.close()

    def extract_feature_1_host_diversity(self):
        """Feature 1: Host Diversity Score"""
        print("\n[Phase 4] Extracting Feature 1: Host Diversity...")

        with self.driver.session() as session:
            session.run("""
                MATCH (u:User)-[:LOGIN_FROM]->(h:Hostname)
                WITH count(DISTINCT u) as total_users
                MATCH (u2:User)-[:LOGIN_FROM]->(h2:Hostname)
                WITH u2, count(DISTINCT h2) as unique_hosts, total_users
                WITH u2, unique_hosts,
                     avg(unique_hosts) as avg_unique_hosts
                SET u2.feature_host_diversity = ROUND(1.0 * unique_hosts / COALESCE(avg_unique_hosts, 1), 4)
                RETURN count(u2) as updated
            """)

        print("  [OK] Feature 1 calculated")

    def extract_feature_2_critical_server_ratio(self):
        """Feature 2: Critical Server Access Ratio"""
        print("\n[Phase 4] Extracting Feature 2: Critical Server Ratio...")

        with self.driver.session() as session:
            session.run("""
                MATCH (u:User)-[:AUTHENTICATED_VIA]->(s:Server)
                WITH u, count(DISTINCT s) as total_servers, collect(DISTINCT s) as servers
                WITH u, total_servers,
                     size([s2 IN servers WHERE s2.type = 'DOMAIN_CONTROLLER' OR s2.criticality IN ['CRITICAL', 'HIGH']]) as critical_count
                SET u.feature_critical_server_ratio = CASE
                  WHEN total_servers > 0 THEN ROUND(1.0 * critical_count / total_servers, 4)
                  ELSE 0
                END
                RETURN count(u) as updated
            """)

        print("  [OK] Feature 2 calculated")

    def extract_feature_3_failure_ratio(self):
        """Feature 3: Failed Login Ratio"""
        print("\n[Phase 4] Extracting Feature 3: Failure Ratio...")

        with self.driver.session() as session:
            session.run("""
                MATCH (u:User)
                OPTIONAL MATCH (u)-[r:LOGIN_FROM]->(h:Hostname)
                WITH u, count(r) as total_logins
                OPTIONAL MATCH (u)-[r2:FAILED_LOGIN]->(s:Server)
                WITH u, total_logins, COALESCE(sum(r2.count), 0) as failed_logins
                SET u.feature_failure_ratio = CASE
                  WHEN total_logins > 0 THEN ROUND(1.0 * failed_logins / total_logins, 4)
                  ELSE 0
                END
                RETURN count(u) as updated
            """)

        print("  [OK] Feature 3 calculated")

    def extract_feature_4_shared_device_risk(self):
        """Feature 4: Shared Device Risk Score"""
        print("\n[Phase 4] Extracting Feature 4: Shared Device Risk...")

        with self.driver.session() as session:
            session.run("""
                MATCH (u:User)-[:LOGIN_FROM]->(h:Hostname)
                WITH u, count(DISTINCT h) as unique_devices,
                     sum(COALESCE(h.user_count, 1)) as total_device_users
                SET u.feature_shared_device_risk = CASE
                  WHEN unique_devices > 0 THEN ROUND(1.0 * total_device_users / unique_devices, 4)
                  ELSE 1.0
                END
                RETURN count(u) as updated
            """)

        print("  [OK] Feature 4 calculated")

    def extract_feature_5_ip_network_risk(self):
        """Feature 5: IP Network Risk Score"""
        print("\n[Phase 4] Extracting Feature 5: IP Network Risk...")

        with self.driver.session() as session:
            session.run("""
                MATCH (u:User)-[:CONNECTED_FROM]->(ip:IPAddress)
                WITH u, count(DISTINCT ip) as total_ips, collect(DISTINCT ip) as ips
                WITH u, total_ips,
                     size([ip2 IN ips WHERE NOT ip2.range_category IN ['Office_Network', 'VPN']]) as unusual_count
                SET u.feature_ip_network_risk = CASE
                  WHEN total_ips > 0 THEN ROUND(1.0 * unusual_count / total_ips, 4)
                  ELSE 0
                END
                RETURN count(u) as updated
            """)

        print("  [OK] Feature 5 calculated")

    def extract_feature_6_privilege_level(self):
        """Feature 6: Privilege Level"""
        print("\n[Phase 4] Extracting Feature 6: Privilege Level...")

        with self.driver.session() as session:
            session.run("""
                MATCH (u:User)
                OPTIONAL MATCH (u)-[:MEMBER_OF]->(g:Group)
                WITH u, max(CASE
                  WHEN g.privilege_level = 'ADMIN' THEN 4
                  WHEN g.privilege_level = 'HIGH' THEN 3
                  WHEN g.privilege_level = 'MEDIUM' THEN 2
                  ELSE 1
                END) as max_privilege
                SET u.feature_privilege_level = COALESCE(max_privilege, 1)
                RETURN count(u) as updated
            """)

        print("  [OK] Feature 6 calculated")

    def extract_feature_7_connectivity(self):
        """Feature 7: Graph Connectivity (Degree Centrality)"""
        print("\n[Phase 4] Extracting Feature 7: Connectivity Score...")

        with self.driver.session() as session:
            # First get total edges
            total_edges = session.run("""
                MATCH ()-[]-()
                RETURN count(*) as total
            """).single()['total']

            session.run("""
                MATCH (u:User)
                OPTIONAL MATCH (u)-[r]-()
                WITH u, count(r) as total_relationships, $total_edges as total_edges_in_graph
                SET u.feature_connectivity = CASE
                  WHEN total_edges_in_graph > 0 THEN ROUND(1.0 * total_relationships / total_edges_in_graph, 6)
                  ELSE 0
                END
                RETURN count(u) as updated
            """, total_edges=total_edges)

        print("  [OK] Feature 7 calculated")

    def extract_feature_8_rule_violations(self):
        """Feature 8: Rule Violations Count"""
        print("\n[Phase 4] Extracting Feature 8: Rule Violations...")

        with self.driver.session() as session:
            session.run("""
                MATCH (u:User)
                SET u.feature_rule_violations = COALESCE(u.rule_violations, 0)
                RETURN count(u) as updated
            """)

        print("  [OK] Feature 8 calculated")

    def extract_feature_9_lockout_count(self):
        """Feature 9: Account Lockout Count"""
        print("\n[Phase 4] Extracting Feature 9: Lockout Count...")

        with self.driver.session() as session:
            session.run("""
                MATCH (u:User)
                OPTIONAL MATCH (u)-[r:LOCKED_OUT]->()
                WITH u, COALESCE(sum(r.count), 0) as total_lockouts
                SET u.feature_lockout_count = total_lockouts
                RETURN count(u) as updated
            """)

        print("  [OK] Feature 9 calculated")

    def extract_feature_10_admin_actions(self):
        """Feature 10: Admin Actions Performed (as actor)"""
        print("\n[Phase 4] Extracting Feature 10: Admin Actions Performed...")

        with self.driver.session() as session:
            session.run("""
                MATCH (u:User)
                OPTIONAL MATCH (u)-[r:ADMIN_ACTION_ON]->()
                WITH u, COALESCE(sum(r.count), 0) as actions_performed
                SET u.feature_admin_actions = actions_performed
                RETURN count(u) as updated
            """)

        print("  [OK] Feature 10 calculated")

    def extract_feature_11_sensitive_groups(self):
        """Feature 11: Sensitive Group Membership Count"""
        print("\n[Phase 4] Extracting Feature 11: Sensitive Groups...")

        with self.driver.session() as session:
            session.run("""
                MATCH (u:User)
                OPTIONAL MATCH (u)-[:REAL_MEMBER_OF]->(g:Group)
                WHERE g.privilege_level IN ['ADMIN', 'HIGH']
                WITH u, count(DISTINCT g) as sensitive_groups
                SET u.feature_sensitive_groups = sensitive_groups
                RETURN count(u) as updated
            """)

        print("  [OK] Feature 11 calculated")

    def export_to_csv(self):
        """Export features to CSV"""
        print("\n[Phase 4] Exporting features to CSV...")

        with self.driver.session() as session:
            result = session.run("""
                MATCH (u:User)
                RETURN
                    u.user_id as user_id,
                    u.username as username,
                    COALESCE(u.feature_host_diversity, 0) as host_diversity,
                    COALESCE(u.feature_critical_server_ratio, 0) as critical_server_ratio,
                    COALESCE(u.feature_failure_ratio, 0) as failure_ratio,
                    COALESCE(u.feature_shared_device_risk, 1.0) as shared_device_risk,
                    COALESCE(u.feature_ip_network_risk, 0) as ip_network_risk,
                    COALESCE(u.feature_privilege_level, 1) as privilege_level,
                    COALESCE(u.feature_connectivity, 0) as connectivity,
                    COALESCE(u.feature_rule_violations, 0) as rule_violations,
                    COALESCE(u.feature_lockout_count, 0) as lockout_count,
                    COALESCE(u.feature_admin_actions, 0) as admin_actions,
                    COALESCE(u.feature_sensitive_groups, 0) as sensitive_groups
                ORDER BY u.user_id
            """)

            records = result.data()
            df = pd.DataFrame(records)

            output_path = "data/phase4_graph_features.csv"
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            df.to_csv(output_path, index=False)

            print(f"  [OK] Exported {len(df):,} users to {output_path}")
            return df

    def validate_features(self):
        """Validate feature extraction"""
        print("\n[Phase 4] Validating features...")

        with self.driver.session() as session:
            queries = {
                "Total users with features": "MATCH (u:User) WHERE u.feature_rule_violations IS NOT NULL RETURN count(u) as count",
                "Avg host diversity": "MATCH (u:User) RETURN avg(u.feature_host_diversity) as avg",
                "Avg failure ratio": "MATCH (u:User) RETURN avg(u.feature_failure_ratio) as avg",
                "Avg shared device risk": "MATCH (u:User) RETURN avg(u.feature_shared_device_risk) as avg",
                "Users with HIGH privilege": "MATCH (u:User) WHERE u.feature_privilege_level >= 3 RETURN count(u) as count",
                "Users with 3+ rule violations": "MATCH (u:User) WHERE u.feature_rule_violations >= 3 RETURN count(u) as count",
                "Max connectivity score": "MATCH (u:User) RETURN max(u.feature_connectivity) as max",
                "Users with lockouts": "MATCH (u:User) WHERE u.feature_lockout_count > 0 RETURN count(u) as count",
                "Users performing admin actions": "MATCH (u:User) WHERE u.feature_admin_actions > 0 RETURN count(u) as count",
                "Users in sensitive groups": "MATCH (u:User) WHERE u.feature_sensitive_groups > 0 RETURN count(u) as count",
            }

            for label, query in queries.items():
                result = session.run(query).single()
                value = result[list(result.keys())[0]]
                if isinstance(value, float):
                    print(f"  {label:<35}: {value:.6f}")
                else:
                    print(f"  {label:<35}: {value:,}")

    def run_extraction(self):
        """Execute complete feature extraction"""
        print("\n" + "="*70)
        print("PHASE 4: GRAPH FEATURE EXTRACTION")
        print("="*70)
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            # Extract all features
            self.extract_feature_1_host_diversity()
            self.extract_feature_2_critical_server_ratio()
            self.extract_feature_3_failure_ratio()
            self.extract_feature_4_shared_device_risk()
            self.extract_feature_5_ip_network_risk()
            self.extract_feature_6_privilege_level()
            self.extract_feature_7_connectivity()
            self.extract_feature_8_rule_violations()
            self.extract_feature_9_lockout_count()
            self.extract_feature_10_admin_actions()
            self.extract_feature_11_sensitive_groups()

            # Export to CSV
            df = self.export_to_csv()

            # Validate
            self.validate_features()

            print("\n" + "="*70)
            print("PHASE 4 COMPLETE")
            print("="*70)
            print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"\nFeatures CSV: data/phase4_graph_features.csv")
            print(f"Total users with features: {len(df):,}")
            print("\nNext steps:")
            print("  1. Run Phase 5: Isolation Forest Anomaly Detection")
            print("  2. Train multi-method anomaly detection models")
            print("  3. Generate anomaly scores and severity classifications")

            return df

        except Exception as e:
            print(f"\n[ERROR] Feature extraction failed: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    # Configuration
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "lalarasa"

    # Run extraction
    extractor = FeatureExtractor(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    try:
        df = extractor.run_extraction()
    finally:
        extractor.close()
