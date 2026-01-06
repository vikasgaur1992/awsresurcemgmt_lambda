import boto3
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
SNS_TOPIC_ARN = 'arn:aws:sns:us-east-1:accountid:NewResourceNotification' 
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

# --- B. RDS CLUSTER LOGIC (Aurora / Multi-AZ Clusters) ---
        try:
            clusters = rds_cli.describe_db_clusters()['DBClusters']
            for cluster in clusters:
                cid = cluster['DBClusterIdentifier']
                status = cluster['Status']
                
                # Tag check
                tags_resp = rds_cli.list_tags_for_resource(ResourceName=cluster['DBClusterArn'])
                tags = {t['Key']: t['Value'] for t in tags_resp.get('TagList', [])}
                if tags.get(EXCLUDE_TAG_KEY) == EXCLUDE_TAG_VALUE: continue

                if status == 'available':
                    try:
                        rds_cli.stop_db_cluster(DBClusterIdentifier=cid)
                        # THIS LINE ADDS IT TO YOUR EMAIL
                        report_data.append(f"RDS Cluster [Stopped]: {cid} ({region})")
                    except Exception as rds_e:
                        err_msg = str(rds_e).split(':')[-1].strip()
                        report_data.append(f"RDS Cluster [Error]: {cid} ({region}) - {err_msg}")
                elif status == 'stopping':
                    report_data.append(f"RDS Cluster [Already Stopping]: {cid} ({region})")

        except Exception as e: print(f"RDS Cluster Loop Error {region}: {e}")

        # --- C. STANDALONE RDS LOGIC (Non-Aurora Instances) ---
        try:
            instances = rds_cli.describe_db_instances()['DBInstances']
            for db in instances:
                did = db['DBInstanceIdentifier']
                status = db['DBInstanceStatus']
                
                # Skip if managed by a cluster (handled above)
                if 'DBClusterIdentifier' in db: continue
                
                # Tag check
                tags_resp = rds_cli.list_tags_for_resource(ResourceName=db['DBInstanceArn'])
                tags = {t['Key']: t['Value'] for t in tags_resp.get('TagList', [])}
                if tags.get(EXCLUDE_TAG_KEY) == EXCLUDE_TAG_VALUE: continue

                if status == 'available':
                    try:
                        rds_cli.stop_db_instance(DBInstanceIdentifier=did)
                        # THIS LINE ADDS IT TO YOUR EMAIL
                        report_data.append(f"RDS Instance [Stopped]: {did} ({region})")
                    except Exception as rds_e:
                        err_msg = str(rds_e).split(':')[-1].strip()
                        report_data.append(f"RDS Instance [Error]: {did} ({region}) - {err_msg}")
                elif status == 'stopping':
                    report_data.append(f"RDS Instance [Already Stopping]: {did} ({region})")

        except Exception as e: print(f"RDS Instance Loop Error {region}: {e}")
 
# --- 3. SEND REPORT ---
    if report_data:
        sns = boto3.client('sns')
        # This joins the report_data list (which now contains EC2 AND RDS) into the email body
        email_body = "Daily Resource Optimization Report:\n\n" + "-"*40 + "\n"
        email_body += "\n".join(report_data)
        email_body += f"\n\nTotal Resources Processed: {len(report_data)}"
        
        sns.publish(
            TopicArn=SNS_TOPIC_ARN, 
            Subject=f"AWS Optimization Report - {datetime.now().date()}", 
            Message=email_body
        )
        print("Success: Report sent to SNS.")
    else:
        print("Done: No active resources found to stop.")

    return {"status": "success", "items_processed": len(report_data)}
