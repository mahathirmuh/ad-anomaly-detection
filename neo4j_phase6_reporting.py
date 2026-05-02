#!/usr/bin/env python3
"""
Phase 6: Results & Comprehensive Reporting
Generate anomaly detection report with audit trail and evidence
"""

import pandas as pd
from neo4j import GraphDatabase
from datetime import datetime
import json
import os

class ReportGenerator:
    def __init__(self, uri, user, password):
        """Initialize Neo4j connection"""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        """Close connection"""
        self.driver.close()

    def load_anomaly_results(self):
        """Load anomaly detection results and SHAP explanations"""
        print("\n[Phase 6] Loading anomaly results...")

        self.results_df = pd.read_csv('data/phase5_anomaly_results.csv')
        self.results_df = self.results_df.drop_duplicates(subset='user_id')

        # Merge SHAP explanations if available
        shap_path = 'data/phase55_shap_values.csv'
        if os.path.exists(shap_path):
            shap_df = pd.read_csv(shap_path)[['user_id', 'top_feature_1', 'top_feature_1_label', 'top_feature_1_shap']]
            shap_df = shap_df.drop_duplicates(subset='user_id')
            self.results_df = self.results_df.merge(shap_df, on='user_id', how='left')
            print(f"  [OK] SHAP explanations merged")

        print(f"  [OK] Loaded {len(self.results_df):,} users")
        return self.results_df

    def get_user_evidence(self, user_id, username):
        """Get graph evidence for user"""
        with self.driver.session() as session:
            # Get rule violations
            rules_result = session.run(f"""
                MATCH (u:User {{{username}}})
                RETURN
                    u.rule_R001_violation as r001,
                    u.rule_R002_violation as r002,
                    u.rule_R003_violation as r003,
                    u.rule_R004_violation as r004,
                    u.rule_R005_violation as r005,
                    u.rule_R006_violation as r006,
                    u.rule_R007_violation as r007,
                    u.rule_R001_unique_hosts as r001_hosts,
                    u.rule_R002_off_hours_ratio as r002_ratio,
                    u.rule_R005_total_failures as r005_failures,
                    u.rule_R006_unusual_ips as r006_ips
            """, username=username).single()

            # Get relationships count
            rels_result = session.run(f"""
                MATCH (u:User {{{username}}})
                RETURN
                    COUNT {{ (u)-[:LOGIN_FROM]->() }} as logins,
                    COUNT {{ (u)-[:AUTHENTICATED_VIA]->() }} as authentications,
                    COUNT {{ (u)-[:FAILED_LOGIN]->() }} as failures,
                    COUNT {{ (u)-[:CONNECTED_FROM]->() }} as ips,
                    COUNT {{ (u)-[:MEMBER_OF]->() }} as groups
            """, username=username).single()

            return {
                'rules': rules_result,
                'relationships': rels_result
            }

    def generate_user_report(self, row):
        """Generate report for single user"""
        user_id = row['user_id']
        username = row['username']

        # Get evidence from graph
        evidence = self.get_user_evidence(user_id, f"user_id: '{user_id}'")

        # Build triggered rules
        triggered_rules = []
        rule_map = {
            'r001': ('R001', 'Normal Login Hosts', 'User logged in from unusual number of hosts'),
            'r002': ('R002', 'Business Hours Pattern', 'User has unusual off-hours login pattern'),
            'r003': ('R003', 'Shared Device Detection', 'User accesses shared devices'),
            'r004': ('R004', 'Uncommon Server Access', 'User accessed critical servers'),
            'r005': ('R005', 'Failed Login Spike', 'User has high failed login rate'),
            'r006': ('R006', 'Unusual IP Address', 'User connects from unusual IP addresses'),
            'r007': ('R007', 'After-Hours Privileged', 'Privileged user accessed critical resources off-hours'),
        }

        for key, (rid, name, desc) in rule_map.items():
            if evidence['rules'][key]:
                triggered_rules.append({
                    'rule_id': rid,
                    'rule_name': name,
                    'description': desc,
                    'triggered': True
                })

        # Build anomalous features
        anomalous_features = []
        feature_thresholds = {
            'host_diversity': (2.0, 'High host diversity (accessing many devices)'),
            'critical_server_ratio': (0.5, 'High critical server access ratio'),
            'failure_ratio': (0.2, 'High failed login ratio (possible brute force)'),
            'shared_device_risk': (5.0, 'High shared device risk'),
            'ip_network_risk': (0.7, 'High IP network risk (unusual locations)'),
            'privilege_level': (3, 'High privilege level (admin access)'),
            'rule_violations': (3, 'Multiple rule violations'),
        }

        for feature, (threshold, desc) in feature_thresholds.items():
            value = row[feature]
            if isinstance(threshold, float):
                if value > threshold:
                    anomalous_features.append({'feature': feature, 'value': value, 'description': desc})
            else:
                if value >= threshold:
                    anomalous_features.append({'feature': feature, 'value': int(value), 'description': desc})

        shap_explanation = {}
        if 'top_feature_1' in row and pd.notna(row.get('top_feature_1')):
            shap_explanation = {
                'top_feature': row['top_feature_1'],
                'top_feature_label': row.get('top_feature_1_label', ''),
                'top_feature_shap_value': float(row.get('top_feature_1_shap', 0)),
            }

        return {
            'user_id': user_id,
            'username': username,
            'anomaly_score': float(row['final_anomaly_score']),
            'severity': row['severity'],
            'triggered_rules': triggered_rules,
            'anomalous_features': anomalous_features,
            'shap_explanation': shap_explanation,
            'evidence': {
                'total_logins': int(evidence['relationships']['logins']) if evidence['relationships']['logins'] else 0,
                'failed_logins': int(evidence['relationships']['failures']) if evidence['relationships']['failures'] else 0,
                'unique_ips': int(evidence['relationships']['ips']) if evidence['relationships']['ips'] else 0,
                'unique_groups': int(evidence['relationships']['groups']) if evidence['relationships']['groups'] else 0,
            },
            'confidence_score': 0.85 + (0.15 * min(len(triggered_rules), 7) / 7)
        }

    def generate_text_report(self):
        """Generate human-readable text report"""
        print("\n[Phase 6] Generating text report...")

        report = []
        report.append("="*80)
        report.append("ACTIVE DIRECTORY ANOMALY DETECTION REPORT")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("="*80)

        report.append("\nEXECUTIVE SUMMARY")
        report.append("-"*80)

        total_users = len(self.results_df)
        anomalies = self.results_df[self.results_df['is_anomaly'] == 1]
        critical = self.results_df[self.results_df['severity'] == 'CRITICAL']
        high = self.results_df[self.results_df['severity'] == 'HIGH']

        report.append(f"\nTotal Users Analyzed:        {total_users:,}")
        report.append(f"Anomalous Users:             {len(anomalies):,} ({len(anomalies)/total_users*100:.1f}%)")
        report.append(f"  - CRITICAL severity:       {len(critical):,}")
        report.append(f"  - HIGH severity:           {len(high):,}")

        report.append("\n\nDETECTION METHODOLOGY")
        report.append("-"*80)
        report.append("Three independent anomaly detection methods were used:")
        report.append("1. Isolation Forest (IF) - Isolates anomalies via random partitioning")
        report.append("2. Local Outlier Factor (LOF) - Detects density-based anomalies")
        report.append("3. Elliptic Envelope (EE) - Identifies outliers via robust covariance")
        report.append("\nFinal anomaly score combines:")
        report.append("  - Ensemble voting (60% weight): How many methods flagged the user?")
        report.append("  - Rule violations (40% weight): How many domain rules were violated?")
        report.append("\nUser is flagged anomalous if:")
        report.append("  - 2+ methods agree it's anomalous, OR")
        report.append("  - Final score > 0.75 (on 0-1 scale)")

        report.append("\n\nTOP 10 HIGHEST ANOMALY SCORE USERS")
        report.append("-"*80)

        top_users = self.results_df[self.results_df['is_anomaly'] == 1].nlargest(10, 'final_anomaly_score')
        for idx, (_, row) in enumerate(top_users.iterrows(), 1):
            shap_label = row.get('top_feature_1_label', '-') if pd.notna(row.get('top_feature_1_label')) else '-'
            report.append(f"\n{idx}. {row['user_id']} ({row['username']})")
            report.append(f"   Anomaly Score:   {row['final_anomaly_score']:.4f}")
            report.append(f"   Severity:        {row['severity']}")
            report.append(f"   Rule Violations: {int(row['rule_violations'])}/7")
            report.append(f"   Ensemble Votes:  {int(row['anomaly_votes'])}/3")
            report.append(f"   Top SHAP Cause:  {shap_label}")

        report.append("\n\nKEY FINDINGS")
        report.append("-"*80)

        high_failure_users = self.results_df[self.results_df['failure_ratio'] > 0.2]
        unusual_ip_users = self.results_df[self.results_df['ip_network_risk'] > 0.7]
        shared_device_users = self.results_df[self.results_df['shared_device_risk'] > 5.0]

        report.append(f"\nBrute Force Risk (failure_ratio > 20%):")
        report.append(f"  - {len(high_failure_users):,} users affected")
        if len(high_failure_users) > 0:
            top_fail = high_failure_users.nlargest(3, 'failure_ratio')
            for _, row in top_fail.iterrows():
                report.append(f"    • {row['user_id']}: {row['failure_ratio']*100:.1f}% failure rate")

        report.append(f"\nUnusual IP Access:")
        report.append(f"  - {len(unusual_ip_users):,} users with non-office IP access")

        report.append(f"\nShared Device Risk:")
        report.append(f"  - {len(shared_device_users):,} users accessing shared devices")

        report.append("\n\nRECOMMENDATIONS")
        report.append("-"*80)
        report.append("\n1. IMMEDIATE ACTION (CRITICAL Users)")
        report.append("   - Reset passwords for users with high failure rates")
        report.append("   - Review privileged access logs")
        report.append("   - Investigate unusual IP connections")

        report.append("\n2. SHORT-TERM (HIGH Severity Users)")
        report.append("   - Enable MFA for unusual access patterns")
        report.append("   - Monitor shared device usage")
        report.append("   - Review group memberships")

        report.append("\n3. LONG-TERM IMPROVEMENTS")
        report.append("   - Implement risk-based adaptive authentication")
        report.append("   - Strengthen network segmentation")
        report.append("   - Deploy behavioral analytics platform")

        report.append("\n\n" + "="*80)
        report.append("END OF REPORT")
        report.append("="*80)

        report_text = "\n".join(report)
        report_path = "output/anomaly_detection_report.txt"
        os.makedirs(os.path.dirname(report_path), exist_ok=True)

        with open(report_path, 'w') as f:
            f.write(report_text)

        print(f"  [OK] Text report saved to {report_path}")

        return report_text

    def generate_json_report(self):
        """Generate detailed JSON report with evidence"""
        print("\n[Phase 6] Generating JSON report...")

        anomalies = self.results_df[self.results_df['is_anomaly'] == 1].copy()

        json_data = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'total_users': len(self.results_df),
                'anomalies_detected': len(anomalies),
                'anomaly_rate': float(len(anomalies) / len(self.results_df))
            },
            'summary': {
                'critical': int((self.results_df['severity'] == 'CRITICAL').sum()),
                'high': int((self.results_df['severity'] == 'HIGH').sum()),
                'medium': int((self.results_df['severity'] == 'MEDIUM').sum()),
                'low': int((self.results_df['severity'] == 'LOW').sum()),
                'normal': int((self.results_df['severity'] == 'NORMAL').sum()),
            },
            'anomalies': []
        }

        # Add top 50 anomalies with full details
        top_anomalies = anomalies.nlargest(50, 'final_anomaly_score')
        for _, row in top_anomalies.iterrows():
            user_report = self.generate_user_report(row)
            json_data['anomalies'].append(user_report)

        json_path = "output/anomaly_detection_detailed.json"
        os.makedirs(os.path.dirname(json_path), exist_ok=True)

        with open(json_path, 'w') as f:
            json.dump(json_data, f, indent=2, default=str)

        print(f"  [OK] JSON report saved to {json_path} ({len(json_data['anomalies'])} anomalies)")

        return json_data

    def generate_summary_statistics(self):
        """Generate summary statistics"""
        print("\n[Phase 6] Generating summary statistics...")

        stats = {
            'total_users': len(self.results_df),
            'anomaly_distribution': self.results_df['severity'].value_counts().to_dict(),
            'anomaly_score_stats': {
                'mean': float(self.results_df['final_anomaly_score'].mean()),
                'median': float(self.results_df['final_anomaly_score'].median()),
                'std': float(self.results_df['final_anomaly_score'].std()),
                'min': float(self.results_df['final_anomaly_score'].min()),
                'max': float(self.results_df['final_anomaly_score'].max()),
            },
            'rule_violations_stats': {
                'mean': float(self.results_df['rule_violations'].mean()),
                'users_with_0': int((self.results_df['rule_violations'] == 0).sum()),
                'users_with_1_2': int(((self.results_df['rule_violations'] >= 1) & (self.results_df['rule_violations'] <= 2)).sum()),
                'users_with_3_plus': int((self.results_df['rule_violations'] >= 3).sum()),
            },
            'ensemble_voting': {
                '0_votes': int((self.results_df['anomaly_votes'] == 0).sum()),
                '1_vote': int((self.results_df['anomaly_votes'] == 1).sum()),
                '2_votes': int((self.results_df['anomaly_votes'] == 2).sum()),
                '3_votes': int((self.results_df['anomaly_votes'] == 3).sum()),
            }
        }

        stats_path = "output/anomaly_statistics.json"
        os.makedirs(os.path.dirname(stats_path), exist_ok=True)

        with open(stats_path, 'w') as f:
            json.dump(stats, f, indent=2)

        print(f"  [OK] Statistics saved to {stats_path}")

        return stats

    def print_summary(self):
        """Print summary to console"""
        print("\n" + "="*70)
        print("PHASE 6 SUMMARY")
        print("="*70)

        print(f"\nTotal Users: {len(self.results_df):,}")
        print(f"Anomalies: {(self.results_df['is_anomaly'] == 1).sum():,}")

        print("\nSeverity Distribution:")
        for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'NORMAL']:
            count = (self.results_df['severity'] == severity).sum()
            pct = count / len(self.results_df) * 100
            print(f"  {severity:<10}: {count:>4} ({pct:>5.1f}%)")

        print("\nOutput Files:")
        print("  - output/anomaly_detection_report.txt (human-readable)")
        print("  - output/anomaly_detection_detailed.json (detailed evidence)")
        print("  - output/anomaly_statistics.json (summary statistics)")

    def run_reporting(self):
        """Execute complete reporting"""
        print("\n" + "="*70)
        print("PHASE 6: RESULTS & COMPREHENSIVE REPORTING")
        print("="*70)
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            # Load results
            self.load_anomaly_results()

            # Generate reports
            self.generate_text_report()
            self.generate_json_report()
            self.generate_summary_statistics()

            # Print summary
            self.print_summary()

            print("\n" + "="*70)
            print("PHASE 6 COMPLETE - ALL PHASES DONE!")
            print("="*70)
            print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            print("\n[DONE] PIPELINE COMPLETE!")
            print("\nGenerated Files:")
            print("  1. data/phase4_graph_features.csv - 8 features per user")
            print("  2. data/phase5_anomaly_results.csv - All anomaly scores")
            print("  3. data/phase5_anomalies_summary.csv - Summary of anomalies")
            print("  4. output/anomaly_detection_report.txt - Human-readable report")
            print("  5. output/anomaly_detection_detailed.json - Detailed evidence")
            print("  6. output/anomaly_statistics.json - Summary statistics")
            print("  7. models/ - Trained ML models (IF, LOF, EE, Scaler)")

            print("\nNext: Review findings and implement recommendations")

        except Exception as e:
            print(f"\n[ERROR] Reporting failed: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    reporter = ReportGenerator("bolt://localhost:7687", "neo4j", "lalarasa")
    try:
        reporter.run_reporting()
    finally:
        reporter.close()
