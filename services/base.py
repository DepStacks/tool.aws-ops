"""
Base AWS Service Manager with multi-account support via AssumeRole and AWS Profiles
"""

import boto3
from botocore.exceptions import ClientError
from typing import Dict, Any, Optional
import logging
import os

logger = logging.getLogger(__name__)


class AWSServiceBase:
    """
    Base class for AWS service managers with AssumeRole and Profile support.
    
    Handles multi-account authentication by:
    1. Using AWS profiles (~/.aws/credentials) - ideal for local development
    2. Assuming roles in target accounts - ideal for production (IRSA)
    
    Clients are lazily loaded and cached per (service, role_arn, profile, region) tuple.
    
    Authentication priority:
    - If profile is provided: Use named profile from ~/.aws/credentials
    - If role_arn is provided: Use AssumeRole with current credentials
    - Otherwise: Use default credentials (env vars, IRSA, instance profile)
    """
    
    def __init__(self):
        self._clients: Dict[str, Any] = {}
        self._sts_client = None
        self._credentials_cache: Dict[str, Dict[str, Any]] = {}
        self._sessions: Dict[str, boto3.Session] = {}
    
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
    
    def _get_session(self, profile: Optional[str] = None) -> boto3.Session:
        """
        Get or create a boto3 Session for the specified profile.
        
        Args:
            profile: AWS profile name from ~/.aws/credentials
            
        Returns:
            boto3 Session object
        """
        cache_key = profile or 'default'
        
        if cache_key not in self._sessions:
            if profile:
                self._sessions[cache_key] = boto3.Session(profile_name=profile)
                logger.debug(f"Created session with profile: {profile}")
            else:
                self._sessions[cache_key] = boto3.Session()
                logger.debug("Created default session")
        
        return self._sessions[cache_key]
    
    def _get_aws_client(
        self,
        service_name: str,
        role_arn: Optional[str] = None,
        region: Optional[str] = None,
        profile: Optional[str] = None
    ):
        """
        Get or create a boto3 client for the specified service.
        
        Authentication priority:
        1. If profile is provided: Use named profile from ~/.aws/credentials
        2. If role_arn is provided: Use AssumeRole with current credentials
        3. Otherwise: Use default credentials (env vars, IRSA, instance profile)
        
        Clients are cached per (service, role_arn, profile, region) combination.
        
        Args:
            service_name: AWS service name (e.g., 'secretsmanager', 's3')
            role_arn: Optional IAM role ARN to assume
            region: AWS region (defaults to AWS_REGION env var)
            profile: Optional AWS profile name from ~/.aws/credentials
            
        Returns:
            boto3 client for the specified service
            
        Note:
            profile and role_arn are mutually exclusive. If both are provided,
            profile takes precedence for local development convenience.
        """
        region = region or self._get_default_region()
        cache_key = f"{service_name}:{profile or 'no-profile'}:{role_arn or 'no-role'}:{region}"
        
        if cache_key not in self._clients:
            if profile:
                # Use named profile - ideal for local development
                session = self._get_session(profile)
                self._clients[cache_key] = session.client(service_name, region_name=region)
                logger.debug(f"Created client for {service_name} in {region} using profile: {profile}")
            elif role_arn:
                # Assume the role and use temporary credentials
                credentials = self._assume_role(role_arn)
                self._clients[cache_key] = boto3.client(
                    service_name,
                    region_name=region,
                    **credentials
                )
                logger.debug(f"Created client for {service_name} in {region} using role: {role_arn}")
            else:
                # Use default credentials (env vars, IRSA, instance profile)
                self._clients[cache_key] = boto3.client(service_name, region_name=region)
                logger.debug(f"Created client for {service_name} in {region} using default credentials")
        
        return self._clients[cache_key]
    
    def clear_cache(
        self,
        role_arn: Optional[str] = None,
        profile: Optional[str] = None
    ):
        """
        Clear cached clients, credentials, and sessions.
        
        Args:
            role_arn: If provided, only clear cache for this role
            profile: If provided, only clear cache for this profile
            
        Note:
            If neither role_arn nor profile is provided, clears all caches.
        """
        if role_arn:
            # Clear specific role
            self._credentials_cache.pop(role_arn, None)
            keys_to_remove = [k for k in self._clients if f":{role_arn}:" in k]
            for key in keys_to_remove:
                del self._clients[key]
        elif profile:
            # Clear specific profile
            self._sessions.pop(profile, None)
            keys_to_remove = [k for k in self._clients if f":{profile}:" in k]
            for key in keys_to_remove:
                del self._clients[key]
        else:
            # Clear all
            self._credentials_cache.clear()
            self._sessions.clear()
            self._clients.clear()
