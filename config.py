'''
Copyright (c) 2023 Amazon.com, Inc. or its affiliates. All Rights Reserved.
This source code is subject to the terms found in the AWS Enterprise Customer Agreement.
NOTE: If deploying to production, set this to true.
 - If this is set to true, all properties from the Prod_Props class will be used
 - If this is set to false, all the properties from the Dev_Props class will be used
'''
IS_PROD = False


class DevProps:
    # General params
    ACCOUNT_ID = "017444429555"  # "ACCOUNT_ID"
    ACCOUNT_REGION = "us-east-1"

    # Account ID to enable cross-account access
    X_ACCOUNT_ID = ""

    # CloudFormation Service Linked Role
    SERVICE_LINKED_ROLE_NAME = "CloudFormationServiceLinkedRole"

    # CodeCommit Repository Name
    REPO_NAME = "index-extraction-repo"

    # CodeCommit Branch Names
    CODE_BRANCH = "main"

    # CodeBuild Settings
    TESTSPEC_FILENAME = "testspec.yaml"
    BUILDSPEC_FILENAME = "buildspec.yaml"

    # SNS Topic Names
    CICD_PROJECT_TOPIC_NAME = "idx_ext_build_notifications"
    CICD_APPROVAL_TOPIC_NAME = "idx_ext_peer_approval_notifications"
    INFERENCE_NOTIFICATIONS_TOPIC_NAME = "idx_ext_notifications"

    # CICD topic subscriptions
    CICD_TOPIC_EMAIL = [
        "snghigf@amazon.com",
    ]

    # NOTIFICATION topic subscriptions
    NOTIFICATION_TOPIC_EMAIL = ["idx-ext-security@amazon.com"]

    # S3 Bucket Names
    INPUT_BUCKET_NAME = "01-idx-extraction-input-dev" + '-' + ACCOUNT_ID
    MERGED_OUTPUT_BUCKET_NAME = "02-merged-output-bucket-dev" + '-' + ACCOUNT_ID
    TEXTRACT_OUTPUT_BUCKET_NAME = "02-textract-output-bucket-dev" + '-' + ACCOUNT_ID
    COMPREHEND_OUTPUT_BUCKET_NAME = "03-comprehend-output-bucket-dev" + '-' + ACCOUNT_ID

    # Bucket Folder prefixes
    INFERENCE_DOCUMENT_UPLOAD_FOLDER_PREFIX = "input-data"
    TEXTRACT_OUTPUT_FOLDER_PREFIX = "textract-output"
    COMPREHEND_OUTPUT_FOLDER_PREFIX = "comprehend-output"

    # DynamoDB Database
    DYNAMO_DATABASE_NAME = "index-extraction-pipeline-dev"


class ProdProps:
    pass


