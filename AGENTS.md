# AWS Operations MCP Server - Agent Documentation

## Project Overview

FastMCP HTTP server for AWS operations across multiple accounts. Provides SREs with tools for Secrets Manager, Route53, S3, and other AWS services with multi-account support via AssumeRole and AWS Profiles.

## Architecture

### Components

1. **server.py** - Main FastMCP server
   - Defines all MCP tools with `@mcp.tool()` decorator
   - Handles HTTP/SSE transport
   - Routes requests to appropriate service managers

2. **services/** - Modular AWS service managers
   - `base.py` - Base class with AssumeRole and Profile support
   - `secrets_manager.py` - Secrets Manager CRUD operations
   - Future: `route53.py`, `s3.py`, `ec2.py`, etc.

3. **config.py** - Configuration Management
   - Loads settings from environment variables
   - Role ARN and Profile mappings for accounts
   - Uses python-dotenv for `.env` file support

### Multi-Account Authentication Model

**CRITICAL SECURITY PATTERN**:

1. **Base Role (IRSA)** - Production:
   - EKS ServiceAccount with IAM Role
   - Has `sts:AssumeRole` permission only
   - No direct AWS service permissions

2. **Target Roles (per account)**:
   - Each AWS account has a role that trusts the base role
   - LLM provides `role_arn` per tool call
   - Maximum flexibility: credentials only exist in memory during request

3. **AWS Profiles** - Local Development:
   - Uses `~/.aws/credentials` profiles
   - LLM provides `profile` per tool call
   - Ideal for local testing with multiple accounts

4. **Authentication Priority**:
   ```
   profile (if provided) → role_arn (if provided) → default credentials
   ```

5. **AssumeRole Flow** (Production):
   ```
   Request → Base Role → STS AssumeRole → Target Role → AWS Service
   ```

6. **Profile Flow** (Local Development):
   ```
   Request → ~/.aws/credentials → Named Profile → AWS Service
   ```

### Transport

- **HTTP/SSE** (Server-Sent Events) instead of STDIO
- Runs on port 8000 in container
- Benefits:
  - No buffering issues
  - Kubernetes-friendly
  - Load balancer compatible

## Adding New AWS Services

### Step 1: Create Service Manager

Create `services/{service_name}.py`:

```python
from typing import Dict, Any, Optional
from .base import AWSServiceBase

class ServiceNameManager(AWSServiceBase):
    """Manages AWS {ServiceName} operations"""
    
    def _get_client(self, role_arn: Optional[str] = None, region: Optional[str] = None, profile: Optional[str] = None):
        return self._get_aws_client('servicename', role_arn, region, profile)
    
    async def operation_name(
        self,
        param1: str,
        role_arn: Optional[str] = None,
        region: Optional[str] = None,
        profile: Optional[str] = None
    ) -> Dict[str, Any]:
        """Describe the operation"""
        try:
            client = self._get_client(role_arn, region, profile)
            response = client.operation(...)
            return {"success": True, "data": response}
        except Exception as e:
            return {"success": False, "error": str(e)}
```

### Step 2: Add Tools to server.py

```python
from services.service_name import ServiceNameManager

service_manager = ServiceNameManager()

@mcp.tool()
async def operation_name(
    param1: str,
    role_arn: Optional[str] = None,
    region: Optional[str] = None,
    profile: Optional[str] = None
) -> Dict[str, Any]:
    """Tool description for LLM"""
    return await service_manager.operation_name(param1, role_arn, region, profile)
```

### Step 3: Update Documentation

1. Add tools to README.md
2. Update AGENTS.md if patterns change

## Available Services

### Secrets Manager
- `create_secret` - Create a new secret
- `get_secret_value` - Retrieve secret value
- `update_secret` - Update secret value
- `delete_secret` - Delete a secret (with recovery window)
- `list_secrets` - List all secrets with filtering

### Future Services
- Route53: DNS record management
- S3: Bucket operations, object management
- EC2: Instance operations
- IAM: Role/policy management

## Configuration

### Environment Variables

```bash
# AWS Region (default)
AWS_REGION=us-east-1

# MCP Authentication
MCP_AUTH_TOKEN=your-secret-token

# Optional: Pre-configured role ARN mappings (Production)
ACCOUNT_PRODUCTION_ROLE_ARN=arn:aws:iam::111111111111:role/aws-ops-target
ACCOUNT_STAGING_ROLE_ARN=arn:aws:iam::222222222222:role/aws-ops-target

# Optional: Pre-configured profile mappings (Local Development)
ACCOUNT_PRODUCTION_PROFILE=prod
ACCOUNT_STAGING_PROFILE=staging
```

### Target Account Setup

Each target AWS account needs:

1. **IAM Role** with trust policy:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Principal": {
         "AWS": "arn:aws:iam::BASE_ACCOUNT:role/aws-ops-mcp"
       },
       "Action": "sts:AssumeRole"
     }]
   }
   ```

2. **Service permissions** attached to the role

## Security Considerations

1. **Never use AWS access keys** - Use IRSA and AssumeRole in production
2. **Least privilege** - Target roles have minimum permissions
3. **Per-request authentication** - role_arn or profile provided per call
4. **Audit trail** - CloudTrail logs all assumed role actions
5. **MCP API authentication** - Bearer token required
6. **TLS encryption** - HTTPS only in production
7. **Profile for dev only** - Use profiles only in local development

## Development Workflow

### Local Development

```bash
# Using Docker
./docker-start.sh

# Server runs on http://localhost:8100/sse
```

### Adding Tools Checklist

- [ ] Create/update service manager in `services/`
- [ ] Add tool functions to `server.py`
- [ ] Update README.md with tool documentation
- [ ] Test locally with Docker
- [ ] Update AGENTS.md if patterns change

## Troubleshooting

### Common Issues

**AssumeRole fails**:
- Verify trust policy in target account
- Check base role has `sts:AssumeRole` permission
- Verify role ARN is correct

**Connection timeout during startup**:
- boto3 clients are lazy-loaded to prevent this
- Check server logs for initialization errors

**Permission denied on AWS operation**:
- Verify target role has required permissions
- Check resource-level permissions if applicable

## Maintainers

- DepStacks Team
- Primary contact: SRE team channel
