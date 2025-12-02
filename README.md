# AWS Operations MCP Server

FastMCP server for AWS operations across multiple accounts. Provides comprehensive SRE tools for Secrets Manager, Route53, S3, and other AWS services with multi-account support via AssumeRole.

## Features

### Secrets Manager Operations
- **Create secrets** with tags and descriptions
- **Retrieve secret values** with version support
- **Update secrets** and their metadata
- **Delete secrets** with recovery window or force delete
- **List secrets** with filtering and pagination
- **Describe secrets** (metadata without value)
- **Restore deleted secrets** within recovery window
- **Tag/Untag secrets** for organization

### Multi-Account Support
- **AssumeRole** based authentication for cross-account access (production)
- **AWS Profiles** support for local development (~/.aws/credentials)
- **Per-request authentication** - role_arn or profile provided per tool call
- **Pre-configured account mappings** via environment variables
- **No stored credentials** - maximum security

### Future Services (Extensible Architecture)
- Route53: DNS record management
- S3: Bucket and object operations
- EC2: Instance operations
- IAM: Role/policy management

## Architecture

### Multi-Account Authentication

```
┌──────────────────────────────────────────────────────────────┐
│                    MCP Server (EKS)                          │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  IRSA Role: aws-ops-mcp (sts:AssumeRole permission)    │  │
│  └────────────────────────────────────────────────────────┘  │
│                              │                               │
│           Each tool call includes: role_arn                  │
│                              ▼                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                   STS AssumeRole                       │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         ▼                     ▼                     ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  Account A      │   │  Account B      │   │  Account C      │
│  Trust Policy   │   │  Trust Policy   │   │  Trust Policy   │
│  → aws-ops-mcp  │   │  → aws-ops-mcp  │   │  → aws-ops-mcp  │
└─────────────────┘   └─────────────────┘   └─────────────────┘
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- AWS credentials (for local development)

### Local Development

```bash
# Clone the repository
git clone https://github.com/DepStacks/tool.aws-ops.git
cd tool.aws-ops

# Copy and configure environment
cp .env.example .env
# Edit .env with your configuration

# Start the server
chmod +x docker-start.sh
./docker-start.sh

# Server runs on http://localhost:8100/sse
```

### MCP Client Configuration

Add to your MCP client config:

```json
{
  "mcpServers": {
    "aws-ops": {
      "url": "http://localhost:8100/sse",
      "headers": {
        "Authorization": "Bearer YOUR_AUTH_TOKEN"
      }
    }
  }
}
```

## Available Tools

### Utility Tools

#### `list_accounts`
List all pre-configured AWS accounts with their role ARNs.

### Secrets Manager Tools

#### `create_secret`
Create a new secret in AWS Secrets Manager.

```python
# Using AssumeRole (production)
{
    "name": "prod/myapp/database",
    "secret_value": "{\"username\":\"admin\",\"password\":\"secret\"}",
    "description": "Database credentials",
    "tags": {"Environment": "prod", "Team": "platform"},
    "role_arn": "arn:aws:iam::111111111111:role/aws-ops-target",
    "region": "us-east-1"
}

# Using AWS Profile (local development)
{
    "name": "staging/myapp/database",
    "secret_value": "{\"username\":\"admin\",\"password\":\"secret\"}",
    "profile": "staging",
    "region": "us-east-1"
}
```

#### `get_secret_value`
Retrieve the value of a secret.

```python
# Using AssumeRole
{
    "secret_id": "prod/myapp/database",
    "role_arn": "arn:aws:iam::111111111111:role/aws-ops-target"
}

# Using AWS Profile
{
    "secret_id": "staging/myapp/database",
    "profile": "staging"
}
```

#### `update_secret`
Update an existing secret's value.

#### `delete_secret`
Delete a secret (with configurable recovery window).

#### `list_secrets`
List secrets with optional name prefix filtering.

#### `describe_secret`
Get metadata about a secret (without the value).

#### `restore_secret`
Restore a previously deleted secret.

#### `tag_secret`
Add or update tags on a secret.

#### `untag_secret`
Remove tags from a secret.

## Configuration

### Environment Variables

```bash
# Default AWS Region
AWS_REGION=us-east-1

# MCP Authentication Token (required for API access)
MCP_AUTH_TOKEN=your-secret-token

