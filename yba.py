#!/usr/bin/env python3
"""
YugabyteDB Anywhere (YBA)

This module provides functions to simplify the usage of the YugabyteDB Anywhere API.
It's deliberately simplistic to help users see the API request payloads (in JSON template files).

API reference:
https://api-docs.yugabyte.com/docs/yugabyte-platform/f10502c9c9623-yugabyte-db-anywhere-api-overview

Additional examples of using the API:
https://github.com/yugabyte/yugabyte-db/tree/master/managed/api-examples/python-simple

Author: David Roberts
Version: 0.0.2
"""

import json
import requests
import time
import os
import urllib3
import uuid
from string import Template
from typing import Optional, Dict, Any, List

def invoke_yba_request(
    base_url: str,
    endpoint: str,
    api_token: str,
    customer_id: str,
    method: str = "GET",
    payload: Optional[dict[str, Any]] = None,
    params: Optional[dict[str, str]] = None,
    headers: Optional[dict[str, str]] = None,
    verify_certificate: bool = True,
    timeout: int = 30,
    wait_timeout: int = 600,
    wait: bool = False
) -> dict[str, Any]:
    """
    Invokes a request to the YugabyteDB Anywhere REST API.
    Returns the API response or a task, if the request creates a task.
    Optionally waits for task completion before returning.

    Args:
        base_url (str): The base URL of the YugabyteDB Anywhere instance (e.g. 'https://yba.example.com').
        endpoint (str): The API endpoint to call (e.g. '/api/v1/universes').
        api_token (str): API token for authentication.
        method (str): HTTP method to use ('GET', 'POST', 'PUT', 'DELETE'). Defaults to GET.
        customer_id (str): Customer / tenant ID. Required when wait is true.
        payload (Optional[dict]): JSON payload for POST or PUT requests.
        params (Optional[dict]): Query parameters for the request.
        headers (Optional[dict]): Additional headers to include with the request.
        timeout (int): Timeout for any HTTP request in seconds. Defaults to 30 seconds.
        wait (boolean): Whether to poll, up to the timeout period, for task completion. Applies to async API requests which invoke tasks. If false a task ID is returned as soon as it's started. Defaults to true.
        wait_timeout (int): Timeout for overall task completion in seconds. Defaults to 600 seconds (10 minutes).
        verify_certificate (bool): Whether to verify the certificate presented by the YugabyteDB Anywhere instance. Defaults to true.
        customer_id (Optional[str]): Customer ID to retrieve in-flight task if wait is true. 
    Returns:
        dict: Parsed JSON response from the API.

    Raises:
        requests.exceptions.RequestException: For network-related errors.
        ValueError: If the response is not JSON or contains an error.
    """

    # Start time to respect requested timeout period
    start = time.time()

    # Construct the full URL
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    # Set default headers and authentication
    default_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-AUTH-YW-API-TOKEN": api_token
    }

    # Merge any custom headers
    if headers:
        default_headers.update(headers)

    # Suppress warnings if we're accepting invalid certificates
    if not verify_certificate:
        urllib3.disable_warnings()

    try:
        response = requests.request(
            method = method.upper(),
            url = url,
            headers = default_headers,
            json = payload,
            params = params,
            timeout = timeout,
            verify = verify_certificate
        )

        # Raise an exception if error status codes are returned
        response.raise_for_status()

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"API request failed with status {response.status_code} and error {response.json()["error"]}")

    # Try to parse JSON response
    try:
        json_response = response.json()
    except ValueError:
        raise ValueError(f"Expected a JSON-formatted response but received: {response.text}")

    # If we're not waiting (async) or this request didn't trigger a task, return the API response
    if not wait or not 'taskUUID' in json_response or not customer_id:
        return json_response

    # Loop until timeout and poll for the task status
    while time.time() - start < wait_timeout:

        try:
            task_response = requests.request(
                url = f"{base_url.rstrip('/')}/api/v1/customers/{customer_id}/tasks/{json_response["taskUUID"]}",
                method = 'GET',
                headers = default_headers,
                timeout = 1,
                verify = verify_certificate
            )
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"API request for in-flight task failed: {e}")

        try:
            json_task_response = task_response.json()
        except ValueError:
            raise ValueError(f"Expected a JSON-formatted response for in-flight task's status but received: {response.text}")

        # If the invoked task has finished, return the latest task
        if json_task_response['percent'] == 100 or json_task_response['status'] in ['Aborted', 'Failure']:
            return json_task_response

        time.sleep(2) # Poll every two seconds until timeout reached

    # Timed out waiting for an async task to finish, return the latest task
    return json_task_response

