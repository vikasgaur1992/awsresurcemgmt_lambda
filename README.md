# awsresurcemgmt_lambda
++++++++++++++++++++++++++
IAM Permissions - cost_optimization_lambda
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
