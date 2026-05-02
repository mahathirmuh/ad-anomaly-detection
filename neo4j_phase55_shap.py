#!/usr/bin/env python3
"""
Phase 5.5: SHAP Explainability
Explain anomaly scores using SHAP TreeExplainer on Isolation Forest model
"""

import pandas as pd
import numpy as np
import shap
import joblib
import os
from datetime import datetime
from neo4j import GraphDatabase


FEATURE_COLS = [
    'host_diversity', 'critical_server_ratio', 'failure_ratio',
    'shared_device_risk', 'ip_network_risk', 'privilege_level',
    'connectivity', 'rule_violations',
    'lockout_count', 'admin_actions', 'sensitive_groups'
]

FEATURE_LABELS = {
    'host_diversity':         'Login dari banyak host',
    'critical_server_ratio':  'Akses critical server',
    'failure_ratio':          'Rasio login gagal',
    'shared_device_risk':     'Risiko shared device',
    'ip_network_risk':        'Risiko IP tidak dikenal',
    'privilege_level':        'Level privilege tinggi',
    'connectivity':           'Graph connectivity tinggi',
    'rule_violations':        'Pelanggaran rule',
    'lockout_count':          'Sering lockout',
    'admin_actions':          'Banyak admin action',
    'sensitive_groups':       'Anggota grup sensitif',
}