def register_yba_instance(
    url: str,
    code: str,
    email: str,
    name: str,
    password: str,
    verify_certificate: bool = True
) -> Dict[str, Any]:
    """
    Registers a newly provisioned YugabyteDB Anywhere instance through its REST API.
    Returns the result of the registration and an API token for further requests.

    Args:
        url (str): The base URL of the YugabyteDB Anywhere instance (e.g. 'https://yba.example.com').
        code (str): The instance's purpose.
        name: Full name of the administrator of the instance.
        email (str): Email address for the administrator of the instance.
        password: Password for the administrator of the instance.
        verify_certificate (bool): Whether to verify the certificate presented by the YugabyteDB Anywhere instance. Defaults to true.
    Returns:
        dict: Parsed JSON response from the API.

    Raises:
        requests.exceptions.RequestException: For network-related errors.
        ValueError: If the response is not JSON or contains an error.
    """

     # Construct the full URL
    url = f"{url.rstrip('/')}/api/v1/register"

    # Set headers
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    # Suppress warnings if we're accepting invalid certificates
    if not verify_certificate:
        urllib3.disable_warnings()

    payload = {
        "code": code,
        "name": name,
        "email": email,
        "password": password
    }

    try:
        response = requests.request(
            method = 'POST',
            url = url,
            headers = headers,
            json = payload,
            params = {'generateApiToken': 1},
            timeout = 30,
            verify = verify_certificate
        )

        # Raise an exception if error status codes are returned
        response.raise_for_status()

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Registration failed with status {response.status_code} and error {response.json()["error"]}")

    # Try to parse JSON response
    try:
        response = response.json()
    except ValueError:
        raise ValueError(f"Expected a JSON-formatted response but received: {response.text}")

    return response

def login_yba_instance(
    url: str,
    email: str,
    password: str,
    verify_certificate: bool = True
) -> dict[str, Any]:
    """
    Logs in to a YugabyteDB Anywhere instance through its REST API.
    Returns the result of the login with an API token for further requests.

    Args:
        url (str): The base URL of the YugabyteDB Anywhere instance (e.g. 'https://yba.example.com').
        email (str): Email address / user name for an administrator of the instance.
        password: Password for an administrator of the instance.
        verify_certificate (bool): Whether to verify the certificate presented by the YugabyteDB Anywhere instance. Defaults to true.
    Returns:
        dict: Parsed JSON response from the API.

    Raises:
        requests.exceptions.RequestException: For network-related errors.
        ValueError: If the response is not JSON or contains an error.
    """

     # Construct the full URL
    url = f"{url.rstrip('/')}/api/v1/api_login"

    # Set headers
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    # Suppress warnings if we're accepting invalid certificates
    if not verify_certificate:
        urllib3.disable_warnings()

    payload = {'email': email, 'password': password}

    try:
        response = requests.request(
            method = 'POST',
            url = url,
            headers = headers,
            json = payload,
            timeout = 30,
            verify = verify_certificate
        )

        # Raise an exception if error status codes are returned
        response.raise_for_status()

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Registration failed with status {response.status_code} and error {response.json()["error"]}")

    # Try to parse JSON response
    try:
        response = response.json()
    except ValueError:
        raise ValueError(f"Expected a JSON-formatted response but received: {response.text}")

    return response

def create_yba_provider_kubernetes(
    url: str,
    api_token: str,
    customer_id: str,
    params: dict,
    use_suggested: bool = True,
    template_file: str = f"{os.path.dirname(__file__)}/templates/provider_k8s.json",
    verify_certificate: bool = True
) -> dict[str, Any]:
    """
    Creates a provider for the Kubernetes cluster on which a YugabyteDB Anywhere instance resides.
    Optionally use the automatically retrieved information about the Kubernetes cluster hosting the YBA instance to populate some configuration settings.
    Returns the provider creation task.

    Args:
        url (str): The base URL of the YugabyteDB Anywhere instance (e.g. 'https://yba.example.com').
        api_token (str): API token for authentication.
        customer_id (str): Customer / tenant ID.
        params (dict): Dictionary of values to be interpolated into the provider creation template.
        use_suggested (bool): Whether to use the auto-fill Kubernetes settings retrieved from the cluster hosting the YBA instance. Defaults to faise.
        template_file (str): Path to a JSON file holding the API request payload with $-prefixed variable names from the params dictionary for interpolation.
        verify_certificate (bool): Whether to verify the certificate presented by the YugabyteDB Anywhere instance. Defaults to true.
    Returns:
        dict: Parsed JSON response from the API.

    Raises:
        requests.exceptions.RequestException: For network-related errors.
        ValueError: If the response is not JSON or contains an error.
    """

    # Construct common arguments for API invocations
    invoke_yba_request_args = {
        'base_url': url,
        'api_token': api_token,
        'customer_id': customer_id,
        'verify_certificate': verify_certificate
    }

    if use_suggested:
        try:
            suggested_config = invoke_yba_request(
                **invoke_yba_request_args,
                endpoint = f"/api/v1/customers/{customer_id}/providers/suggested_kubernetes_config"
            )
            # Populate parameters with values from the suggested (local) Kubernetes cluster
            params.update({'code': suggested_config['code']})
            params.update({'name': suggested_config['name']})
            params.update({'image_registry': suggested_config['config']['KUBECONFIG_IMAGE_REGISTRY']})
            params.update({'cloud_provider': suggested_config['config']['KUBECONFIG_PROVIDER'].lower()})
            params.update({'pull_secret': suggested_config['config']['KUBECONFIG_PULL_SECRET_CONTENT'].replace('"', '\\"')}) # Escape quotes within the secret data
            params.update({'pull_secret_name': suggested_config['config']['KUBECONFIG_IMAGE_PULL_SECRET_NAME']})
            params.update({'region_code': suggested_config['regionList'][0]['code']})
            params.update({'region_name': suggested_config['regionList'][0]['name']})
            params.update({'zone_code': suggested_config['regionList'][0]['zoneList'][0]['code']})
            params.update({'zone_name': suggested_config['regionList'][0]['zoneList'][0]['name']})
        except requests.exceptions.RequestException as e:
            print(f"Unable to retrieve suggested Kubernetes provider configuration. It is likely that YBA is not running on Kubernetes or its service account doesn't have appropriate permissions to the Kubernetes API.")            

    with open(template_file, 'r') as json_file:
        template = Template(json_file.read())
        provider_payload = template.substitute(params)

    provider_payload = json.loads(provider_payload.replace('\n', ''))

    # Create a provider
    provider_task = invoke_yba_request(
        **invoke_yba_request_args,
        endpoint = f"/api/v1/customers/{customer_id}/providers",
        method = 'POST',
        payload = provider_payload, 
        wait = True
    )

    return provider_task

