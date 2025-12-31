# awsresurcemgmt_lambda
++++++++++++++++++++++++++
Create IAM role - EC2-ECS-Cleanup-Role
Attach Policy - cost_optimization_lambda
Add IAM Permissions - cost_optimization_lambda
Create labmda function with the code.
Use event bridg to trigger lambda
Add scheduler.amazonaws.com to IAM role trust policy

+++++++++++++++++++++
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ec2:Describe*",
                "ec2:StopInstances",
                "cloudwatch:GetMetricStatistics",
                "ecs:List*",
                "ecs:UpdateService",
                "ecs:Describe*",
                "sns:Publish",
                "rds:DescribeDBClusters",
                "rds:DescribeDBInstances",
                "rds:StopDBInstance",
                "rds:ListTagsForResource",
                "rds:StopDBCluster",
                "rds:DescribeDBClusters"
            ],
            "Resource": "*"
        }
    ]
}
+++++++++++++++++++++++++