class EnvSettings:
    TEAM = "AWS-ProServe"
    PROJECT_NAME = "index_extraction"
    # General params
    ACCOUNT_ID = ProdProps.ACCOUNT_ID if IS_PROD else DevProps.ACCOUNT_ID
    ACCOUNT_REGION = ProdProps.ACCOUNT_REGION if IS_PROD else DevProps.ACCOUNT_REGION

    # CloudFormation Service Linked Role
    SERVICE_LINKED_ROLE_NAME = ProdProps.SERVICE_LINKED_ROLE_NAME if IS_PROD else DevProps.SERVICE_LINKED_ROLE_NAME

    # CodeCommit Repository Name
    REPO_NAME = ProdProps.REPO_NAME if IS_PROD else DevProps.REPO_NAME

    # CodeCommit Branch Names
    CODE_BRANCH = ProdProps.CODE_BRANCH if IS_PROD else DevProps.CODE_BRANCH

    # CodeBuild Settings
    TESTSPEC_FILENAME = ProdProps.TESTSPEC_FILENAME if IS_PROD else DevProps.TESTSPEC_FILENAME
    BUILDSPEC_FILENAME = ProdProps.BUILDSPEC_FILENAME if IS_PROD else DevProps.BUILDSPEC_FILENAME

    # SNS Topic Names
    CICD_PROJECT_TOPIC_NAME = ProdProps.CICD_PROJECT_TOPIC_NAME if IS_PROD else DevProps.CICD_PROJECT_TOPIC_NAME
    CICD_APPROVAL_TOPIC_NAME = ProdProps.CICD_APPROVAL_TOPIC_NAME if IS_PROD else DevProps.CICD_APPROVAL_TOPIC_NAME
    INFERENCE_NOTIFICATIONS_TOPIC_NAME = ProdProps.INFERENCE_NOTIFICATIONS_TOPIC_NAME if IS_PROD else DevProps.INFERENCE_NOTIFICATIONS_TOPIC_NAME

    # CICD topic subscriptions
    CICD_TOPIC_EMAIL = ProdProps.CICD_TOPIC_EMAIL if IS_PROD else DevProps.CICD_TOPIC_EMAIL

    # NOTIFICATION topic subscriptions
    NOTIFICATION_TOPIC_EMAIL = ProdProps.NOTIFICATION_TOPIC_EMAIL if IS_PROD else DevProps.NOTIFICATION_TOPIC_EMAIL

    # S3 Bucket Names
    INPUT_BUCKET_NAME = ProdProps.INPUT_BUCKET_NAME if IS_PROD else DevProps.INPUT_BUCKET_NAME
    MERGED_OUTPUT_BUCKET_NAME = ProdProps.MERGED_OUTPUT_BUCKET_NAME if IS_PROD \
        else DevProps.MERGED_OUTPUT_BUCKET_NAME
    TEXTRACT_OUTPUT_BUCKET_NAME = ProdProps.TEXTRACT_OUTPUT_BUCKET_NAME if IS_PROD \
        else DevProps.TEXTRACT_OUTPUT_BUCKET_NAME
    COMPREHEND_OUTPUT_BUCKET_NAME = ProdProps.COMPREHEND_OUTPUT_BUCKET_NAME if IS_PROD \
        else DevProps.COMPREHEND_OUTPUT_BUCKET_NAME

    # Bucket Folder prefixes
    INFERENCE_DOCUMENT_UPLOAD_FOLDER_PREFIX = ProdProps.INFERENCE_DOCUMENT_UPLOAD_FOLDER_PREFIX if IS_PROD \
        else DevProps.INFERENCE_DOCUMENT_UPLOAD_FOLDER_PREFIX
    TEXTRACT_OUTPUT_FOLDER_PREFIX = ProdProps.TEXTRACT_OUTPUT_FOLDER_PREFIX if IS_PROD \
        else DevProps.TEXTRACT_OUTPUT_FOLDER_PREFIX
    COMPREHEND_OUTPUT_FOLDER_PREFIX = ProdProps.COMPREHEND_OUTPUT_FOLDER_PREFIX if IS_PROD \
        else DevProps.COMPREHEND_OUTPUT_FOLDER_PREFIX

    # DynamoDB Database
    DYNAMO_DATABASE_NAME = ProdProps.DYNAMO_DATABASE_NAME if IS_PROD else DevProps.DYNAMO_DATABASE_NAME


class Name:
    PREFIX = "index-extraction"
    CICD_PREFIX = f'{PREFIX}-cicd'
    INFRA_PREFIX = f'{PREFIX}-infra'
    TRAINING_PIPELINE_PREFIX = f'{PREFIX}-training-pipeline-cdk'

    # Stages Names
    SOURCE_STAGE = "Source";
    TEST_STAGE = "Test";
    APPROVE_STAGE = "Approve";
    BUILD_STAGE = "Build";
    DEPLOY_STAGE = "Deploy";

    PREFIX_UNDERSCORE = f'{PREFIX}'.replace("-", "_")

    # Stack Names
    CICD_STACK = f'{CICD_PREFIX}-stack'
    INFRA_STACK = f'{INFRA_PREFIX}-stack'
    TRAINING_PIPELINE_STACK = f'{TRAINING_PIPELINE_PREFIX}-stack'


class IDs:
    # Resource IDs
    IDX_EXT_BUCKET = f'{Name.CICD_PREFIX}-bucket'