def create_yba_provider(
    url: str,
    api_token: str,
    customer_id: str,
    params: dict,
    template_file: str = f"{os.path.dirname(__file__)}/templates/provider_aws_iam_ybimage.json",
    verify_certificate: bool = True
) -> dict[str, Any]:
    """
    Creates a provider for a public cloud using the variables specified provided in params with the JSON template specified in template_file.
    Returns the provider creation task.

    Args:
        url (str): The base URL of the YugabyteDB Anywhere instance (e.g. 'https://yba.example.com').
        api_token (str): API token for authentication.
        customer_id (str): Customer / tenant ID.
        params (dict): Dictionary of values to be interpolated into the provider creation template.
        template_file (str): Path to a JSON file holding the API request payload with $-prefixed variable names from the params dictionary for interpolation.
        verify_certificate (bool): Whether to verify the certificate presented by the YugabyteDB Anywhere instance. Defaults to true.
    Returns:
        dict: Parsed JSON response from the API.

    Raises:
        requests.exceptions.RequestException: For network-related errors.
        ValueError: If the response is not JSON or contains an error.
    """

    # Construct common arguments for API invocations
    invoke_yba_request_args = {
        'base_url': url,
        'api_token': api_token,
        'customer_id': customer_id,
        'verify_certificate': verify_certificate
    }

    with open(template_file, 'r') as json_file:
        template = Template(json_file.read())
        provider_payload = template.substitute(params)

    provider_payload = json.loads(provider_payload.replace('\n', ''))

    # Create a provider
    provider_task = invoke_yba_request(
        **invoke_yba_request_args,
        endpoint = f"/api/v1/customers/{customer_id}/providers",
        method = 'POST',
        payload = provider_payload, 
        wait = True
    )

    return provider_task

def create_yba_backup_storage_aws(
    url: str,
    api_token: str,
    customer_id: str,
    configuration_name: str,
    bucket_name: str,
    access_key_id: Optional[str] = None,
    access_key_secret: Optional[str] = None,
    verify_certificate: bool = True
) -> dict[str, Any]:
    """
    Creates an AWS S3 backup storage location for YugabyteDB backups.
    Returns the created configuration.

    Args:
        url (str): The base URL of the YugabyteDB Anywhere instance (e.g. 'https://yba.example.com').
        api_token (str): API token for authentication.
        customer_id (str): Customer / tenant ID.
        configuration_name (str): Name for the configuration in the YBA user interface
        bucket_name (str): Name of the S3 bucket to contain backups, without any prefix or domain name
        access_key_id (str): AWS service account access key with permission to use the S3 bucket. Defaults to using an EC2 IAM role.
        access_key_secret (str): AWS service account access key secret. Defaults to using an EC2 IAM role.
        verify_certificate (bool): Whether to verify the certificate presented by the YugabyteDB Anywhere instance. Defaults to true.
    Returns:
        dict: Parsed JSON response from the API.

    Raises:
        requests.exceptions.RequestException: For network-related errors.
        ValueError: If the response is not JSON or contains an error.
    """

    params = {
        'configuration_name': configuration_name,
        'bucket_name': bucket_name
    }

    if access_key_id and access_key_secret:
        template_file = f"{os.path.dirname(__file__)}/templates/backup_storage_aws_key.json"
        params.update({'access_key_id': access_key_id})
        params.update({'access_key_secret': access_key_secret})
    else:
        template_file = f"{os.path.dirname(__file__)}/templates/backup_storage_aws_iam.json"

    with open(template_file, 'r') as json_file:
        template = Template(json_file.read())
        payload = template.substitute(params)

    payload = json.loads(payload.replace('\n', ''))

    # Create and return a configured backup location
    return invoke_yba_request(
        base_url = url,
        api_token = api_token,
        customer_id = customer_id,
        verify_certificate = verify_certificate,
        endpoint = f"/api/v1/customers/{customer_id}/configs",
        method = 'POST',
        payload = payload
    )

