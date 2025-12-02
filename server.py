"""
FastMCP Server for AWS Operations
Provides multi-account AWS operations for SRE teams
"""

import sys
import os

# Force unbuffered output for MCP STDIO communication
os.environ['PYTHONUNBUFFERED'] = '1'
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from fastmcp import FastMCP
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.requests import Request
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional, List, Dict, Any

from services.secrets_manager import SecretsManagerService
from config import get_mcp_auth_token, list_configured_accounts, list_configured_profiles, get_aws_region

# Initialize FastMCP server
mcp = FastMCP("aws-ops")

# Initialize service managers
secrets_manager = SecretsManagerService()


# =============================================================================
# Health & OpenAPI Endpoints
# =============================================================================

@mcp.custom_route("/healthz", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    """Health check endpoint for Kubernetes probes"""
    return PlainTextResponse("OK")


@mcp.custom_route("/openapi.json", methods=["GET", "OPTIONS"])
async def openapi_spec(request: Request) -> JSONResponse:
    """OpenAPI specification for the MCP server"""
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type",
    }
    
    if request.method == "OPTIONS":
        return JSONResponse({}, status_code=204, headers=cors_headers)
    
    schema = {
        "openapi": "3.0.0",
        "info": {
            "title": "AWS Operations MCP Server",
            "version": "1.0.0",
            "description": "Multi-account AWS operations via MCP protocol"
        },
        "servers": [{"url": "/"}],
        "paths": {
            "/healthz": {
                "get": {
                    "summary": "Health check",
                    "responses": {"200": {"description": "OK"}}
                }
            }
        },
        "components": {
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer"}
            }
        }
    }
    
    return JSONResponse(schema, headers=cors_headers)


# =============================================================================
# Authentication Middleware
# =============================================================================

MCP_AUTH_TOKEN = get_mcp_auth_token()


async def auth_middleware(request: Request, call_next):
    """Validate authentication token for all requests"""
    # Skip auth for health and OpenAPI endpoints
    if request.url.path in ("/healthz", "/openapi.json"):
        return await call_next(request)
    
    # Check Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return JSONResponse({"detail": "Missing Authorization header"}, status_code=401)
    
    # Validate Bearer token
    if not auth_header.startswith("Bearer "):
        return JSONResponse({"detail": "Invalid authorization format. Use: Bearer <token>"}, status_code=401)
    
    token = auth_header[7:]
    
    # Validate token against environment variable
    if MCP_AUTH_TOKEN and token != MCP_AUTH_TOKEN:
        return JSONResponse({"detail": "Invalid authentication token"}, status_code=403)
    
    return await call_next(request)


# =============================================================================
# Utility Tools
# =============================================================================

@mcp.tool()
async def list_accounts(
    region: Optional[str] = None
) -> Dict[str, Any]:
    """
    List all pre-configured AWS accounts with their role ARNs and profiles.
    
    Args:
        region: AWS region to use as default (defaults to AWS_REGION env var)
    
    Returns:
        Dictionary with configured accounts, profiles, and default region
    """
    accounts = list_configured_accounts()
    profiles = list_configured_profiles()
    return {
        "success": True,
        "accounts": accounts,
        "profiles": profiles,
        "accounts_count": len(accounts),
        "profiles_count": len(profiles),
        "default_region": region or get_aws_region()
    }


# =============================================================================
# Secrets Manager Tools
# =============================================================================