class ARNs:
    CF_SERVICE_LINKED_ROLE_ARN = f'arn:aws:iam::{EnvSettings.ACCOUNT_ID}:role/{EnvSettings.SERVICE_LINKED_ROLE_NAME}'
    CICD_PROJECT_TOPIC_ARN = f'arn:aws:sns:{EnvSettings.ACCOUNT_REGION}:{EnvSettings.ACCOUNT_ID}:{EnvSettings.CICD_PROJECT_TOPIC_NAME}'
    CICD_APPROVAL_TOPIC_ARN = f'arn:aws:sns:{EnvSettings.ACCOUNT_REGION}:{EnvSettings.ACCOUNT_ID}:{EnvSettings.CICD_APPROVAL_TOPIC_NAME}'


class ResourceNames:
    FUNCTION_PREFIX = f'{Name.PREFIX_UNDERSCORE}_func'
    BUCKET_PREFIX = f'{Name.PREFIX_UNDERSCORE}_bucket'
    CLOUDWATCH_PREFIX = f'{Name.PREFIX_UNDERSCORE}_cloudwatch'
    ROLE_PREFIX = f'{Name.PREFIX_UNDERSCORE}_role'
    POLICY_PREFIX = f'{Name.PREFIX_UNDERSCORE}_policy'
    QUEUE_PREFIX = f'{Name.PREFIX_UNDERSCORE}_queue'
    SNS_PREFIX = f'{Name.PREFIX_UNDERSCORE}_topic'
    TABLE_PREFIX = f'{Name.PREFIX_UNDERSCORE}_table'
    CICD_PREFIX = f'{Name.PREFIX_UNDERSCORE}_cicd'
    RULE_PREFIX = f'{Name.PREFIX_UNDERSCORE}_rule'
    STATE_MACHINE_PREFIX = f'{Name.PREFIX_UNDERSCORE}_sm'

# Dev_Props = {
#     # General params
#     "ACCOUNT_ID" : "",
#     "ACCOUNT_REGION" :"us-east-1",
#
#     # Account ID to enable cross-account access
#     "X_ACCOUNT_ID" : "",
#
#     # CloudFormation Service Linked Role
#     "SERVICE_LINKED_ROLE_NAME" : "CloudFormationServiceLinkedRole",
#
#     # CodeCommit Repository Name
#     "ROSIE_REPO_NAME" : "rosie-repo",
#
#     # CodeCommit Branch Names
#     "ROSIE_CODE_BRANCH" : "main",
#
#     # CodeBuild Settings
#     "TESTSPEC_FILENAME" :"testspec.yaml",
#     "BUILDSPEC_FILENAME" : "buildspec.yaml",
#
#     # SNS Topic Names
#     "CICD_PROJECT_TOPIC_NAME" : "rosie_build_notifications",
#     "CICD_APPROVAL_TOPIC_NAME" : "rosie_peer_approval_notifications",
#     "ROSIE_NOTIFICATIONS_TOPIC_NAME" : "rosie_notifications",
#
#     # CICD topic subscriptions
#     "CICD_TOPIC_EMAIL" : [
#         "snghigf@amazon.com",
#     ],
#
#     # NOTIFICATION topic subscriptions
#     "NOTIFICATION_TOPIC_EMAIL" : ["whs-rosie-security@amazon.com"],
#
#     # S3 Bucket Names
#     "INPUT_BUCKET_NAME" : "01-idx-extraction-input",
#     "TEXTRACT_OUTPUT_BUCKET_NAME" :"02-textract-output-bucket",
#     "COMPREHEND_OUTPUT_BUCKET_NAME" : "03-comprehend-output-bucket",
#
#     # Bucket Folder prefixes
#     "INFERENCE_DOCUMENT_UPLOAD_FOLDER_PREFIX" : "input-data",
#     "TEXTRACT_OUTPUT_FOLDER_PREFIX" : "textract-output",
#     "COMPREHEND_OUTPUT_FOLDER_PREFIX" : "comprehend-output",
#
#     # DynamoDB Database
#     "DYNAMO_DATABASE_NAME" : "index-extraction-pipeline"
# }