def create_yba_backup_storage_gcp(
    url: str,
    api_token: str,
    customer_id: str,
    configuration_name: str,
    bucket_name: str,
    access_key_secret_json: Optional[str] = None,
    verify_certificate: bool = True
) -> dict[str, Any]:
    """
    Creates an AWS S3 backup storage location for YugabyteDB backups.
    Returns the created configuration.

    Args:
        url (str): The base URL of the YugabyteDB Anywhere instance (e.g. 'https://yba.example.com').
        api_token (str): API token for authentication.
        customer_id (str): Customer / tenant ID.
        configuration_name (str): Name for the configuration in the YBA user interface.
        bucket_name (str): Name of the storage bucket to contain backups, without any prefix or domain name
        access_key_secret_json (str): GCP service account access key in JSON format with permission to use the storage bucket.
        verify_certificate (bool): Whether to verify the certificate presented by the YugabyteDB Anywhere instance. Defaults to true.
    Returns:
        dict: Parsed JSON response from the API.

    Raises:
        requests.exceptions.RequestException: For network-related errors.
        ValueError: If the response is not JSON or contains an error.
    """

    params = {
        'configuration_name': configuration_name,
        'bucket_name': bucket_name
    }

    if access_key_secret_json:
        template_file = f"{os.path.dirname(__file__)}/templates/backup_storage_gcp_key.json"
        params.update({'access_key_secret_json': access_key_secret_json})

    with open(template_file, 'r') as json_file:
        template = Template(json_file.read())
        payload = template.substitute(params)

    payload = json.loads(payload.replace('\n', ''))

    # Create and return a configured backup location
    return invoke_yba_request(
        base_url = url,
        api_token = api_token,
        customer_id = customer_id,
        verify_certificate = verify_certificate,
        endpoint = f"/api/v1/customers/{customer_id}/configs",
        method = 'POST',
        payload = payload
    )

def create_yba_release(
    url: str,
    api_token: str,
    customer_id: str,
    package_url: str,
    verify_certificate: bool = True
) -> dict[str, Any]:
    """
    Creates a YugabyteDB release in YugabyteDB Anywhere from which universes can be deployed.
    Returns the created configuration.

    Args:
        url (str): The base URL of the YugabyteDB Anywhere instance (e.g. 'https://yba.example.com').
        api_token (str): API token for authentication.
        customer_id (str): Customer / tenant ID.
        package_url (str): URL to the release package (x86 or ARM) or Helm chart.
        verify_certificate (bool): Whether to verify the certificate presented by the YugabyteDB Anywhere instance. Defaults to true.
    Returns:
        dict: Parsed JSON response from the API.

    Raises:
        requests.exceptions.RequestException: For network-related errors.
        ValueError: If the response is not JSON or contains an error.
    """

    # Construct common arguments for API invocations
    invoke_yba_request_args = {
        'base_url': url,
        'api_token': api_token,
        'customer_id': customer_id,
        'verify_certificate': verify_certificate
    }

    # First try to retrieve metadata for the package, which we use to construct the release creation request
    metadata = invoke_yba_request(
        **invoke_yba_request_args,
        endpoint = f"/api/v1/customers/{customer_id}/ybdb_release/extract_metadata",
        method = 'POST',
        payload = {"url": package_url}
    )

    # The API first returns resourceUUID, then when you query for that resource it will return a status 
    # field which should move to 'success' when the metadata is retrieved
    if (not 'resourceUUID' in metadata):
        raise ValueError(f"Unable to retrieve metadata for URL {package_url}. API response: {metadata}")

    metadata_id = metadata['resourceUUID']

    # Poll until the metadata is collected
    # This doesn't use the task management of YBA, so the Wait option of invoke_yba_request won't work
    start = time.time()
    while (time.time() - start < 30) and (not 'status' in metadata or metadata['status'] == 'running'):

        try:
            metadata = requests.request(
                url = f"{url.rstrip('/')}/api/v1/customers/{customer_id}/ybdb_release/extract_metadata/{metadata_id}",
                method = 'GET',
                headers = { "Content-Type": "application/json", "X-AUTH-YW-API-TOKEN": api_token},
                timeout = 1,
                verify = verify_certificate
            )
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"API request for package metadata retrieval progress failed: {e}")
        
        metadata = metadata.json()
        
        time.sleep(1) # Poll every second until timeout reached

    if (not 'version' in metadata):
        raise ValueError(f"Failed to retrieve metadata for URL {package_url}. API response: {metadata.text}")

    # Check for an existing release for this package - if so we need to add the package / architecture to an
    # existing release
    releases = invoke_yba_request(
        **invoke_yba_request_args,
        endpoint = f"/api/v1/customers/{customer_id}/ybdb_release",
        method = 'GET'
    )

    # Select a matching existing release
    release = next((release for release in releases if release['version'] == metadata['version']), None)

    if release is None:

        # Construct a new release request
        params = {
            'version': metadata['version'],
            'yb_type': metadata['yb_type'],
            'platform': metadata['platform'],
            'architecture': metadata['architecture'],
            'package_url': package_url,
            'release_type': metadata['release_type'],
            'release_date_msecs': metadata['release_date_msecs']
        }

        template_file = f"{os.path.dirname(__file__)}/templates/release.json"

        with open(template_file, 'r') as json_file:
            template = Template(json_file.read())
            payload = template.substitute(params)

        payload = json.loads(payload.replace('\n', ''))

        # Create and return a new release
        return invoke_yba_request(
            base_url = url,
            api_token = api_token,
            customer_id = customer_id,
            verify_certificate = verify_certificate,
            endpoint = f"/api/v1/customers/{customer_id}/ybdb_release",
            method = 'POST',
            payload = payload
        )

    else:

        # Select a matching package from an existing release
        package = next((package for package in release['artifacts'] if package['architecture'] == metadata['architecture']), None)

        if package is not None:
            return release # Package is already present in YBA, return its existing release

        else:

            # Add the new package to an existing release
            architecture = {
                'package_url': package_url,
                'platform': metadata['platform'],
                'architecture': metadata['architecture']
            }

            release["artifacts"].append(architecture)

            # Update the existing release
            return invoke_yba_request(
                base_url = url,
                api_token = api_token,
                customer_id = customer_id,
                verify_certificate = verify_certificate,
                endpoint = f"/api/v1/customers/{customer_id}/ybdb_release/{release['release_uuid']}",
                method = 'PUT',
                payload = release
            )
   