# Pre-configured Account Role ARNs (Production - AssumeRole)
ACCOUNT_PRODUCTION_ROLE_ARN=arn:aws:iam::111111111111:role/aws-ops-target
ACCOUNT_STAGING_ROLE_ARN=arn:aws:iam::222222222222:role/aws-ops-target

# Pre-configured Account Profiles (Local Development - ~/.aws/credentials)
ACCOUNT_PRODUCTION_PROFILE=prod
ACCOUNT_STAGING_PROFILE=staging
ACCOUNT_DEVELOPMENT_PROFILE=dev
```

### Authentication Methods

All tools support three authentication methods:

| Method | Parameter | Use Case |
|--------|-----------|----------|
| **Profile** | `profile="staging"` | Local development with ~/.aws/credentials |
| **AssumeRole** | `role_arn="arn:aws:iam::..."` | Production with IRSA |
| **Default** | (none) | Uses environment credentials |

**Priority**: `profile` > `role_arn` > default credentials

### Target Account Setup

Each target AWS account needs an IAM role with:

1. **Trust Policy** (allows the base role to assume it):
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "AWS": "arn:aws:iam::BASE_ACCOUNT_ID:role/aws-ops-mcp"
    },
    "Action": "sts:AssumeRole"
  }]
}
```

2. **Permissions Policy** (for Secrets Manager):
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "secretsmanager:CreateSecret",
      "secretsmanager:GetSecretValue",
      "secretsmanager:PutSecretValue",
      "secretsmanager:UpdateSecret",
      "secretsmanager:DeleteSecret",
      "secretsmanager:ListSecrets",
      "secretsmanager:DescribeSecret",
      "secretsmanager:RestoreSecret",
      "secretsmanager:TagResource",
      "secretsmanager:UntagResource"
    ],
    "Resource": "*"
  }]
}
```

## Extensibility

The architecture is designed for easy addition of new AWS services:

### Adding a New Service

1. Create a new service manager in `services/`:

```python
# services/route53.py
from .base import AWSServiceBase

class Route53Service(AWSServiceBase):
    def _get_client(self, role_arn=None, region=None):
        return self._get_aws_client('route53', role_arn, region)
    
    async def list_hosted_zones(self, role_arn=None, region=None):
        client = self._get_client(role_arn, region)
        response = client.list_hosted_zones()
        return {"success": True, "zones": response['HostedZones']}
```

2. Add tools to `server.py`:

```python
from services.route53 import Route53Service
route53 = Route53Service()

@mcp.tool()
async def list_hosted_zones(role_arn=None, region=None):
    """List Route53 hosted zones"""
    return await route53.list_hosted_zones(role_arn, region)
```

3. Update documentation

## Security Best Practices

1. **Never use AWS access keys** - Use IRSA in production
2. **Least privilege** - Target roles have minimum permissions
3. **Per-request authentication** - Role ARN provided per request
4. **Audit trail** - CloudTrail logs all assumed role actions
5. **MCP API authentication** - Bearer token required
6. **TLS encryption** - HTTPS only in production
7. **No stored credentials** - Credentials only exist in memory

## Monitoring

### Health Checks

- **Endpoint**: `/healthz`
- **Used by**: ALB health checks, Kubernetes probes

### Logging

- Structured logs to stdout
- Compatible with CloudWatch, Fluent Bit, etc.

## Troubleshooting

### AssumeRole Fails

- Verify trust policy in target account
- Check base role has `sts:AssumeRole` permission
- Verify role ARN is correctly formatted

### Permission Denied

- Verify target role has required service permissions
- Check resource-level permissions if applicable
- Ensure you're using the correct region

### Connection Timeout During Startup

- boto3 clients are lazy-loaded to prevent this
- Check server logs for initialization errors

## Development

### Project Structure

```
tool.aws-ops/
├── server.py              # Main FastMCP server
├── config.py              # Configuration management
├── services/              # AWS service managers
│   ├── __init__.py
│   ├── base.py            # Base class with AssumeRole
│   └── secrets_manager.py # Secrets Manager operations
├── requirements.txt       # Python dependencies
├── Dockerfile             # Container image
├── docker-compose.yml     # Local development
├── docker-start.sh        # Startup script
├── .env.example           # Example configuration
├── AGENTS.md              # Agent documentation
└── README.md              # This file
```

### Running Tests

```bash
# Install dependencies
pip install -r requirements.txt

# Test imports
python -c "from server import mcp; print('OK')"
```

## License

Internal tool for DepStacks use.
