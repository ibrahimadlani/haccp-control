# AWS Production Architecture Guide

This guide describes a production-ready AWS target for the HACCP FastAPI backend:

- Container runtime: ECS Fargate or an EC2 host running Docker.
- Database: Amazon RDS PostgreSQL 16.
- DNS and TLS: Route 53 plus AWS Certificate Manager.
- Registry: Amazon ECR.
- Secrets: AWS Secrets Manager, SSM Parameter Store, or runtime environment variables. Do not hard-code secrets.

## 1. Network Baseline

Create or reuse a VPC with at least two Availability Zones.

Recommended subnets:

- Public subnets for the internet-facing load balancer.
- Private application subnets for ECS tasks or EC2 instances running the API.
- Private database subnets for RDS.

Create security groups:

- `haccp-alb-sg`
  - Inbound: TCP 443 from `0.0.0.0/0`.
  - Optional inbound: TCP 80 from `0.0.0.0/0` only for HTTP to HTTPS redirects.
  - Outbound: TCP 8000 to `haccp-api-sg`.
- `haccp-api-sg`
  - Inbound: TCP 8000 from `haccp-alb-sg`.
  - Outbound: TCP 5432 to `haccp-rds-sg`.
  - Outbound: HTTPS 443 to AWS services such as ECR, CloudWatch, S3, Secrets Manager.
- `haccp-rds-sg`
  - Inbound: TCP 5432 from `haccp-api-sg` only.
  - No public inbound access.

## 2. Amazon RDS PostgreSQL 16

Provision a managed database:

```bash
aws rds create-db-subnet-group \
  --db-subnet-group-name haccp-rds-private-subnets \
  --db-subnet-group-description "Private subnets for HACCP RDS" \
  --subnet-ids subnet-private-a subnet-private-b
```

Create the DB instance with encryption at rest:

```bash
aws rds create-db-instance \
  --db-instance-identifier haccp-prod-postgres \
  --engine postgres \
  --engine-version 16 \
  --db-instance-class db.t4g.medium \
  --allocated-storage 50 \
  --storage-type gp3 \
  --storage-encrypted \
  --kms-key-id alias/aws/rds \
  --db-name haccp_control \
  --master-username haccp_admin \
  --master-user-password "$RDS_MASTER_PASSWORD" \
  --db-subnet-group-name haccp-rds-private-subnets \
  --vpc-security-group-ids sg-haccp-rds \
  --backup-retention-period 14 \
  --deletion-protection \
  --no-publicly-accessible
```

Production requirements:

- Store `RDS_MASTER_PASSWORD` in Secrets Manager, never in Git.
- Enable automated backups and deletion protection.
- Use a customer-managed KMS key if required by public-sector procurement rules.
- Restrict `haccp-rds-sg` inbound traffic to `haccp-api-sg` only.

Set the backend runtime variable:

```text
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<rds-endpoint>:5432/haccp_control
```

Run migrations from a controlled release job or a one-off ECS task:

```bash
uv run alembic upgrade head
```

## 3. Container Runtime And ECR

Create the ECR repository:

```bash
aws ecr create-repository \
  --repository-name haccp-backend \
  --image-scanning-configuration scanOnPush=true \
  --encryption-configuration encryptionType=AES256
```

GitHub Actions pushes:

```text
<account-id>.dkr.ecr.<region>.amazonaws.com/haccp-backend:<git-sha>
```

For ECS Fargate, configure the task with:

- Image from ECR.
- Container port `8000`.
- Environment variables from Secrets Manager or SSM Parameter Store.
- IAM task role allowing access only to required S3 buckets and secrets.
- CloudWatch Logs enabled.

Required runtime variables:

```text
DATABASE_URL
JWT_SECRET_KEY
JWT_ALGORITHM
ESTABLISHMENT_ACCESS_TOKEN_EXPIRE_HOURS
AWS_REGION
AWS_ENDPOINT_URL
S3_PUBLIC_ENDPOINT_URL
S3_BUCKET_NAME
BACKEND_CORS_ORIGINS
```

Use an IAM role for S3 access in production rather than long-lived AWS access keys when running on ECS.

## 4. Route 53, ACM And HTTPS

Create or use a public hosted zone:

```bash
aws route53 create-hosted-zone \
  --name saas-haccp.fr \
  --caller-reference "$(date +%s)"
```

Request a public ACM certificate in the same region as the Application Load Balancer:

```bash
aws acm request-certificate \
  --domain-name api.saas-haccp.fr \
  --validation-method DNS
```

Add the ACM-provided CNAME validation record to Route 53. After validation, attach the certificate to an HTTPS listener on the ALB.

ALB setup:

- Listener `443` with the ACM certificate.
- Listener `80` redirecting to HTTPS.
- Target group protocol HTTP, port `8000`.
- Health check path `/health`.
- Target type:
  - `ip` for ECS Fargate.
  - `instance` for EC2.

Create the DNS record:

```bash
aws route53 change-resource-record-sets \
  --hosted-zone-id ZONE_ID \
  --change-batch file://route53-api-record.json
```

Example `route53-api-record.json`:

```json
{
  "Changes": [
    {
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "api.saas-haccp.fr",
        "Type": "A",
        "AliasTarget": {
          "HostedZoneId": "ALB_HOSTED_ZONE_ID",
          "DNSName": "dualstack.your-alb.amazonaws.com",
          "EvaluateTargetHealth": true
        }
      }
    }
  ]
}
```

## 5. GitHub Secrets

Configure these repository secrets:

```text
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_REGION
ECR_REPOSITORY
```

Recommended production improvement:

- Replace static AWS keys with GitHub OIDC federation.
- Use an IAM role constrained to ECR push and deployment permissions only.

## 6. Production Security Checklist

- RDS is private and encrypted at rest.
- API tasks run in private subnets.
- Only the ALB is public.
- HTTPS is mandatory.
- S3 buckets block public access unless explicitly using signed URLs or controlled public assets.
- Secrets are stored in Secrets Manager or SSM Parameter Store.
- Container runs as a non-root user.
- ECR image scanning is enabled.
- CloudWatch metrics and logs are enabled.
