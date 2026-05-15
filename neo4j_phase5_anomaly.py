#!/usr/bin/env python3
"""
Phase 5: Multi-Method Anomaly Detection
Use ensemble of 3 methods + rule violations for robust anomaly detection
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.covariance import EllipticEnvelope
from sklearn.preprocessing import StandardScaler
from neo4j import GraphDatabase
import joblib
from datetime import datetime
import os

class MultiMethodAnomalyDetector:
    def __init__(self, neo4j_uri=None, neo4j_user=None, neo4j_password=None):
        """Initialize detector"""
        self.df = None
        self.scaler = StandardScaler()
        self.if_model = None
        self.lof_model = None
        self.ee_model = None
        self.X_scaled = None
        self.driver = None
        if neo4j_uri:
            self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    def close(self):
        if self.driver:
            self.driver.close()

    def load_features(self):
        """Load features from Phase 4"""
        print("\n[Phase 5] Loading features...")

        self.df = pd.read_csv('data/phase4_graph_features.csv')
        print(f"  [OK] Loaded {len(self.df):,} users with 8 features")
        return self.df

    def prepare_features(self):
        """Prepare features for ML models"""
        print("\n[Phase 5] Preparing features...")

        feature_cols = [
            'host_diversity', 'critical_server_ratio', 'failure_ratio',
            'shared_device_risk', 'ip_network_risk', 'privilege_level',
            'connectivity', 'rule_violations',
            'lockout_count', 'admin_actions', 'sensitive_groups'
        ]

        X = self.df[feature_cols].fillna(0)

        # Check for NaN or inf
        X = X.replace([np.inf, -np.inf], 0)

        # Normalize
        self.X_scaled = self.scaler.fit_transform(X)

        print(f"  [OK] Prepared {len(X):,} users x {len(feature_cols)} features")
        print(f"      Features: {feature_cols}")

        return self.X_scaled

    def train_isolation_forest(self):
        """Train Isolation Forest model"""
        print("\n[Phase 5] Training Isolation Forest...")

        self.if_model = IsolationForest(
            contamination=0.05,  # Expect 5% anomalies
            random_state=42,
            n_estimators=100,
            n_jobs=-1
        )

        self.if_model.fit(self.X_scaled)

        # Get scores
        if_scores = self.if_model.score_samples(self.X_scaled)
        if_predictions = self.if_model.predict(self.X_scaled)  # -1 = anomaly, 1 = normal

        self.df['if_score'] = if_scores
        self.df['if_anomaly'] = (if_predictions == -1).astype(int)

        anomaly_count = (if_predictions == -1).sum()
        print(f"  [OK] IF: Detected {anomaly_count:,} anomalies ({anomaly_count/len(self.df)*100:.2f}%)")

        return if_scores

    def train_local_outlier_factor(self):
        """Train Local Outlier Factor model"""
        print("\n[Phase 5] Training Local Outlier Factor...")

        self.lof_model = LocalOutlierFactor(
            n_neighbors=20,
            contamination=0.05
        )

        lof_predictions = self.lof_model.fit_predict(self.X_scaled)
        lof_scores = self.lof_model.negative_outlier_factor_  # Negative LOF score

        self.df['lof_score'] = lof_scores
        self.df['lof_anomaly'] = (lof_predictions == -1).astype(int)

        anomaly_count = (lof_predictions == -1).sum()
        print(f"  [OK] LOF: Detected {anomaly_count:,} anomalies ({anomaly_count/len(self.df)*100:.2f}%)")

        return lof_scores

    def train_elliptic_envelope(self):
        """Train Elliptic Envelope (robust covariance) model"""
        print("\n[Phase 5] Training Elliptic Envelope...")

        self.ee_model = EllipticEnvelope(
            contamination=0.05,
            random_state=42
        )

        ee_predictions = self.ee_model.fit_predict(self.X_scaled)
        ee_scores = self.ee_model.score_samples(self.X_scaled)

        self.df['ee_score'] = ee_scores
        self.df['ee_anomaly'] = (ee_predictions == -1).astype(int)

        anomaly_count = (ee_predictions == -1).sum()
        print(f"  [OK] EE: Detected {anomaly_count:,} anomalies ({anomaly_count/len(self.df)*100:.2f}%)")

        return ee_scores

    def ensemble_voting(self):
        """Create ensemble anomaly score"""
        print("\n[Phase 5] Creating ensemble anomaly score...")

        # Normalize individual scores to 0-1 range
        # IF: score_samples returns values in range [-1, +1], more negative = more anomalous
        if_norm = (self.df['if_score'] - self.df['if_score'].min()) / (self.df['if_score'].max() - self.df['if_score'].min())
        if_norm = 1 - if_norm  # Invert so higher = more anomalous

        # LOF: negative_outlier_factor is negative, more negative = more anomalous
        lof_norm = (self.df['lof_score'] - self.df['lof_score'].min()) / (self.df['lof_score'].max() - self.df['lof_score'].min())
        lof_norm = 1 - lof_norm  # Invert

        # EE: score_samples returns log-likelihood, lower = more anomalous
        ee_norm = (self.df['ee_score'] - self.df['ee_score'].min()) / (self.df['ee_score'].max() - self.df['ee_score'].min())
        ee_norm = 1 - ee_norm  # Invert

        # Weighted ensemble (equal weights for simplicity)
        self.df['ensemble_anomaly_score'] = (if_norm + lof_norm + ee_norm) / 3.0

        # Voting: count how many methods flagged as anomaly
        self.df['anomaly_votes'] = (
            self.df['if_anomaly'] +
            self.df['lof_anomaly'] +
            self.df['ee_anomaly']
        )

        # Rule violations contribution (0-10 scale, normalize to 0-1)
        self.df['rule_score'] = self.df['rule_violations'] / 10.0

        # Final anomaly score: combine ensemble + rules (0.6 ML + 0.4 rules)
        self.df['final_anomaly_score'] = (
            0.6 * self.df['ensemble_anomaly_score'] +
            0.4 * self.df['rule_score']
        )

        # Classify severity using quantile-based thresholds (data-driven)
        # Reference:
        #   - Aggarwal, C. C. (2017). Outlier Analysis. Springer.
        #   - Goldstein & Uchida (2016). A Comparative Evaluation of
        #     Unsupervised Anomaly Detection Algorithms. PLOS ONE.
        #   - Liu, Ting, Zhou (2008). Isolation Forest. IEEE ICDM.
        p75 = self.df['final_anomaly_score'].quantile(0.75)
        p90 = self.df['final_anomaly_score'].quantile(0.90)
        p95 = self.df['final_anomaly_score'].quantile(0.95)
        p99 = self.df['final_anomaly_score'].quantile(0.99)

        print(f"\n  Quantile-based severity thresholds:")
        print(f"    CRITICAL (>=P99): {p99:.4f}")
        print(f"    HIGH     (>=P95): {p95:.4f}")
        print(f"    MEDIUM   (>=P90): {p90:.4f}")
        print(f"    LOW      (>=P75): {p75:.4f}")

        self.df['severity'] = self.df['final_anomaly_score'].apply(lambda x:
            'CRITICAL' if x >= p99 else
            'HIGH'     if x >= p95 else
            'MEDIUM'   if x >= p90 else
            'LOW'      if x >= p75 else
            'NORMAL'
        )

        # Final anomaly flag: anomalous if ensemble voting >= 2 or score > 0.75
        self.df['is_anomaly'] = (
            (self.df['anomaly_votes'] >= 2) |
            (self.df['final_anomaly_score'] > 0.75)
        ).astype(int)

        print(f"  [OK] Ensemble voting complete")
        print(f"      Anomalies detected: {self.df['is_anomaly'].sum():,}")

    def analyze_results(self):
        """Analyze anomaly detection results"""
        print("\n[Phase 5] Analyzing results...")

        print("\n  Anomaly Score Distribution:")
        print(f"    Mean: {self.df['final_anomaly_score'].mean():.4f}")
        print(f"    Median: {self.df['final_anomaly_score'].median():.4f}")
        print(f"    Std Dev: {self.df['final_anomaly_score'].std():.4f}")
        print(f"    Min: {self.df['final_anomaly_score'].min():.4f}")
        print(f"    Max: {self.df['final_anomaly_score'].max():.4f}")

        print("\n  Severity Distribution:")
        for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'NORMAL']:
            count = (self.df['severity'] == severity).sum()
            pct = count / len(self.df) * 100
            print(f"    {severity:<10}: {count:>4} ({pct:>5.1f}%)")

        print("\n  Ensemble Voting Distribution:")
        for votes in range(4):
            count = (self.df['anomaly_votes'] == votes).sum()
            pct = count / len(self.df) * 100
            print(f"    {votes} votes: {count:>4} ({pct:>5.1f}%)")

        # Top anomalies
        print("\n  Top 10 Most Anomalous Users:")
        top_anomalies = self.df.nlargest(10, 'final_anomaly_score')[
            ['user_id', 'username', 'final_anomaly_score', 'severity', 'anomaly_votes', 'rule_violations']
        ]
        for idx, row in top_anomalies.iterrows():
            print(f"    {row['user_id']:<15} {row['username']:<30} "
                  f"Score: {row['final_anomaly_score']:.4f} Severity: {row['severity']:<10} "
                  f"Votes: {int(row['anomaly_votes'])} Rules: {int(row['rule_violations'])}")

    def save_results(self):
        """Save results to CSV"""
        print("\n[Phase 5] Saving results...")

        # Full results with all scores
        output_cols = [
            'user_id', 'username',
            'host_diversity', 'critical_server_ratio', 'failure_ratio',
            'shared_device_risk', 'ip_network_risk', 'privilege_level',
            'connectivity', 'rule_violations',
            'lockout_count', 'admin_actions', 'sensitive_groups',
            'if_score', 'lof_score', 'ee_score',
            'if_anomaly', 'lof_anomaly', 'ee_anomaly',
            'anomaly_votes', 'ensemble_anomaly_score', 'rule_score',
            'final_anomaly_score', 'severity', 'is_anomaly'
        ]

        output_path = "data/phase5_anomaly_results.csv"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        self.df[output_cols].to_csv(output_path, index=False)

        print(f"  [OK] Saved full results to {output_path}")

        # Summary results (anomalies only)
        anomalies = self.df[self.df['is_anomaly'] == 1]
        summary_path = "data/phase5_anomalies_summary.csv"
        anomalies[['user_id', 'username', 'final_anomaly_score', 'severity', 'rule_violations']].to_csv(
            summary_path, index=False
        )
        print(f"  [OK] Saved {len(anomalies):,} anomalies to {summary_path}")

        return self.df

    def write_to_neo4j(self):
        """Write anomaly scores back to Neo4j User nodes (batched)"""
        if not self.driver:
            print("\n[Phase 5] Skipping Neo4j write (no connection)")
            return

        print("\n[Phase 5] Writing results to Neo4j...")

        # Deduplicate by user_id (highest score wins)
        df_unique = self.df.sort_values('final_anomaly_score', ascending=False).drop_duplicates(subset='user_id')

        records = df_unique[[
            'user_id', 'final_anomaly_score', 'severity', 'anomaly_votes',
            'is_anomaly', 'if_score', 'lof_score', 'ee_score'
        ]].to_dict('records')

        # Convert numpy types to Python types for Neo4j compatibility
        for r in records:
            r['final_anomaly_score'] = float(r['final_anomaly_score'])
            r['anomaly_votes']       = int(r['anomaly_votes'])
            r['is_anomaly']          = int(r['is_anomaly'])
            r['if_score']            = float(r['if_score'])
            r['lof_score']           = float(r['lof_score'])
            r['ee_score']            = float(r['ee_score'])

        batch_size = 200
        total_updated = 0
        with self.driver.session() as session:
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                result = session.run("""
                    UNWIND $records AS row
                    MATCH (u:User {user_id: row.user_id})
                    SET u.anomaly_score    = row.final_anomaly_score,
                        u.severity         = row.severity,
                        u.anomaly_votes    = row.anomaly_votes,
                        u.is_anomaly       = row.is_anomaly,
                        u.if_score         = row.if_score,
                        u.lof_score        = row.lof_score,
                        u.ee_score         = row.ee_score
                    RETURN count(u) as updated
                """, records=batch)
                total_updated += result.single()['updated']

        print(f"  [OK] Updated {total_updated:,} users in Neo4j with anomaly scores")

    def save_models(self):
        """Save trained models"""
        print("\n[Phase 5] Saving models...")

        os.makedirs("models", exist_ok=True)

        joblib.dump(self.if_model, "models/isolation_forest_model.pkl")
        joblib.dump(self.lof_model, "models/lof_model.pkl")
        joblib.dump(self.ee_model, "models/elliptic_envelope_model.pkl")
        joblib.dump(self.scaler, "models/feature_scaler.pkl")

        print("  [OK] Saved all models to models/")

    def run_detection(self):
        """Run complete anomaly detection pipeline"""
        print("\n" + "="*70)
        print("PHASE 5: MULTI-METHOD ANOMALY DETECTION")
        print("="*70)
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            # Load and prepare
            self.load_features()
            self.prepare_features()

            # Train models
            self.train_isolation_forest()
            self.train_local_outlier_factor()
            self.train_elliptic_envelope()

            # Ensemble voting
            self.ensemble_voting()

            # Analyze
            self.analyze_results()

            # Save
            self.save_results()
            self.save_models()
            self.write_to_neo4j()

            print("\n" + "="*70)
            print("PHASE 5 COMPLETE")
            print("="*70)
            print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("\nResults:")
            print(f"  Results CSV: data/phase5_anomaly_results.csv")
            print(f"  Anomalies CSV: data/phase5_anomalies_summary.csv")
            print(f"  Models saved to: models/")
            print("\nNext step:")
            print("  Run Phase 6: Generate comprehensive anomaly report")

            return self.df

        except Exception as e:
            print(f"\n[ERROR] Anomaly detection failed: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    NEO4J_URI      = "bolt://localhost:7687"
    NEO4J_USER     = "neo4j"
    NEO4J_PASSWORD = "lalarasa"

    detector = MultiMethodAnomalyDetector(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    try:
        df = detector.run_detection()
    finally:
        detector.close()
