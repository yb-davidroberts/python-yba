# Overview

This repository includes a Python module with functions to help use the YugabyteDB Anywhere REST API.

The API endpoints are documented [here](https://api-docs.yugabyte.com/docs/yugabyte-platform/f10502c9c9623-yugabyte-db-anywhere-api-overview). Please note that there are v1 and v2 endpoints, with v2 under development. Most functionality is available in v1 only. There are examples of using the v1 endpoints with Python [here](https://api-docs.yugabyte.com/docs/yugabyte-platform/f10502c9c9623-yugabyte-db-anywhere-api-overview).

The module is intentionally simple to allow the API request payloads to be easily seen or updated. They are stored as JSON in template files and variables are substituted to generate a valid configuration. In future the templating could be moved to Jinja to allow more dynamic payloads to be created, but this is at the cost of readability.

# Infrastructure as Code

A typical pattern for working with YugabyteDB Anywhere (YBA) might be:

1. Provision a YugabyteDB Anywhere instance
   - [On a virtual machine](https://docs.yugabyte.com/preview/yugabyte-platform/install-yugabyte-platform/install-software/installer/#quick-start) with cloud-init
   - [On Kubernetes](https://docs.yugabyte.com/preview/yugabyte-platform/install-yugabyte-platform/install-software/kubernetes/#install-yugabytedb-anywhere) with Helm

2. Register the newly provisioned instance to generate a tenant / customer and an administrative user. This can be done with the API (or this Python module)

3. Authenticate with the instance to retrieve an API token.

4. Create, read, update or delete configurations with the API (or this Python module)
   - Cloud, Kubernetes or on-prem (server) providers
   - Backup locations
   - YugabyteDB software releases

# Function

## Registering YugabyteDB Anywhere

When initially provisioned the YBA instance allows unauthenticated connection to generate a customer / tenant and administrative user. Visiting its website will automatically redirect to the registration page. 

### register_yba_instance

This function can programmatically register a new YBA instance.

```
url = 'https://<FQDN or IP address>'
name = '<full name>'
email = '<email address>'
password = '<password>'
verify_certificate = False

registration = register_yba_instance(
    url = url,
    code = 'dev',
    email = email,
    name = name,
    password = password,
    verify_certificate = verify_certificate
)
```

It will return registration information, including the unique identifier for the new tenant and `apiToken` to authenticate further API requests.

```
{
    "authToken":"d245b12634cab4fbcf458f6b1f1adabb",
    "apiToken": "3.4c436a54-8d65-459e-abf0-36924461a62ab.69e6ef9d-37f3-4388-02ac-42252afb4eab", 
    "apiTokenVersion":1,
    "customerUUID":"fdea5272-081e-4d84-a998-5bd6e140b931",
    "userUUID":"4c536a54-8d65-459e-abf0-3661461a62ab"
}
```

## Using the API

### login_yba_instance

Although the API token generated at registration does not expire it can also be retrieved with a login request to the API. This uses the email address and password supplied during registration.

```
login = login_yba_instance(
    url = 'https://<FQDN or IP address>',
    email = '<email address>',
    password = '<password>',
    verify_certificate = verify_certificate
)
```

It will return login information, as a dictionary, which we will refer to in further examples.

```
{
    'apiToken': '3.4c436a54-8d65-459e-abf0-36924461a62ab.69e6ef9d-37f3-4388-02ac-42252afb4eab', 
    'apiTokenVersion': 2,
    'customerUUID': 'fdea5272-081e-4d84-a998-5bd6e140b931',
    'userUUID': '4c536a54-8d65-459e-abf0-3661461a62ab'
}
```

### invoke_yba_request

This is a wrapper for most API requests which sets up headers for authentication and can optionally poll (up to a timeout) for task completion if the submitted request starts one. By default the `wait` parameter is false and the function will run asynchronously.

This example also shows setting up some of the common parameters used by function in the module so they can be splatted (expanded from a dictionary to separate arguments) in future calls. This helps keep further examples concise.

The API token and customer (tenant) ID are taken from the earlier login response.

```
invoke_yba_request_args = {
    'base_url': 'https://<FQDN or IP address>',
    'api_token': login['apiToken'],
    'customer_id': login['customerUUID'],
    'verify_certificate': false
}

universes = invoke_yba_request(
    **invoke_yba_request_args,
    endpoint = f"/api/v1/customers/{login['customerUUID']}/universes"
)
```

As an example the returned universe may look like this:

```
[
  {
    "uuid": "3e5ee188-731a-46c7-a891-01119b326c2e",
    "code": "aws",
    "name": "universe-abc",
    "active": "true",
    "customerUUID": "0e7112ac-3a12-4419-ad62-087979610ab0",
    "config": {},
    "details": {
      "sshUser": "ec2-user",
      "sshPort": 22,
      "airGapInstall": "false",
      "passwordlessSudoAccess": "true",
      "provisionInstanceScript": "",
      "installNodeExporter": "true",
      "nodeExporterPort": 9300,
      "nodeExporterUser": "prometheus",
      "skipProvisioning": "false",
      "setUpChrony": "true",
      "ntpServers": [],
      "showSetUpChrony": "false",
      "cloudInfo": {
        "aws": {
          "useIMDSv2": "true",
          "hostVpcRegion": "eu-west-3",
          "hostVpcId": "vpc-01234567890",
          "vpcType": "EXISTING"
        }
      },
      "enableNodeAgent": "true"
    },
    "regions": [
      {
        "uuid": "457834f0-bbfe-4a8e-b222-999404b142fc",
        "code": "eu-west-3",
        "name": "Europe (Paris)",
        "longitude": 2.2770204,
        "latitude": 48.8589507,
        "zones": [
          {
            "uuid": "9b136c2b-2144-46c4-a456-5ab427ffd5e3",
            "code": "eu-west-3a",
            "name": "eu-west-3a",
            "active": "true",
            "subnet": "subnet-01234567890",
            "details": {
              "cloudInfo": {}
            }
          },
          {
            "uuid": "edb41508-ab7f-112b-b9e1-abfb20ba3d0d",
            "code": "eu-west-3b",
            "name": "eu-west-3b",
            "active": "true",
            "subnet": "subnet-11234567890",
            "details": {
              "cloudInfo": {}
            }
          },
          {
            "uuid": "15933172-c555-4652-a741-6a719352bf99",
            "code": "eu-west-3c",
            "name": "eu-west-3c",
            "active": "true",
            "subnet": "subnet-21234567890",
            "details": {
              "cloudInfo": {}
            }
          }
        ],
        "active": "true",
        "details": {
          "cloudInfo": {
            "aws": {
              "vnet": "vpc-01234567890",
              "securityGroupId": "sg-01234567890"
            }
          }
        },
        "securityGroupId": "sg-01234567890",
        "vnetName": "vpc-01234567890"
      }
    ],
    "imageBundles": [
      {
        "uuid": "99733bf7-5b31-424f-8a8f-1f21c770da79",
        "name": "YBA-Managed-AlmaLinux-8.9_20240303",
        "details": {
          "arch": "x86_64",
          "regions": {
            "eu-west-3": {
              "ybImage": "ami-07c6b902dd2603071"
            }
          },
          "sshUser": "ec2-user",
          "sshPort": 22,
          "useIMDSv2": "false"
        },
        "useAsDefault": "true",
        "metadata": {
          "type": "YBA_ACTIVE",
          "version": "8.9_20240303"
        },
        "active": "true"
      },
      {
        "uuid": "745e43f8-bb44-4ded-b7c9-316e2a167d47",
        "name": "YBA-Managed-AlmaLinux-8.9_20240303",
        "details": {
          "arch": "aarch64",
          "regions": {
            "eu-west-3": {
              "ybImage": "ami-0525888bdaf4caa26"
            }
          },
          "sshUser": "ec2-user",
          "sshPort": 22,
          "useIMDSv2": "false"
        },
        "useAsDefault": "false",
        "metadata": {
          "type": "YBA_ACTIVE",
          "version": "8.9_20240303"
        },
        "active": "true"
      }
    ],
    "allAccessKeys": [
      {}
    ],
    "version": 14,
    "usabilityState": "READY",
    "airGapInstall": "false",
    "sshUser": "ec2-user",
    "sshPort": 22,
    "keyPairName": "key-name"
  }
]
```

## Managing universes (YugabyteDB clusters)

### create_yba_release

This function [adds a YugabyteDB release](https://docs.yugabyte.com/preview/yugabyte-platform/manage-deployments/ybdb-releases/) to the YBA instance so that it can be deployed to new or existing universes. Some common parameters are re-used from earlier examples by splatting `invoke_yba_request_args`, and it also accepts a package URL.

The package URLs can be found on the [YugabyteDB releases web page](https://docs.yugabyte.com/preview/releases/ybdb-releases/). In the following table <version> is a four-segment version, such as 2024.2.3.2, and <build> is a build number prefixed with b, such as b6. Note that the Kubernetes Helm chart uses <short version>, a three segment version, such as 2024.2.3.

|Platform|Architecture|Releases page link?|Package URL pattern|
|-|-|-|-|
|Linux|x86 64-bit|Yes|https://software.yugabyte.com/releases/<build>/yugabyte-2024.2.3.2-b6-linux-x86_64.tar.gz|
|Linux|ARM|Yes|https://software.yugabyte.com/releases/<build>>/yugabyte-<version>-<build>-el8-aarch64.tar.gz|
|Kubernetes|Either|No|https://s3.us-west-2.amazonaws.com/releases.yugabyte.com/<version>-<build>/helm/yugabyte-<short version>.tgz|

The function accepts a package URL and either:

- Adds a new release and package (architecture)
- Adds a new architecture to an existing release
- Returns an existing release if it's already present in YBA

Some common parameters are re-used from earlier examples by splatting `invoke_yba_request_args`.

```
release = create_yba_release(
    **invoke_yba_request_args,
    package_url = 'https://software.yugabyte.com/releases/2024.1.6.0/yugabyte-2024.1.6.0-b53-el8-aarch64.tar.gz'
)
```

### create_yba_backup_storage_aws

This function configures a storage location for backups using Amazon's S3 (Simple Storage Service) standard. Some common parameters are re-used from earlier examples by splatting `invoke_yba_request_args`.

```
backup_storage = create_yba_backup_storage_aws(
    **invoke_yba_request_args,
    configuration_name = 'backup-storage-location-1',
    bucket_name = 's3-bucket-backups'
)
```

A successfully applied backup storage configuration will look like this:

```
{
    "configUUID": "e48f50f1-f993-4070-8e73-363364fddf55",
    "configName": "backup-storage-location-1",
    "customerUUID": "0e71e2dc-3a12-4989-ad62-087e796d0ab0",
    "type": "STORAGE",
    "name": "S3",
    "data": {
        "BACKUP_LOCATION":
        "s3://3-bucket-backups",
        "AWS_HOST_BASE": "s3.amazonaws.com",
        "IAM_INSTANCE_PROFILE": "true"
    },
    "state": "Active"
}
```

### create_yba_provider

This function adds a cloud provider to YBA to allow it to build and manage virtual machine-based YugabyteDB universes (clusters) in a public cloud. The templates are configured to support AWS three zone universes through either access key- or IAM-based authentication.

The `template_file` parameter can be used to specify different options from the available, or additional, templates. The `params` parameter is a dictionary which accepts values to be substituted into the JSON templates.

To create a three zone region provider which uses YBA's managed virtual machine images and its assigned IAM role for authentication and authorisation:

```
params = {
    'name': 'aws-cloud-provider-1',
    'region_code': 'eu-west-3',
    'sg_id': 'sg-01234567890',
    'vpc_id': 'vpc-01234567890',
    'zone_1_code': 'eu-west-3a',
    'zone_1_subnet': 'subnet-01234567890',
    'zone_2_code': 'eu-west-3b',
    'zone_2_subnet': 'subnet-09876543210',
    'zone_3_code': 'eu-west-3c',
    'zone_3_subnet': 'subnet-00000000000'
}

provider = create_yba_provider(
    **invoke_yba_request_args,
    params = params
)
```

The function returns a provider configuration task. The created provider can be retrieved from the `/api/v1/providers` endpoint.

```
{
  "title": "Created Provider : dr2-aws-eu-west-3",
  "createTime": "Fri Jul 04 13:34:50 UTC 2025",
  "completionTime": "Fri Jul 04 13:35:00 UTC 2025",
  "target": "aws-cloud-provider-1",
  "targetUUID": "ae2aeb13a-4a2c-471d-8a33-02ac9e10b3f",
  "type": "Create",
  "status": "Success",
  "percent": 100.0,
  "correlationId": "8545e16-b1ee-40b5-a40f-2621242686820",
  "userEmail": "admin@yugabyte.com",
  "details": {
    "taskDetails": [
      {
        "title": "Bootstrapping Cloud",
        "description": "Set up AccessKey, Region, and Provider for a given cloud Provider",
        "state": "Success",
        "extraDetails": []
      },
      {
        "title": "Bootstrapping Region",
        "description": "Set up AccessKey, Region, and Provider for a given cloud Provider",
        "state": "Success",
        "extraDetails": []
      },
      {
        "title": "Creating AccessKey",
        "description": "Set up AccessKey in the given Provider Vault",
        "state": "Success",
        "extraDetails": []
      },
      {
        "title": "Initializing Cloud Metadata",
        "description": "Initialize Instance Pricing and Zone Metadata from Cloud Provider",
        "state": "Success",
        "extraDetails": []
      }
    ]
  },
  "abortable": "false",
  "retryable": "false"
}
```

Alternatively, to create a three zone region provider which uses custom virtual machine images and an access key for authentication and authorisation:

```
params = {
    'name': 'aws-cloud-provider-2',
    'region_code': 'eu-west-3',
    'access_key_id': '<access key ID>',
    'access_key_secret': '<access key secret>',
    'dns_zone_id': 'r53-01234567890',
    'sg_id': 'sg-01234567890',
    'vpc_id': 'vpc-01234567890',
    'ssh_private_key': '<private_key_data>',
    'zone_1_code': 'eu-west-3a',
    'zone_1_subnet': 'subnet-01234567890',
    'zone_2_code': 'eu-west-3b',
    'zone_2_subnet': 'subnet-09876543210',
    'zone_3_code': 'eu-west-3c',
    'zone_3_subnet': 'subnet-00000000000',
    'ntp_server_1': '0.ntp.org',
    'ntp_server_2': '2.ntp.org',
    'architecture': 'x86_64',
    'ami_id': 'ami-01234567890',
    'ssh_user': 'admin-user',
    'image_name': 'custom-aws-ec2-image'
}

provider = create_yba_provider(
    **invoke_yba_request_args,
    params = params,
    template_file = './templates/provider_aws_key_customimage.json'
)
```

Further examples of using the YBA API to create cloud provider configuration can be seen [here](https://github.com/yugabyte/yugabyte-db/blob/master/managed/api-examples/python-simple/create-provider.ipynb).

### create_yba_provider_kubernetes

If YugabyteDB Anywhere is deployed to Kubernetes with the `rbac.create` Helm chart value set to `true` it will configure a service account, role and role binding to allow it sufficient privileges to retrieve configuration information from the Kubernetes cluster on which it resides. This reduces the details that need to be provided when adding a provider for its own Kubernetes cluster.

The function has a `use_suggested` parameter to enable this option, else additonal values must be provided in the `params` dictionary for substitution into the JSON template. In this example the automatically detected Kubernetes details are used and only the storage class needs to be defined:

```
create_yba_provider_local_kubernetes(
    **invoke_yba_request_args,
    params = {'storage_class': 'default'},
    use_suggested = True
)
```

### create_yba_universe

The universe creation function follows the pattern of earlier functions but has a longer list of required details to be injected into the creation template.

Many of these details can be retrieved from the provider through the API, which this example does first. It assumes that the first provider is appropriate for the new universe.

```
    providers = invoke_yba_request(
        **invoke_yba_request_args,
        endpoint = f"/api/v1/customers/{login['customerUUID']}/providers"
    )

    params = {
        'name': 'new-universe',
        'version': '2024.2.3.2-b6',
        'ysql_password': password,
        'ycql_password': password,
        'node_count': 1,
        'replication_factor': 1,
        'volume_size': 5,
        'volume_count': 1,
        'master_volume_size': 50,
        'master_volume_count': 1,
        'storage_class': 'default',
        'master_cpu_count': 1,
        'master_memory_gb': 2,
        'tserver_cpu_count': 1,
        'tserver_memory_gb': 2,
        'provider_id': providers[0]['uuid'],
        'cloud_id': providers[0]['uuid'],
        'cloud_region_list': f"\"{providers[0]["regions"][0]["uuid"]}\"",
        'cloud_region_id': providers[0]["regions"][0]["uuid"],
        'cloud_region_code': providers[0]["regions"][0]["code"],
        'cloud_region_name': providers[0]["regions"][0]["name"],
        'cloud_az_id': providers[0]["regions"][0]["zones"][0]["uuid"],
        'cloud_az_name': providers[0]["regions"][0]["zones"][0]["name"],
        'architecture': 'x86_64'
    }

    # Create a universe
    create_yba_universe(
        **invoke_yba_request_args,
        params = params
    )
```
