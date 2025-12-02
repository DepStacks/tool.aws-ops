"""
Base AWS Service Manager with multi-account support via AssumeRole
"""

import boto3
from botocore.exceptions import ClientError
from typing import Dict, Any, Optional
import logging
import os

logger = logging.getLogger(__name__)


class AWSServiceBase:
    """
    Base class for AWS service managers with AssumeRole support.
    
    Handles multi-account authentication by assuming roles in target accounts.
    Clients are lazily loaded and cached per (service, role_arn, region) tuple.
    """
    
    def __init__(self):
        self._clients: Dict[str, Any] = {}
        self._sts_client = None
        self._credentials_cache: Dict[str, Dict[str, Any]] = {}
    
    def _get_sts_client(self):
        """Get or create STS client for AssumeRole operations"""
        if self._sts_client is None:
            self._sts_client = boto3.client('sts')
        return self._sts_client
    
    def _get_default_region(self) -> str:
        """Get default AWS region from environment"""
        return os.getenv('AWS_REGION', os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))
    
    def _assume_role(self, role_arn: str, session_name: str = 'MCPSession') -> Dict[str, Any]:
        """
        Assume an IAM role and return temporary credentials.
        
        Credentials are cached for reuse within their validity period.
        
        Args:
            role_arn: The ARN of the role to assume
            session_name: Name for the assumed role session
            
        Returns:
            Dictionary with AccessKeyId, SecretAccessKey, SessionToken
        """
        # Check cache first (simplified - in production, check expiration)
        if role_arn in self._credentials_cache:
            return self._credentials_cache[role_arn]
        
        try:
            sts = self._get_sts_client()
            response = sts.assume_role(
                RoleArn=role_arn,
                RoleSessionName=session_name,
                DurationSeconds=3600  # 1 hour
            )
            
            credentials = {
                'aws_access_key_id': response['Credentials']['AccessKeyId'],
                'aws_secret_access_key': response['Credentials']['SecretAccessKey'],
                'aws_session_token': response['Credentials']['SessionToken']
            }
            
            self._credentials_cache[role_arn] = credentials
            logger.info(f"Successfully assumed role: {role_arn}")
            return credentials
            
        except ClientError as e:
            logger.error(f"Failed to assume role {role_arn}: {e}")
            raise
    
    def _get_aws_client(
        self,
        service_name: str,
        role_arn: Optional[str] = None,
        region: Optional[str] = None
    ):
        """
        Get or create a boto3 client for the specified service.
        
        If role_arn is provided, assumes that role before creating the client.
        Clients are cached per (service, role_arn, region) combination.
        
        Args:
            service_name: AWS service name (e.g., 'secretsmanager', 's3')
            role_arn: Optional IAM role ARN to assume
            region: AWS region (defaults to AWS_REGION env var)
            
        Returns:
            boto3 client for the specified service
        """
        region = region or self._get_default_region()
        cache_key = f"{service_name}:{role_arn or 'default'}:{region}"
        
        if cache_key not in self._clients:
            client_kwargs = {'region_name': region}
            
            if role_arn:
                # Assume the role and use temporary credentials
                credentials = self._assume_role(role_arn)
                client_kwargs.update(credentials)
            
            self._clients[cache_key] = boto3.client(service_name, **client_kwargs)
            logger.debug(f"Created client for {service_name} in {region} (role: {role_arn or 'default'})")
        
        return self._clients[cache_key]
    
    def clear_cache(self, role_arn: Optional[str] = None):
        """
        Clear cached clients and credentials.
        
        Args:
            role_arn: If provided, only clear cache for this role. Otherwise, clear all.
        """
        if role_arn:
            # Clear specific role
            self._credentials_cache.pop(role_arn, None)
            keys_to_remove = [k for k in self._clients if f":{role_arn}:" in k]
            for key in keys_to_remove:
                del self._clients[key]
        else:
            # Clear all
            self._credentials_cache.clear()
            self._clients.clear()