def create_yba_universe(
    url: str,
    api_token: str,
    customer_id: str,
    params: dict,
    template_file: str = f"{os.path.dirname(__file__)}/templates/universe_k8s_1az.json",
    verify_certificate: bool = True
) -> dict[str, Any]:
    """
    Creates a universe in a YugabyteDB Anywhere instance.
    Returns the universe creation task.

    Args:
        url (str): The base URL of the YugabyteDB Anywhere instance (e.g. 'https://yba.example.com').
        api_token (str): API token for authentication.
        customer_id (str): Customer / tenant ID.
        params (dict): Dictionary of values to be interpolated into the universe creation template.
        template_file (str): Path to a JSON file holding the API request payload with $-prefixed variable names from the params dictionary for interpolation.
        verify_certificate (bool): Whether to verify the certificate presented by the YugabyteDB Anywhere instance. Defaults to true.
    Returns:
        dict: Parsed JSON response from the API.

    Raises:
        requests.exceptions.RequestException: For network-related errors.
        ValueError: If the response is not JSON or contains an error.
    """

    # Construct common arguments for API invocations
    invoke_yba_request_args = {
        'base_url': url,
        'api_token': api_token,
        'customer_id': customer_id,
        'verify_certificate': verify_certificate
    }

    # Interpolate provided parameters into the request body
    with open(template_file, 'r') as json_file:
        template = Template(json_file.read())
        universe_payload = template.substitute(params)

    universe_payload = json.loads(universe_payload.replace('\n', ''))

    # Create a universe
    universe_task = invoke_yba_request(
        **invoke_yba_request_args,
        endpoint = f"/api/v2/customers/{customer_id}/providers",
        method = 'POST',
        payload = universe_payload, 
        wait = True
    )

    return universe_task


    """
    Transform nodeDetailsSet object in universe definition to the format required for universe creation.
    
    Args:
        source_nodes: List of node details from the source universe
        
    Returns:
        List of transformed node details to be used to create a new universe
    """
    target_nodes = []
    
    for node in source_nodes:
        target_node = {
            "nodeIdx": node.get("nodeIdx"),
            "cloudInfo": node.get("cloudInfo", {}),
            "azUuid": node.get("azUuid"),
            "placementUuid": node.get("placementUuid"),
            "disksAreMountedByUUID": node.get("disksAreMountedByUUID"),
            "ybPrebuiltAmi": node.get("ybPrebuiltAmi"),
            "autoSyncMasterAddrs": node.get("autoSyncMasterAddrs"),
            "state": node.get("state"),
            "isMaster": node.get("isMaster"),
            "masterHttpPort": node.get("masterHttpPort"),
            "masterRpcPort": node.get("masterRpcPort"),
            "isTserver": node.get("isTserver"),
            "tserverHttpPort": node.get("tserverHttpPort"),
            "tserverRpcPort": node.get("tserverRpcPort"),
            "ybControllerHttpPort": node.get("ybControllerHttpPort"),
            "ybControllerRpcPort": node.get("ybControllerRpcPort"),
            "isRedisServer": node.get("isRedisServer"),
            "redisServerHttpPort": node.get("redisServerHttpPort"),
            "redisServerRpcPort": node.get("redisServerRpcPort"),
            "isYqlServer": node.get("isYqlServer"),
            "yqlServerHttpPort": node.get("yqlServerHttpPort"),
            "yqlServerRpcPort": node.get("yqlServerRpcPort"),
            "isYsqlServer": node.get("isYsqlServer"),
            "ysqlServerHttpPort": node.get("ysqlServerHttpPort"),
            "ysqlServerRpcPort": node.get("ysqlServerRpcPort"),
            "internalYsqlServerRpcPort": node.get("internalYsqlServerRpcPort"),
            "nodeExporterPort": node.get("nodeExporterPort"),
            "otelCollectorMetricsPort": node.get("otelCollectorMetricsPort"),
            "cronsActive": node.get("cronsActive"),
            "dedicatedTo": node.get("dedicatedTo")
        }
        
        # Add masterState if present (only for master nodes)
        if node.get("masterState"):
            target_node["masterState"] = node.get("masterState")
        
        target_nodes.append(target_node)
    
    return target_nodes

