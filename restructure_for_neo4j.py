#!/usr/bin/env python3
"""
Restructure cleaned data into unified schema for Neo4j ingestion
Creates:
1. unified_logon_events.csv - All logon activity (DC + Member + Failures)
2. privileged_actions.csv - Admin, group, GPO changes
3. account_lockouts.csv - Lockout events
"""

import pandas as pd
import os
from datetime import datetime

CLEAN_DATA_DIR = "data/clean_data"
RESTRUCTURED_DIR = "data/restructured_data"

os.makedirs(RESTRUCTURED_DIR, exist_ok=True)

def restructure_logon_events():
    """Combine all logon events into unified table"""
    print("\n" + "-"*60)
    print("Restructuring: Unified Logon Events")
    print("-"*60)

    events = []

    # 1. DC Logon Activity (successful logons)
    print("  Processing DC Logon Activity...")
    dc_df = pd.read_csv(os.path.join(CLEAN_DATA_DIR, "clean_dc_logon.csv"))
    dc_df['event_source'] = 'dc_logon'
    dc_df['success'] = dc_df['event_type'].str.lower() == 'success'

    for _, row in dc_df.iterrows():
        events.append({
            'event_source': 'dc_logon',
            'username': row['username'],
            'hostname': row['hostname'],
            'ip_address': row['ip_address'],
            'dc_name': row['dc_name'],
            'server_name': None,
            'timestamp': row['logon_time'],
            'success': row['event_type'].lower() == 'success',
            'event_type': row['event_type'],
            'failure_reason': row['failure_reason'] if pd.notna(row['failure_reason']) else None,
            'domain': row['domain'],
            'logon_service': row['logon_service']
        })
    print(f"    Added {len(dc_df):,} DC logon events")

    # 2. Member Server Logon Activity (successful logons)
    print("  Processing Member Server Logon Activity...")
    member_df = pd.read_csv(os.path.join(CLEAN_DATA_DIR, "clean_member_logon.csv"))

    for _, row in member_df.iterrows():
        events.append({
            'event_source': 'member_logon',
            'username': row['username'],
            'hostname': row['hostname'],
            'ip_address': row['ip_address'],
            'dc_name': row['server_name'],  # member server acts as auth server
            'server_name': row['server_name'],
            'timestamp': row['logon_time'],
            'success': row['event_type'].lower() == 'success',
            'event_type': row['event_type'],
            'failure_reason': None,
            'domain': None,
            'logon_service': None
        })
    print(f"    Added {len(member_df):,} member server logon events")

    # 3. Logon Failures (failed logons)
    print("  Processing Logon Failures...")
    failure_df = pd.read_csv(os.path.join(CLEAN_DATA_DIR, "clean_logon_failures.csv"))

    for _, row in failure_df.iterrows():
        events.append({
            'event_source': 'logon_failure',
            'username': row['username'],
            'hostname': row['hostname'],
            'ip_address': row['ip_address'],
            'dc_name': row['dc_name'],
            'server_name': None,
            'timestamp': row['failure_time'],
            'success': False,
            'event_type': 'failure',
            'failure_reason': row['failure_reason'],
            'domain': row['domain'],
            'logon_service': row['logon_service']
        })
    print(f"    Added {len(failure_df):,} logon failure events")

    # Create unified DataFrame
    unified_df = pd.DataFrame(events)
    unified_df = unified_df.sort_values('timestamp').reset_index(drop=True)

    output_path = os.path.join(RESTRUCTURED_DIR, "unified_logon_events.csv")
    unified_df.to_csv(output_path, index=False)

    print(f"\n[OK] Saved: {output_path}")
    print(f"    Total events: {len(unified_df):,}")
    print(f"    DC logons: {len(dc_df):,}")
    print(f"    Member logons: {len(member_df):,}")
    print(f"    Failures: {len(failure_df):,}")
    print(f"    Date range: {unified_df['timestamp'].min()} to {unified_df['timestamp'].max()}")

    return unified_df

def restructure_privileged_actions():
    """Combine admin actions, group changes, GPO changes"""
    print("\n" + "-"*60)
    print("Restructuring: Privileged Actions")
    print("-"*60)

    actions = []

    # 1. Admin Actions
    print("  Processing Admin Actions...")
    if os.path.exists(os.path.join(CLEAN_DATA_DIR, "clean_admin_actions.csv")):
        admin_df = pd.read_csv(os.path.join(CLEAN_DATA_DIR, "clean_admin_actions.csv"))

        for _, row in admin_df.iterrows():
            actions.append({
                'action_type': 'admin_action',
                'actor_username': row['caller_username'],
                'target_username': row['username'],
                'target_name': row['username'],
                'target_type': 'user',
                'timestamp': row['action_time'],
                'dc_name': row['dc_name'],
                'domain': row['domain'],
                'event_type': row['event_type'],
                'description': row['description'],
                'group_name': None,
                'gpo_name': None
            })
        print(f"    Added {len(admin_df):,} admin action events")

    # 2. Group Member Changes
    print("  Processing Group Member Changes...")
    if os.path.exists(os.path.join(CLEAN_DATA_DIR, "clean_group_members.csv")):
        group_df = pd.read_csv(os.path.join(CLEAN_DATA_DIR, "clean_group_members.csv"))

        for _, row in group_df.iterrows():
            actions.append({
                'action_type': 'group_change',
                'actor_username': row['changed_by'],
                'target_username': None if row['member_type'] != 'User' else row['member_name'],
                'target_name': row['member_name'],
                'target_type': row['member_type'],
                'timestamp': row['change_time'],
                'dc_name': None,
                'domain': None,
                'event_type': row['member_type'],
                'description': f"Added {row['member_type']} to group",
                'group_name': row['group_name'],
                'gpo_name': None
            })
        print(f"    Added {len(group_df):,} group member change events")

    # 3. GPO Changes
    print("  Processing GPO Changes...")
    if os.path.exists(os.path.join(CLEAN_DATA_DIR, "clean_gpos.csv")):
        gpo_df = pd.read_csv(os.path.join(CLEAN_DATA_DIR, "clean_gpos.csv"))

        for _, row in gpo_df.iterrows():
            actions.append({
                'action_type': 'gpo_change',
                'actor_username': row['changed_by'],
                'target_username': None,
                'target_name': row['gpo_name'],
                'target_type': 'GPO',
                'timestamp': row['change_time'],
                'dc_name': row['dc_name'],
                'domain': row['domain'],
                'event_type': row['event_type'],
                'description': row['message'],
                'group_name': None,
                'gpo_name': row['gpo_name']
            })
        print(f"    Added {len(gpo_df):,} GPO change events")

    if not actions:
        print("  No privileged actions found")
        return None

    # Create DataFrame
    actions_df = pd.DataFrame(actions)
    actions_df = actions_df.sort_values('timestamp').reset_index(drop=True)

    output_path = os.path.join(RESTRUCTURED_DIR, "privileged_actions.csv")
    actions_df.to_csv(output_path, index=False)

    print(f"\n[OK] Saved: {output_path}")
    print(f"    Total actions: {len(actions_df):,}")
    print(f"    Admin actions: {len(admin_df) if 'admin_df' in locals() else 0:,}")
    print(f"    Group changes: {len(group_df) if 'group_df' in locals() else 0:,}")
    print(f"    GPO changes: {len(gpo_df) if 'gpo_df' in locals() else 0:,}")

    return actions_df

