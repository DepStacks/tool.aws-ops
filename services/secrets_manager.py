"""
AWS Secrets Manager Service Manager
Handles CRUD operations for AWS Secrets Manager
"""

from typing import Dict, Any, Optional, List
from botocore.exceptions import ClientError
import logging
import json

from .base import AWSServiceBase

logger = logging.getLogger(__name__)


class SecretsManagerService(AWSServiceBase):
    """Manages AWS Secrets Manager operations across multiple accounts"""
    
    def _get_client(
        self,
        role_arn: Optional[str] = None,
        region: Optional[str] = None,
        profile: Optional[str] = None
    ):
        """Get Secrets Manager client"""
        return self._get_aws_client('secretsmanager', role_arn, region, profile)
    
    async def create_secret(
        self,
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
            name: Name of the secret
            secret_value: The secret value (string or JSON)
            description: Optional description for the secret
            tags: Optional tags as key-value pairs
            role_arn: IAM role ARN to assume for this operation
            region: AWS region (defaults to AWS_REGION)
            profile: AWS profile name from ~/.aws/credentials
            
        Returns:
            Dictionary with creation status and secret ARN
        """
        try:
            client = self._get_client(role_arn, region, profile)
            
            params = {
                'Name': name,
                'SecretString': secret_value
            }
            
            if description:
                params['Description'] = description
            
            if tags:
                params['Tags'] = [{'Key': k, 'Value': v} for k, v in tags.items()]
            
            response = client.create_secret(**params)
            
            return {
                "success": True,
                "secret_name": response['Name'],
                "secret_arn": response['ARN'],
                "version_id": response.get('VersionId'),
                "region": region or self._get_default_region()
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            return {
                "success": False,
                "error": error_message,
                "error_code": error_code,
                "secret_name": name
            }
    
    async def get_secret_value(
        self,
        secret_id: str,
        version_id: Optional[str] = None,
        version_stage: Optional[str] = None,
        role_arn: Optional[str] = None,
        region: Optional[str] = None,
        profile: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieve the value of a secret.
        
        Args:
            secret_id: Secret name or ARN
            version_id: Optional specific version ID
            version_stage: Optional version stage (e.g., AWSCURRENT, AWSPREVIOUS)
            role_arn: IAM role ARN to assume for this operation
            region: AWS region (defaults to AWS_REGION)
            profile: AWS profile name from ~/.aws/credentials
            
        Returns:
            Dictionary with secret value and metadata
        """
        try:
            client = self._get_client(role_arn, region, profile)
            
            params = {'SecretId': secret_id}
            
            if version_id:
                params['VersionId'] = version_id
            
            if version_stage:
                params['VersionStage'] = version_stage
            
            response = client.get_secret_value(**params)
            
            # Try to parse as JSON, otherwise return as string
            secret_value = response.get('SecretString')
            is_json = False
            parsed_value = secret_value
            
            if secret_value:
                try:
                    parsed_value = json.loads(secret_value)
                    is_json = True
                except json.JSONDecodeError:
                    pass
            
            return {
                "success": True,
                "secret_name": response['Name'],
                "secret_arn": response['ARN'],
                "secret_value": parsed_value,
                "is_json": is_json,
                "version_id": response.get('VersionId'),
                "version_stages": response.get('VersionStages', []),
                "created_date": response.get('CreatedDate').isoformat() if response.get('CreatedDate') else None
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            return {
                "success": False,
                "error": error_message,
                "error_code": error_code,
                "secret_id": secret_id
            }
    
    async def update_secret(
        self,
        secret_id: str,
        secret_value: str,
        description: Optional[str] = None,
        role_arn: Optional[str] = None,
        region: Optional[str] = None,
        profile: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update an existing secret's value.
        
        Args:
            secret_id: Secret name or ARN
            secret_value: New secret value (string or JSON)
            description: Optional new description
            role_arn: IAM role ARN to assume for this operation
            region: AWS region (defaults to AWS_REGION)
            profile: AWS profile name from ~/.aws/credentials
            
        Returns:
            Dictionary with update status
        """
        try:
            client = self._get_client(role_arn, region, profile)
            
            params = {
                'SecretId': secret_id,
                'SecretString': secret_value
            }
            
            if description:
                params['Description'] = description
            
            response = client.update_secret(**params)
            
            return {
                "success": True,
                "secret_name": response['Name'],
                "secret_arn": response['ARN'],
                "version_id": response.get('VersionId'),
                "region": region or self._get_default_region()
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            return {
                "success": False,
                "error": error_message,
                "error_code": error_code,
                "secret_id": secret_id
            }
    
    async def delete_secret(
        self,
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
            recovery_window_in_days: Days before permanent deletion (7-30)
            force_delete_without_recovery: If True, delete immediately without recovery
            role_arn: IAM role ARN to assume for this operation
            region: AWS region (defaults to AWS_REGION)
            profile: AWS profile name from ~/.aws/credentials
            
        Returns:
            Dictionary with deletion status
        """
        try:
            client = self._get_client(role_arn, region, profile)
            
            params = {'SecretId': secret_id}
            
            if force_delete_without_recovery:
                params['ForceDeleteWithoutRecovery'] = True
            else:
                params['RecoveryWindowInDays'] = recovery_window_in_days
            
            response = client.delete_secret(**params)
            
            return {
                "success": True,
                "secret_name": response['Name'],
                "secret_arn": response['ARN'],
                "deletion_date": response.get('DeletionDate').isoformat() if response.get('DeletionDate') else None,
                "force_deleted": force_delete_without_recovery
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            return {
                "success": False,
                "error": error_message,
                "error_code": error_code,
                "secret_id": secret_id
            }
    
    async def list_secrets(
        self,
        filters: Optional[List[Dict[str, Any]]] = None,
        max_results: int = 500,
        include_planned_deletion: bool = False,
        role_arn: Optional[str] = None,
        region: Optional[str] = None,
        profile: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List secrets in AWS Secrets Manager.
        
        Args:
            filters: Optional filters (e.g., [{"Key": "name", "Values": ["prod/"]}])
            max_results: Maximum number of results to return
            include_planned_deletion: Include secrets scheduled for deletion
            role_arn: IAM role ARN to assume for this operation
            region: AWS region (defaults to AWS_REGION)
            profile: AWS profile name from ~/.aws/credentials
            
        Returns:
            Dictionary with list of secrets
        """
        try:
            client = self._get_client(role_arn, region, profile)
            
            params = {'MaxResults': min(max_results, 100)}
            
            if filters:
                params['Filters'] = filters
            
            if include_planned_deletion:
                params['IncludePlannedDeletion'] = True
            
            secrets = []
            next_token = None
            
            while True:
                if next_token:
                    params['NextToken'] = next_token
                
                response = client.list_secrets(**params)
                
                for secret in response.get('SecretList', []):
                    secrets.append({
                        "name": secret['Name'],
                        "arn": secret['ARN'],
                        "description": secret.get('Description'),
                        "last_changed_date": secret.get('LastChangedDate').isoformat() if secret.get('LastChangedDate') else None,
                        "last_accessed_date": secret.get('LastAccessedDate').isoformat() if secret.get('LastAccessedDate') else None,
                        "tags": {tag['Key']: tag['Value'] for tag in secret.get('Tags', [])},
                        "deletion_date": secret.get('DeletedDate').isoformat() if secret.get('DeletedDate') else None
                    })
                
                next_token = response.get('NextToken')
                
                if not next_token or len(secrets) >= max_results:
                    break
            
            return {
                "success": True,
                "secrets": secrets[:max_results],
                "count": len(secrets[:max_results]),
                "region": region or self._get_default_region()
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            return {
                "success": False,
                "error": error_message,
                "error_code": error_code
            }
    
    async def describe_secret(
        self,
        secret_id: str,
        role_arn: Optional[str] = None,
        region: Optional[str] = None,
        profile: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get metadata about a secret (without the secret value).
        
        Args:
            secret_id: Secret name or ARN
            role_arn: IAM role ARN to assume for this operation
            region: AWS region (defaults to AWS_REGION)
            profile: AWS profile name from ~/.aws/credentials
            
        Returns:
            Dictionary with secret metadata
        """
        try:
            client = self._get_client(role_arn, region, profile)
            
            response = client.describe_secret(SecretId=secret_id)
            
            return {
                "success": True,
                "secret_name": response['Name'],
                "secret_arn": response['ARN'],
                "description": response.get('Description'),
                "kms_key_id": response.get('KmsKeyId'),
                "rotation_enabled": response.get('RotationEnabled', False),
                "rotation_lambda_arn": response.get('RotationLambdaARN'),
                "rotation_rules": response.get('RotationRules'),
                "last_rotated_date": response.get('LastRotatedDate').isoformat() if response.get('LastRotatedDate') else None,
                "last_changed_date": response.get('LastChangedDate').isoformat() if response.get('LastChangedDate') else None,
                "last_accessed_date": response.get('LastAccessedDate').isoformat() if response.get('LastAccessedDate') else None,
                "deleted_date": response.get('DeletedDate').isoformat() if response.get('DeletedDate') else None,
                "tags": {tag['Key']: tag['Value'] for tag in response.get('Tags', [])},
                "version_ids_to_stages": response.get('VersionIdsToStages', {})
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            return {
                "success": False,
                "error": error_message,
                "error_code": error_code,
                "secret_id": secret_id
            }
    
    async def restore_secret(
        self,
        secret_id: str,
        role_arn: Optional[str] = None,
        region: Optional[str] = None,
        profile: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Restore a previously deleted secret.
        
        Args:
            secret_id: Secret name or ARN
            role_arn: IAM role ARN to assume for this operation
            region: AWS region (defaults to AWS_REGION)
            profile: AWS profile name from ~/.aws/credentials
            
        Returns:
            Dictionary with restore status
        """
        try:
            client = self._get_client(role_arn, region, profile)
            
            response = client.restore_secret(SecretId=secret_id)
            
            return {
                "success": True,
                "secret_name": response['Name'],
                "secret_arn": response['ARN'],
                "region": region or self._get_default_region()
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            return {
                "success": False,
                "error": error_message,
                "error_code": error_code,
                "secret_id": secret_id
            }
    
    async def tag_secret(
        self,
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
            tags: Tags as key-value pairs
            role_arn: IAM role ARN to assume for this operation
            region: AWS region (defaults to AWS_REGION)
            profile: AWS profile name from ~/.aws/credentials
            
        Returns:
            Dictionary with tagging status
        """
        try:
            client = self._get_client(role_arn, region, profile)
            
            client.tag_resource(
                SecretId=secret_id,
                Tags=[{'Key': k, 'Value': v} for k, v in tags.items()]
            )
            
            return {
                "success": True,
                "secret_id": secret_id,
                "tags_added": tags
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            return {
                "success": False,
                "error": error_message,
                "error_code": error_code,
                "secret_id": secret_id
            }
    
    async def untag_secret(
        self,
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
            role_arn: IAM role ARN to assume for this operation
            region: AWS region (defaults to AWS_REGION)
            profile: AWS profile name from ~/.aws/credentials
            
        Returns:
            Dictionary with untagging status
        """
        try:
            client = self._get_client(role_arn, region, profile)
            
            client.untag_resource(
                SecretId=secret_id,
                TagKeys=tag_keys
            )
            
            return {
                "success": True,
                "secret_id": secret_id,
                "tags_removed": tag_keys
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            return {
                "success": False,
                "error": error_message,
                "error_code": error_code,
                "secret_id": secret_id
            }