class SHAPExplainer:
    def __init__(self, neo4j_uri, neo4j_user, neo4j_password):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.df = None
        self.df_results = None
        self.X_scaled = None
        self.shap_values = None

    def close(self):
        self.driver.close()

    def load_data(self):
        """Load features and phase 5 results"""
        print("\n[Phase 5.5] Loading data...")

        self.df = pd.read_csv('data/phase4_graph_features.csv')
        df5 = pd.read_csv('data/phase5_anomaly_results.csv')

        # Normalise column names from phase 5
        df5 = df5.rename(columns={
            'final_anomaly_score': 'anomaly_score',
            'anomaly_votes':       'ensemble_votes',
        })

        # Keep one row per user (highest anomaly score)
        df5 = df5.sort_values('anomaly_score', ascending=False).drop_duplicates(subset='user_id')

        merge_cols = [c for c in ['user_id', 'username', 'anomaly_score', 'severity', 'ensemble_votes'] if c in df5.columns]
        self.df = self.df.merge(df5[merge_cols], on='user_id', how='left', suffixes=('', '_r'))

        if 'username_r' in self.df.columns:
            self.df.drop(columns=['username_r'], inplace=True)

        print(f"  [OK] Loaded {len(self.df):,} users")
        return self.df

    def load_models(self):
        """Load saved scaler and IF model"""
        print("\n[Phase 5.5] Loading models...")

        self.scaler = joblib.load('models/feature_scaler.pkl')
        self.if_model = joblib.load('models/isolation_forest_model.pkl')

        X = self.df[FEATURE_COLS].fillna(0).replace([np.inf, -np.inf], 0)
        self.X_scaled = self.scaler.transform(X)

        print(f"  [OK] Models loaded, feature matrix: {self.X_scaled.shape}")

    def compute_shap_values(self):
        """Compute SHAP values using TreeExplainer on Isolation Forest"""
        print("\n[Phase 5.5] Computing SHAP values...")

        explainer = shap.TreeExplainer(self.if_model)
        self.shap_values = explainer.shap_values(self.X_scaled)

        print(f"  [OK] SHAP values computed: shape {self.shap_values.shape}")
        return self.shap_values

    def build_shap_dataframe(self):
        """Build per-user SHAP dataframe with top contributing features"""
        print("\n[Phase 5.5] Building SHAP dataframe...")

        shap_df = pd.DataFrame(self.shap_values, columns=[f'shap_{c}' for c in FEATURE_COLS])

        # Absolute contribution per feature
        abs_shap = np.abs(self.shap_values)

        # Top 3 features per user (by absolute SHAP value)
        top_indices = np.argsort(abs_shap, axis=1)[:, ::-1][:, :3]
        top1 = [FEATURE_COLS[i] for i in top_indices[:, 0]]
        top2 = [FEATURE_COLS[i] for i in top_indices[:, 1]]
        top3 = [FEATURE_COLS[i] for i in top_indices[:, 2]]
        top1_val = [self.shap_values[row, top_indices[row, 0]] for row in range(len(self.df))]
        top1_label = [FEATURE_LABELS[f] for f in top1]

        shap_df['user_id']       = self.df['user_id'].values
        shap_df['username']      = self.df['username'].values
        shap_df['anomaly_score'] = self.df.get('anomaly_score', pd.Series([0]*len(self.df))).values
        shap_df['severity']      = self.df.get('severity', pd.Series(['NORMAL']*len(self.df))).values
        shap_df['ensemble_votes']= self.df.get('ensemble_votes', pd.Series([0]*len(self.df))).values
        shap_df['top_feature_1'] = top1
        shap_df['top_feature_2'] = top2
        shap_df['top_feature_3'] = top3
        shap_df['top_feature_1_shap'] = top1_val
        shap_df['top_feature_1_label'] = top1_label

        # Reorder columns
        front = ['user_id', 'username', 'anomaly_score', 'severity', 'ensemble_votes',
                 'top_feature_1', 'top_feature_1_label', 'top_feature_1_shap',
                 'top_feature_2', 'top_feature_3']
        shap_cols = [f'shap_{c}' for c in FEATURE_COLS]
        shap_df = shap_df[front + shap_cols]

        self.shap_df = shap_df
        print(f"  [OK] SHAP dataframe built: {len(shap_df):,} rows")
        return shap_df

    def export_to_csv(self):
        """Export SHAP values to CSV"""
        print("\n[Phase 5.5] Exporting to CSV...")

        os.makedirs('data', exist_ok=True)
        self.shap_df.to_csv('data/phase55_shap_values.csv', index=False)

        # Anomalies only
        anomalies = self.shap_df[self.shap_df['severity'].isin(['CRITICAL', 'HIGH', 'MEDIUM'])]
        anomalies.to_csv('data/phase55_shap_anomalies.csv', index=False)

        print(f"  [OK] Full SHAP: data/phase55_shap_values.csv ({len(self.shap_df):,} rows)")
        print(f"  [OK] Anomalies SHAP: data/phase55_shap_anomalies.csv ({len(anomalies):,} rows)")

    def write_to_neo4j(self):
        """Write top SHAP features back to Neo4j user nodes (batched)"""
        print("\n[Phase 5.5] Writing SHAP results to Neo4j...")

        records = self.shap_df[['user_id', 'top_feature_1', 'top_feature_1_label',
                                 'top_feature_1_shap', 'top_feature_2', 'top_feature_3']].to_dict('records')

        batch_size = 200
        total_updated = 0
        with self.driver.session() as session:
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                result = session.run("""
                    UNWIND $records AS row
                    MATCH (u:User {user_id: row.user_id})
                    SET u.shap_top_feature = row.top_feature_1,
                        u.shap_top_feature_label = row.top_feature_1_label,
                        u.shap_top_feature_value = row.top_feature_1_shap,
                        u.shap_top_feature_2 = row.top_feature_2,
                        u.shap_top_feature_3 = row.top_feature_3
                    RETURN count(u) as updated
                """, records=batch)
                total_updated += result.single()['updated']

        print(f"  [OK] Updated {total_updated:,} users in Neo4j with SHAP data")

    def print_summary(self):
        """Print SHAP global feature importance summary"""
        print("\n[Phase 5.5] Global Feature Importance (mean |SHAP|):")

        mean_abs = np.abs(self.shap_values).mean(axis=0)
        importance = sorted(zip(FEATURE_COLS, mean_abs), key=lambda x: x[1], reverse=True)

        for rank, (feat, val) in enumerate(importance, 1):
            bar = '#' * int(val * 200)
            label = FEATURE_LABELS[feat]
            print(f"  {rank}. {feat:<28} {val:.6f}  {bar}  [{label}]")

        print("\n[Phase 5.5] Top Anomalous Users with SHAP Explanation:")
        top_anomalies = self.shap_df[
            self.shap_df['severity'].isin(['CRITICAL', 'HIGH', 'MEDIUM'])
        ].sort_values('anomaly_score', ascending=False).head(10)

        for _, row in top_anomalies.iterrows():
            print(f"  {row['username']:<35} Score:{row['anomaly_score']:.4f}  "
                  f"Top cause: {row['top_feature_1_label']}")

    def run(self):
        print("\n" + "="*70)
        print("PHASE 5.5: SHAP EXPLAINABILITY")
        print("="*70)
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            self.load_data()
            self.load_models()
            self.compute_shap_values()
            self.build_shap_dataframe()
            self.export_to_csv()
            self.write_to_neo4j()
            self.print_summary()

            print("\n" + "="*70)
            print("PHASE 5.5 COMPLETE")
            print("="*70)
            print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("\nNext steps:")
            print("  1. Run Phase 6: Generate comprehensive anomaly report")
            print("  2. Report will include SHAP explanations per anomalous user")

        except Exception as e:
            print(f"\n[ERROR] SHAP explainability failed: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    NEO4J_URI      = "bolt://localhost:7687"
    NEO4J_USER     = "neo4j"
    NEO4J_PASSWORD = "lalarasa"

    explainer = SHAPExplainer(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    try:
        explainer.run()
    finally:
        explainer.close()
