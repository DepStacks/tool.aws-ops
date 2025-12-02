"""
Configuration management for AWS Operations MCP Server
Loads settings from environment variables
"""

import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def get_aws_region() -> str:
    """Get default AWS region from environment variable"""
    return os.getenv('AWS_REGION', os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))


def get_mcp_auth_token() -> Optional[str]:
    """Get MCP authentication token from environment"""
    return os.getenv('MCP_AUTH_TOKEN')


def get_account_role_arn(account_name: str) -> Optional[str]:
    """
    Get pre-configured role ARN for a named account.
    
    Environment variable format: ACCOUNT_{NAME}_ROLE_ARN
    
    Args:
        account_name: Name of the account (e.g., 'production', 'staging')
        
    Returns:
        Role ARN if configured, None otherwise
    """
    name = account_name.upper().replace('-', '_')
    return os.getenv(f'ACCOUNT_{name}_ROLE_ARN')


def list_configured_accounts() -> Dict[str, str]:
    """
    List all pre-configured account role ARN mappings.
    
    Returns:
        Dictionary mapping account names to role ARNs
    """
    accounts = {}
    
    for key, value in os.environ.items():
        if key.startswith('ACCOUNT_') and key.endswith('_ROLE_ARN'):
            # Extract account name from ACCOUNT_{NAME}_ROLE_ARN
            name_part = key[8:-9]  # Remove 'ACCOUNT_' prefix and '_ROLE_ARN' suffix
            account_name = name_part.lower().replace('_', '-')
            accounts[account_name] = value
    
    return accounts


def get_account_profile(account_name: str) -> Optional[str]:
    """
    Get pre-configured AWS profile for a named account.
    
    Environment variable format: ACCOUNT_{NAME}_PROFILE
    
    Args:
        account_name: Name of the account (e.g., 'production', 'staging')
        
    Returns:
        Profile name if configured, None otherwise
    """
    name = account_name.upper().replace('-', '_')
    return os.getenv(f'ACCOUNT_{name}_PROFILE')


def list_configured_profiles() -> Dict[str, str]:
    """
    List all pre-configured account profile mappings.
    
    Returns:
        Dictionary mapping account names to profile names
    """
    profiles = {}
    
    for key, value in os.environ.items():
        if key.startswith('ACCOUNT_') and key.endswith('_PROFILE'):
            # Extract account name from ACCOUNT_{NAME}_PROFILE
            name_part = key[8:-8]  # Remove 'ACCOUNT_' prefix and '_PROFILE' suffix
            account_name = name_part.lower().replace('_', '-')
            profiles[account_name] = value
    
    return profiles


def get_server_config() -> Dict[str, Any]:
    """
    Get server configuration settings.
    
    Returns:
        Dictionary with server configuration
    """
    return {
        'aws_region': get_aws_region(),
        'mcp_auth_token': get_mcp_auth_token(),
        'configured_accounts': list_configured_accounts(),
        'configured_profiles': list_configured_profiles()
    }