def replicate_yba_kubernetes_universe(
    url: str,
    api_token: str,
    customer_id: str,
    source_name: str,
    name: str,
    ycql_password: str = 'Yuga_123',
    ysql_password: str = 'Yuga_123',
    tserver_cpus: Optional[int] = None,
    tserver_memory: Optional[int] = None,
    master_cpus: Optional[int] = None,
    master_memory: Optional[int] = None,
    tserver_storage: Optional[int] = None,
    what_if: bool = False,
    verify_certificate: bool = True
) -> dict[str, Any]:
    """
    Creates a Kubernetes or OpenShift universe with the same configuration as another in a YugabyteDB Anywhere instance.
    Returns the universe creation task. Does not replicate schema or data between the universes.
    Overrides can be used to set any exceptions, including the YCQL and YSQL password (which otherwise default to Yuga_123).

    Args:
        url (str): The base URL of the YugabyteDB Anywhere instance (e.g. 'https://yba.example.com').
        api_token (str): API token for authentication.
        customer_id (str): Customer / tenant ID.
        source_name (str): Name of the universe to replicate.
        name (str): Name of the universe to create.
        ycql_password (str): Password for the default YCQL administrative user. Defaults to yugabyte.
        ysql_password (str): Password for the default YCQL administrative user. Defaults to yugabyte.
        tserver_cpus (int): Number of CPUs to assign to each tablet server node. Defaults to the same as the source universe.
        master_cpus (int): Number of CPUs to assign to each master node. Defaults to the same as the source universe.
        tserver_memory (int): Memory in gigabytes to assign to each tablet server node. Defaults to the same as the source universe.
        master_memory (int): Memory in gigabytes to assign to each master node. Defaults to the same as the source universe.
        tserver_storage (int): Storage in gigabytes to assign to each tablet server node. Defaults to the same as the source universe.
        what_if (bool): Whether to return the JSON payload for universe creation rather than actually invoking the creation. Defaults to false.
        verify_certificate (bool): Whether to verify the certificate presented by the YugabyteDB Anywhere instance. Defaults to true.
    Returns:
        dict: Parsed JSON response from the API.

    Raises:
        requests.exceptions.RequestException: For network-related errors.
        ValueError: If the response is not JSON or contains an error.
    """

    # Retrieve the source universe from YBA
    invoke_yba_request_args = {
        'base_url': url,
        'api_token': api_token,
        'customer_id': customer_id,
        'verify_certificate': verify_certificate
    }
    source_universe_id = invoke_yba_request(
        **invoke_yba_request_args,
        endpoint = f"/api/v1/customers/{customer_id}/universes/find?name={source_name}"
    )
    if len(source_universe_id) != 1:
        raise RuntimeError(f"Unable to find an existing source universe named {source_name}")
    source_universe = invoke_yba_request(
        **invoke_yba_request_args,
        endpoint = f"/api/v1/customers/{customer_id}/universes/{source_universe_id[0]}"
    )

    # Check the new universe doesn't already exist
    destination_universe = invoke_yba_request(
        **invoke_yba_request_args,
        endpoint = f"/api/v1/customers/{customer_id}/universes/find?name={name}"
    )
    if destination_universe:
        raise RuntimeError(f"A universe named {name} already exists")

    # Extract universe details
    source_universe = source_universe['universeDetails']

    # Generate a UUID for the new universe
    universe_id = str(uuid.uuid4())
    
    # Build the universe creation payload from the source universe
    configure_universe = {
        "platformVersion": source_universe.get("platformVersion"),
        "sleepAfterMasterRestartMillis": source_universe.get("sleepAfterMasterRestartMillis"),
        "sleepAfterTServerRestartMillis": source_universe.get("sleepAfterTServerRestartMillis"),
        "nodeExporterUser": source_universe.get("nodeExporterUser"),
        "universeUUID": universe_id,
        "enableYbc": source_universe.get("enableYbc"),
        "installYbc": source_universe.get("installYbc"),
        "ybcInstalled": False, # Default value for a new universe
        "expectedUniverseVersion": source_universe.get("expectedUniverseVersion"),
        
        # Transform encryptionAtRestConfig - the source has a different structure
        "encryptionAtRestConfig": {
            "encryptionAtRestEnabled": source_universe.get("encryptionAtRestConfig", {}).get("encryptionAtRestEnabled", "UNDEFINED")
        },
        
        # Generate nodeDetailsSet based on the source nodeDetailsSet
        "nodeDetailsSet": _replicate_yba_kubernetes_universe_node_details(source_universe.get("nodeDetailsSet", [])),
        
        # Copy communicationPorts directly as it has the same structure
        "communicationPorts": source_universe.get("communicationPorts", {}),
        
        # Copy extraDependencies directly
        "extraDependencies": source_universe.get("extraDependencies", {}),
        
        # Copy creatingUser directly
        "creatingUser": source_universe.get("creatingUser", {}),
        
        "platformUrl": source_universe.get("platformUrl"),
        
        # Copy clusters directly as they have the same structure, then update some specifics
        "clusters": source_universe.get("clusters", []),
        
        "currentClusterType": source_universe.get("currentClusterType"),
        "nodePrefix": source_universe.get("nodePrefix").removesuffix(source_name) + name,
        "rootAndClientRootCASame": source_universe.get("rootAndClientRootCASame"),
        "userAZSelected": source_universe.get("userAZSelected"),
        "resetAZConfig": source_universe.get("resetAZConfig"),
        "updateInProgress": source_universe.get("updateInProgress"),
        "updateSucceeded": source_universe.get("updateSucceeded"),
        "universePaused": source_universe.get("universePaused"),
        "softwareUpgradeState": source_universe.get("softwareUpgradeState"),
        "isSoftwareRollbackAllowed": source_universe.get("isSoftwareRollbackAllowed"),
        "nextClusterIndex": source_universe.get("nextClusterIndex"),
        "allowInsecure": source_universe.get("allowInsecure"),
        "setTxnTableWaitCountFlag": source_universe.get("setTxnTableWaitCountFlag"),
        "itestS3PackagePath": source_universe.get("itestS3PackagePath"),
        "remotePackagePath": source_universe.get("remotePackagePath"),
        "nodesResizeAvailable": source_universe.get("nodesResizeAvailable"),
        "useNewHelmNamingStyle": source_universe.get("useNewHelmNamingStyle"),
        "mastersInDefaultRegion": source_universe.get("mastersInDefaultRegion"),
        "isKubernetesOperatorControlled": source_universe.get("isKubernetesOperatorControlled"),
        "overridePrebuiltAmiDBVersion": source_universe.get("overridePrebuiltAmiDBVersion"),
        "sequenceNumber": -1, # Default value for a new universe
        "importedState": source_universe.get("importedState"),
        "capability": source_universe.get("capability"),
        "updateOptions": source_universe.get("updateOptions"),
        "otelCollectorEnabled": source_universe.get("otelCollectorEnabled"),
        "skipMatchWithUserIntent": source_universe.get("skipMatchWithUserIntent"),
        "installNodeAgent": source_universe.get("installNodeAgent"),
        "clusterOperation": "CREATE", # Default value for a new universe
        "allowGeoPartitioning": False, # Default value for a new universe
        "regionsChanged": False, # Default value
        "xclusterInfo": source_universe.get("xclusterInfo", {}),
        "targetXClusterConfigs": source_universe.get("targetXClusterConfigs", []),
        "sourceXClusterConfigs": source_universe.get("sourceXClusterConfigs", [])
    }
    
    # Add CAs if present (they won't be if the universe is using self-signed certificates or not enabling TLS
    if source_universe.get('rootCA'):
        configure_universe['rootCA'] = source_universe.get('rootCA')
    if source_universe.get('clientRootCA'):
        configure_universe['clientRootCA'] = source_universe.get("clientRootCA")

    for cluster in configure_universe['clusters']:
        # Replace the name in the replicated clusters blocks
        cluster['userIntent']['universeName'] = name
        # Replace the passwords for the cluster
        cluster['userIntent']['ycqlPassword'] = ycql_password
        cluster['userIntent']['ysqlPassword'] = ysql_password
        # Update required specification if overridden
        if tserver_cpus:
            cluster['userIntent']['tserverK8SNodeResourceSpec']['cpuCoreCount'] = tserver_cpus
        if tserver_memory:
            cluster['userIntent']['tserverK8SNodeResourceSpec']['memoryGib'] = tserver_memory
        if tserver_storage:
            cluster['userIntent']['deviceInfo']['volumeSize'] = tserver_storage
        # Replica clusters don't necessarily have masters
        if master_cpus and 'masterK8SNodeResourceSpec' in cluster['userIntent']:
            cluster['userIntent']['masterK8SNodeResourceSpec']['cpuCoreCount'] = master_cpus
        if master_memory and 'masterK8SNodeResourceSpec' in cluster['userIntent']:
            cluster['userIntent']['masterK8SNodeResourceSpec']['memoryGib'] = master_memory

    # Remove xCluster certificate path from its block
    del configure_universe['xclusterInfo']['sourceRootCertDirPath']

    # Compose a new universe with the required specification
    configured_universe = invoke_yba_request(
        **invoke_yba_request_args,
        endpoint = f"/api/v1/customers/{customer_id}/universe_configure",
        method = 'POST',
        payload = configure_universe
    )

    for cluster in configured_universe['clusters']:
        # Put the passwords back in as they are redacted fromt he previous response
        cluster['userIntent']['ycqlPassword'] = ycql_password
        cluster['userIntent']['ysqlPassword'] = ysql_password

    if what_if:
        return json.dumps(configured_universe)
    else:
        # Create a new universe with the fully-specified definition returned from YBA
        return invoke_yba_request(
            **invoke_yba_request_args,
            endpoint = f"/api/v1/customers/{customer_id}/universes",
            method = 'POST',
            payload = configured_universe,
            wait = True
        )