@mcp.tool()
async def create_secret(
    name: str,
    secret_value: str,
    description: Optional[str] = None,
    tags: Optional[Dict[str, str]] = None,
    role_arn: Optional[str] = None,
    region: Optional[str] = None,
    profile: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new secret in AWS Secrets Manager.
    
    Args:
        name: Name of the secret (e.g., 'prod/myapp/database')
        secret_value: The secret value (string or JSON string)
        description: Optional description for the secret
        tags: Optional tags as key-value pairs
        role_arn: IAM role ARN to assume (for cross-account access)
        region: AWS region (defaults to AWS_REGION env var)
        profile: AWS profile name from ~/.aws/credentials (for local dev)
    
    Returns:
        Dictionary with creation status and secret ARN
    """
    return await secrets_manager.create_secret(
        name=name,
        secret_value=secret_value,
        description=description,
        tags=tags,
        role_arn=role_arn,
        region=region,
        profile=profile
    )


@mcp.tool()
async def get_secret_value(
    secret_id: str,
    version_id: Optional[str] = None,
    version_stage: Optional[str] = None,
    role_arn: Optional[str] = None,
    region: Optional[str] = None,
    profile: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieve the value of a secret from AWS Secrets Manager.
    
    Args:
        secret_id: Secret name or ARN
        version_id: Optional specific version ID
        version_stage: Optional version stage (AWSCURRENT, AWSPREVIOUS)
        role_arn: IAM role ARN to assume (for cross-account access)
        region: AWS region (defaults to AWS_REGION env var)
        profile: AWS profile name from ~/.aws/credentials (for local dev)
    
    Returns:
        Dictionary with secret value and metadata
    """
    return await secrets_manager.get_secret_value(
        secret_id=secret_id,
        version_id=version_id,
        version_stage=version_stage,
        role_arn=role_arn,
        region=region,
        profile=profile
    )


@mcp.tool()
async def update_secret(
    secret_id: str,
    secret_value: str,
    description: Optional[str] = None,
    role_arn: Optional[str] = None,
    region: Optional[str] = None,
    profile: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update an existing secret's value in AWS Secrets Manager.
    
    Args:
        secret_id: Secret name or ARN
        secret_value: New secret value (string or JSON string)
        description: Optional new description
        role_arn: IAM role ARN to assume (for cross-account access)
        region: AWS region (defaults to AWS_REGION env var)
        profile: AWS profile name from ~/.aws/credentials (for local dev)
    
    Returns:
        Dictionary with update status
    """
    return await secrets_manager.update_secret(
        secret_id=secret_id,
        secret_value=secret_value,
        description=description,
        role_arn=role_arn,
        region=region,
        profile=profile
    )


@mcp.tool()
async def delete_secret(
    secret_id: str,
    recovery_window_in_days: int = 30,
    force_delete_without_recovery: bool = False,
    role_arn: Optional[str] = None,
    region: Optional[str] = None,
    profile: Optional[str] = None
) -> Dict[str, Any]:
    """
    Delete a secret from AWS Secrets Manager.
    
    Args:
        secret_id: Secret name or ARN
        recovery_window_in_days: Days before permanent deletion (7-30, default: 30)
        force_delete_without_recovery: If True, delete immediately without recovery
        role_arn: IAM role ARN to assume (for cross-account access)
        region: AWS region (defaults to AWS_REGION env var)
        profile: AWS profile name from ~/.aws/credentials (for local dev)
    
    Returns:
        Dictionary with deletion status
    """
    return await secrets_manager.delete_secret(
        secret_id=secret_id,
        recovery_window_in_days=recovery_window_in_days,
        force_delete_without_recovery=force_delete_without_recovery,
        role_arn=role_arn,
        region=region,
        profile=profile
    )


@mcp.tool()
async def list_secrets(
    name_prefix: Optional[str] = None,
    max_results: int = 500,
    include_planned_deletion: bool = False,
    role_arn: Optional[str] = None,
    region: Optional[str] = None,
    profile: Optional[str] = None
) -> Dict[str, Any]:
    """
    List secrets in AWS Secrets Manager.
    
    Args:
        name_prefix: Optional prefix to filter secrets by name
        max_results: Maximum number of results (default: 500)
        include_planned_deletion: Include secrets scheduled for deletion
        role_arn: IAM role ARN to assume (for cross-account access)
        region: AWS region (defaults to AWS_REGION env var)
        profile: AWS profile name from ~/.aws/credentials (for local dev)
    
    Returns:
        Dictionary with list of secrets
    """
    filters = None
    if name_prefix:
        filters = [{"Key": "name", "Values": [name_prefix]}]
    
    return await secrets_manager.list_secrets(
        filters=filters,
        max_results=max_results,
        include_planned_deletion=include_planned_deletion,
        role_arn=role_arn,
        region=region,
        profile=profile
    )


@mcp.tool()
async def describe_secret(
    secret_id: str,
    role_arn: Optional[str] = None,
    region: Optional[str] = None,
    profile: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get metadata about a secret (without the secret value).
    
    Args:
        secret_id: Secret name or ARN
        role_arn: IAM role ARN to assume (for cross-account access)
        region: AWS region (defaults to AWS_REGION env var)
        profile: AWS profile name from ~/.aws/credentials (for local dev)
    
    Returns:
        Dictionary with secret metadata (rotation, tags, versions, etc.)
    """
    return await secrets_manager.describe_secret(
        secret_id=secret_id,
        role_arn=role_arn,
        region=region,
        profile=profile
    )


@mcp.tool()
async def restore_secret(
    secret_id: str,
    role_arn: Optional[str] = None,
    region: Optional[str] = None,
    profile: Optional[str] = None
) -> Dict[str, Any]:
    """
    Restore a previously deleted secret (within recovery window).
    
    Args:
        secret_id: Secret name or ARN
        role_arn: IAM role ARN to assume (for cross-account access)
        region: AWS region (defaults to AWS_REGION env var)
        profile: AWS profile name from ~/.aws/credentials (for local dev)
    
    Returns:
        Dictionary with restore status
    """
    return await secrets_manager.restore_secret(
        secret_id=secret_id,
        role_arn=role_arn,
        region=region,
        profile=profile
    )


@mcp.tool()
async def tag_secret(
    secret_id: str,
    tags: Dict[str, str],
    role_arn: Optional[str] = None,
    region: Optional[str] = None,
    profile: Optional[str] = None
) -> Dict[str, Any]:
    """
    Add or update tags on a secret.
    
    Args:
        secret_id: Secret name or ARN
        tags: Tags as key-value pairs (e.g., {"Environment": "prod", "Team": "platform"})
        role_arn: IAM role ARN to assume (for cross-account access)
        region: AWS region (defaults to AWS_REGION env var)
        profile: AWS profile name from ~/.aws/credentials (for local dev)
    
    Returns:
        Dictionary with tagging status
    """
    return await secrets_manager.tag_secret(
        secret_id=secret_id,
        tags=tags,
        role_arn=role_arn,
        region=region,
        profile=profile
    )


@mcp.tool()
async def untag_secret(
    secret_id: str,
    tag_keys: List[str],
    role_arn: Optional[str] = None,
    region: Optional[str] = None,
    profile: Optional[str] = None
) -> Dict[str, Any]:
    """
    Remove tags from a secret.
    
    Args:
        secret_id: Secret name or ARN
        tag_keys: List of tag keys to remove
        role_arn: IAM role ARN to assume (for cross-account access)
        region: AWS region (defaults to AWS_REGION env var)
        profile: AWS profile name from ~/.aws/credentials (for local dev)
    
    Returns:
        Dictionary with untagging status
    """
    return await secrets_manager.untag_secret(
        secret_id=secret_id,
        tag_keys=tag_keys,
        role_arn=role_arn,
        region=region,
        profile=profile
    )


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import sys
    
    # Check if we should run with HTTP transport
    if len(sys.argv) > 1 and sys.argv[1] == "--http":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
        print(f"Starting AWS Ops MCP server on HTTP port {port}...", file=sys.stderr)
        
        # Add auth middleware on SSE app
        try:
            app = mcp.sse_app
            # CORS first so preflight is handled before auth
            app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["*"],
                allow_headers=["*"],
            )
            app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)
            print("✓ Added auth middleware to FastMCP SSE app", file=sys.stderr)
        except Exception as e:
            print(f"⚠ Failed to add auth middleware: {e}", file=sys.stderr)
        
        mcp.run(transport="sse", port=port, host="0.0.0.0")
    else:
        # Default STDIO transport
        mcp.run()
