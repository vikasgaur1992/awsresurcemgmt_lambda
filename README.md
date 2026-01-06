AWS Multi-Region Resource Optimizer
An automated, serverless solution to reduce AWS costs by identifying and stopping idle resources across all regions. This project targets EC2 instances, ECS services, and RDS instances/clusters that show low activity.

🚀 Key Features
Multi-Region Scanning: Automatically iterates through all active AWS regions.

Intelligent Thresholds: * EC2: Stops instances with Max CPU utilization below 5% over the last 10 days.
ECS: Scales services to desired_count = 0 regardless of metrics (unless tagged).
RDS: Stops standalone DB instances with 0 active connections.
Safety Tags: Exclude specific resources from being stopped by adding the tag stop:exclude.
Reporting: Sends a consolidated summary report via Amazon SNS after every execution.

🛠️ Architecture
Amazon EventBridge: Triggers the Lambda function on a daily schedule.
AWS Lambda (Python): Contains the logic to scan regions, check CloudWatch metrics, and stop resources.
Amazon SNS: Dispatches an email notification with the details of all actions taken.
IAM Role: Granted the "Least Privilege" permissions required to describe and stop specific resources.

📋 Setup Instructions
1. SNS Topic Setup
Create an SNS Topic named NewResourceNotification.
Subscribe your email address to the topic and confirm the subscription.
Note the ARN; you will need to paste it into the Lambda code.

2. IAM Configuration
Role Name: EC2-ECS-Cleanup-Role
Trust Policy: Allow both Lambda and the EventBridge Scheduler to assume the role.
Permissions Policy: Attach a custom policy with the permissions provided in this repo to allow the Lambda to describe CloudWatch metrics and stop EC2/RDS/ECS resources.

3. Lambda Deployment
Create a new Lambda function from scratch (Runtime: Python 3.x).
Assign the EC2-ECS-Cleanup-Role created above.
Adjust the Timeout to at least 5 minutes (multi-region scans take time).
Update the SNS_TOPIC_ARN variable in the code with your actual Topic ARN.

4. EventBridge Scheduler
Go to Amazon EventBridge > Scheduler.
Create a new schedule (e.g., cron(0 1 * * ? *) to run at 1:00 AM daily).
Target: AWS Lambda (Invoke).
Select your stop_terminate_aws_resource function.

⚙️ Configuration Variables
You can customize the logic by editing these variables at the top of the script:
CPU_THRESHOLD: The CPU percentage below which an EC2 is considered idle.
DAYS_LOOKBACK: The timeframe CloudWatch looks at to determine idleness.
EXCLUDE_TAG_KEY / VALUE: The tag pair used to "whitelist" a resource from being stopped.

⚠️ Disclaimer
This tool stops resources. Ensure that your critical production workloads are properly tagged with stop:exclude to prevent accidental downtime.