def restructure_lockouts():
    """Separate lockout events"""
    print("\n" + "-"*60)
    print("Restructuring: Account Lockouts")
    print("-"*60)

    if not os.path.exists(os.path.join(CLEAN_DATA_DIR, "clean_locked_users.csv")):
        print("  Lockout file not found")
        return None

    lockout_df = pd.read_csv(os.path.join(CLEAN_DATA_DIR, "clean_locked_users.csv"))

    # Drop redundant column
    if 'lockout_time_original' in lockout_df.columns:
        lockout_df = lockout_df.drop('lockout_time_original', axis=1)

    # Rename for consistency
    lockout_df = lockout_df.rename(columns={'lockout_time': 'timestamp'})

    output_path = os.path.join(RESTRUCTURED_DIR, "account_lockouts.csv")
    lockout_df.to_csv(output_path, index=False)

    print(f"  Processed lockout events")
    print(f"[OK] Saved: {output_path}")
    print(f"    Total lockouts: {len(lockout_df):,}")

    return lockout_df

def generate_improved_features(logon_df):
    """Generate behavioral features from ALL logon sources"""
    print("\n" + "-"*60)
    print("Generating Improved Behavioral Features")
    print("-"*60)

    logon_df['timestamp'] = pd.to_datetime(logon_df['timestamp'])

    features = []

    for username in logon_df['username'].unique():
        user_logons = logon_df[logon_df['username'] == username]

        successful = user_logons[user_logons['success'] == True]
        failed = user_logons[user_logons['success'] == False]

        features.append({
            'username': username,
            'total_logons': len(user_logons),
            'successful_logons': len(successful),
            'failed_logons': len(failed),
            'failure_ratio': len(failed) / len(user_logons) if len(user_logons) > 0 else 0,
            'unique_logon_times': user_logons['timestamp'].nunique(),
            'unique_hostnames': user_logons['hostname'].nunique(),
            'unique_ips': user_logons['ip_address'].nunique(),
            'unique_dcs': user_logons['dc_name'].nunique(),
            'avg_hour': user_logons['timestamp'].dt.hour.mean() if len(user_logons) > 0 else 0,
            'std_hour': user_logons['timestamp'].dt.hour.std() if len(user_logons) > 1 else 0,
            'min_hour': user_logons['timestamp'].dt.hour.min() if len(user_logons) > 0 else 0,
            'max_hour': user_logons['timestamp'].dt.hour.max() if len(user_logons) > 0 else 0,
            'first_logon': user_logons['timestamp'].min(),
            'last_logon': user_logons['timestamp'].max(),
            'logon_sources': ','.join(user_logons['event_source'].unique()),
        })

    features_df = pd.DataFrame(features)

    output_path = os.path.join(RESTRUCTURED_DIR, "improved_behavioral_features.csv")
    features_df.to_csv(output_path, index=False)

    print(f"[OK] Saved: {output_path}")
    print(f"    Total users: {len(features_df):,}")
    print(f"    Features per user: {len(features_df.columns)}")

    return features_df

def main():
    """Run complete restructuring"""
    print("\n" + "="*60)
    print("RESTRUCTURING FOR NEO4J INGESTION")
    print("="*60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Restructure main datasets
    logon_df = restructure_logon_events()
    actions_df = restructure_privileged_actions()
    lockout_df = restructure_lockouts()

    # Generate improved features
    if logon_df is not None:
        features_df = generate_improved_features(logon_df)

    print("\n" + "="*60)
    print("RESTRUCTURING COMPLETE")
    print("="*60)
    print(f"\nRestructured data saved to: {RESTRUCTURED_DIR}/")
    print("\nFiles created:")
    print("  1. unified_logon_events.csv - All logon activity")
    print("  2. privileged_actions.csv - Admin/Group/GPO changes")
    print("  3. account_lockouts.csv - Lockout events")
    print("  4. improved_behavioral_features.csv - Enhanced user features")
    print("\nReady for Neo4j ingestion!")

if __name__ == "__main__":
    main()
