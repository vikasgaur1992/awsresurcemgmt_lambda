import boto3
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
SNS_TOPIC_ARN = 'arn:aws:sns:us-east-1:474727059017:NewResourceNotification' 
CPU_THRESHOLD = 5.0      
DAYS_LOOKBACK = 10       
EXCLUDE_TAG_KEY = 'stop' 
EXCLUDE_TAG_VALUE = 'exclude'

def lambda_handler(event, context):
    ec2_client = boto3.client('ec2')
    regions = [r['RegionName'] for r in ec2_client.describe_regions()['Regions']]
    report_data = [] 

    for region in regions:
        print(f"--- Processing Region: {region} ---")
        ec2_res = boto3.resource('ec2', region_name=region)
        cw_cli = boto3.client('cloudwatch', region_name=region)
        ecs_cli = boto3.client('ecs', region_name=region)
        rds_cli = boto3.client('rds', region_name=region)

        # --- A. ECS SERVICE LOGIC ---
        try:
            clusters = ecs_cli.list_clusters()['clusterArns']
            for cluster in clusters:
                services = ecs_cli.list_services(cluster=cluster, maxResults=100)['serviceArns']
                for svc_arn in services:
                    tags_resp = ecs_cli.list_tags_for_resource(resourceArn=svc_arn)
                    tags = {t['key']: t['value'] for t in tags_resp.get('tags', [])}
                    if tags.get(EXCLUDE_TAG_KEY) == EXCLUDE_TAG_VALUE: continue
                    ecs_cli.update_service(cluster=cluster, service=svc_arn, desiredCount=0)
                    report_data.append(f"ECS [Scaled 0]: {svc_arn.split('/')[-1]} ({region})")
        except Exception as e: print(f"ECS Error {region}: {e}")

        # --- B. EC2 INSTANCE LOGIC ---
        try:
            for inst in ec2_res.instances.filter(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]):
                tags = {t['Key']: t['Value'] for t in inst.tags} if inst.tags else {}
                if tags.get(EXCLUDE_TAG_KEY) == EXCLUDE_TAG_VALUE: continue
                stats = cw_cli.get_metric_statistics(
                    Namespace='AWS/EC2', MetricName='CPUUtilization',
                    Dimensions=[{'Name': 'InstanceId', 'Value': inst.id}],
                    StartTime=datetime.utcnow() - timedelta(days=DAYS_LOOKBACK),
                    EndTime=datetime.utcnow(), Period=86400, Statistics=['Maximum']
                )
                max_cpu = max([d['Maximum'] for d in stats.get('Datapoints', [])]) if stats.get('Datapoints') else 0
                if not stats.get('Datapoints') or max_cpu < CPU_THRESHOLD:
                    inst.stop()
                    report_data.append(f"EC2 [Stopped]: {inst.id} ({region}) - CPU: {round(max_cpu, 1)}%")
        except Exception as e: print(f"EC2 Error {region}: {e}")

        # --- C. RDS CLUSTER & INSTANCE LOGIC ---
        # Part 1: Clusters (Aurora / Multi-AZ Clusters)
        try:
            for cluster in rds_cli.describe_db_clusters()['DBClusters']:
                cid = cluster['DBClusterIdentifier']
                if cluster['Status'] != 'available': continue
                c_stats = cw_cli.get_metric_statistics(
                    Namespace='AWS/RDS', MetricName='DatabaseConnections',
                    Dimensions=[{'Name': 'DBClusterIdentifier', 'Value': cid}],
                    StartTime=datetime.utcnow() - timedelta(days=DAYS_LOOKBACK),
                    EndTime=datetime.utcnow(), Period=86400, Statistics=['Maximum']
                )
                if not c_stats.get('Datapoints') or sum([d['Maximum'] for d in c_stats['Datapoints']]) == 0:
                    report_data.append(f"RDS Cluster [IDLE]: {cid} ({region}) - Reason: Multi-AZ Clusters do not support Stop API.")
        except Exception as e: print(f"RDS Cluster Error {region}: {e}")

        # Part 2: Individual DB Instances
        try:
            for db in rds_cli.describe_db_instances()['DBInstances']:
                did = db['DBInstanceIdentifier']
                if 'DBClusterIdentifier' in db or db['DBInstanceStatus'] != 'available': continue

                i_stats = cw_cli.get_metric_statistics(
                    Namespace='AWS/RDS', MetricName='DatabaseConnections',
                    Dimensions=[{'Name': 'DBInstanceIdentifier', 'Value': did}],
                    StartTime=datetime.utcnow() - timedelta(days=DAYS_LOOKBACK),
                    EndTime=datetime.utcnow(), Period=86400, Statistics=['Maximum']
                )
                
                if not i_stats.get('Datapoints') or sum([d['Maximum'] for d in i_stats['Datapoints']]) == 0:
                    # Check for stopping blockers
                    is_multi_az = db.get('MultiAZ', False)
                    engine = db.get('Engine', '')
                    has_replicas = len(db.get('ReadReplicaDBInstanceIdentifiers', [])) > 0 or db.get('ReadReplicaSourceDBInstanceIdentifier')

                    if engine == 'sqlserver-se' or engine == 'sqlserver-ee' or engine == 'sqlserver-web':
                        if is_multi_az:
                            report_data.append(f"RDS [IDLE]: {did} ({region}) - Reason: SQL Server Multi-AZ (Mirroring) cannot be stopped.")
                            continue
                    
                    if has_replicas:
                        report_data.append(f"RDS [IDLE]: {did} ({region}) - Reason: Instance has active Read Replicas.")
                        continue

                    try:
                        rds_cli.stop_db_instance(DBInstanceIdentifier=did)
                        report_data.append(f"RDS [Stopped]: {did} ({region})")
                    except Exception as rds_e:
                        report_data.append(f"RDS [Error]: {did} ({region}) - {str(rds_e)}")
        except Exception as e: print(f"RDS Instance Error {region}: {e}")

    # --- 3. SEND REPORT ---
    if report_data:
        sns = boto3.client('sns')
        body = "Daily Resource Optimization Report:\n\n" + "\n".join(report_data)
        sns.publish(TopicArn=SNS_TOPIC_ARN, Subject=f"AWS Optimization Report - {datetime.now().date()}", Message=body)
        print("Report sent.")
    
    return {"status": "success", "items": len(report_data)}