def _replicate_yba_kubernetes_universe_node_details(source_nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Transform nodeDetailsSet object in universe definition to the format required for universe creation.
    
    Args:
        source_nodes: List of node details from the source universe
        
    Returns:
        List of transformed node details to be used to create a new universe
    """
    target_nodes = []
    
    for node in source_nodes:
        target_node = {
            "nodeIdx": node.get("nodeIdx"),
            "cloudInfo": node.get("cloudInfo", {}),
            "azUuid": node.get("azUuid"),
            "placementUuid": node.get("placementUuid"),
            "disksAreMountedByUUID": node.get("disksAreMountedByUUID"),
            "ybPrebuiltAmi": node.get("ybPrebuiltAmi"),
            "autoSyncMasterAddrs": node.get("autoSyncMasterAddrs"),
            "state": 'ToBeAdded', # Default for new universes
            "isMaster": node.get("isMaster"),
            "masterHttpPort": node.get("masterHttpPort"),
            "masterRpcPort": node.get("masterRpcPort"),
            "isTserver": node.get("isTserver"),
            "tserverHttpPort": node.get("tserverHttpPort"),
            "tserverRpcPort": node.get("tserverRpcPort"),
            "ybControllerHttpPort": node.get("ybControllerHttpPort"),
            "ybControllerRpcPort": node.get("ybControllerRpcPort"),
            "redisServerHttpPort": node.get("redisServerHttpPort"),
            "redisServerRpcPort": node.get("redisServerRpcPort"),
            "isYqlServer": node.get("isYqlServer"),
            "yqlServerHttpPort": node.get("yqlServerHttpPort"),
            "yqlServerRpcPort": node.get("yqlServerRpcPort"),
            "isYsqlServer": node.get("isYsqlServer"),
            "ysqlServerHttpPort": node.get("ysqlServerHttpPort"),
            "ysqlServerRpcPort": node.get("ysqlServerRpcPort"),
            "internalYsqlServerRpcPort": node.get("internalYsqlServerRpcPort"),
            "nodeExporterPort": node.get("nodeExporterPort"),
            "otelCollectorMetricsPort": node.get("otelCollectorMetricsPort"),
            "cronsActive": node.get("cronsActive"),
            "dedicatedTo": node.get("dedicatedTo")
        }
        
        # Remove some specific node info that should not be preset for a universe not yet created
        if 'kubernetesPodName' in target_node['cloudInfo']:
            del target_node['cloudInfo']['kubernetesPodName']
        if 'kubernetesNamespace' in target_node['cloudInfo']:
            del target_node['cloudInfo']['kubernetesNamespace']
        if 'private_ip' in target_node['cloudInfo']:
            del target_node['cloudInfo']['private_ip']

        # Add masterState if present (only for master nodes)
        if node.get('isMaster'):
            target_node['masterState'] = 'ToStart' # Default for new universes
            target_node['isRedisServer'] = True # Default for new universes,
            target_node['dedicatedTo'] = 'MASTER'
        
        target_nodes.append(target_node)
    
    return target_nodes