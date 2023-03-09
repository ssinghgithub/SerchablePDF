import aws_cdk as cdk
import aws_cdk.aws_s3 as _s3
import aws_cdk.aws_sqs as _sqs
import aws_cdk.aws_iam as _iam
import aws_cdk.aws_ecr as _ecr
import aws_cdk.aws_lambda as _lambda
import aws_cdk.aws_s3_notifications as _s3n
from aws_cdk.aws_ecr_assets import DockerImageAsset
from aws_cdk.aws_lambda_event_sources import SqsEventSource

from config import IDs, EnvSettings, Name, ARNs, ResourceNames


class PipelineIngestStack(cdk.NestedStack):

    def __init__(self, scope, **kwargs):
        super().__init__(scope, "trn-ingest-stack", **kwargs)

        # Create SQS
        data_queue = _sqs.Queue(self, 'raw_data_queue',
                                queue_name='data_pipeline_queue',
                                visibility_timeout=cdk.Duration.seconds(200))

        # Create raw and processed S3 buckets
        raw_bucket = _s3.Bucket(self, 'raw_bucket',
                                bucket_name=EnvSettings.INPUT_BUCKET_NAME,
                                auto_delete_objects=True,
                                removal_policy=cdk.RemovalPolicy.DESTROY,
                                lifecycle_rules=[_s3.LifecycleRule(
                                    transitions=[_s3.Transition(
                                        storage_class=_s3.StorageClass.GLACIER,
                                        transition_after=cdk.Duration.days(7))]
                                )])
        raw_bucket.add_event_notification(_s3.EventType.OBJECT_CREATED, _s3n.SqsDestination(data_queue),
                                          _s3.NotificationKeyFilter(prefix="uploads", suffix=".pdf", )
                                          )
        _s3.Bucket(self, 'textract_output_bucket',
                   bucket_name=EnvSettings.TEXTRACT_OUTPUT_BUCKET_NAME,
                   auto_delete_objects=True,
                   removal_policy=cdk.RemovalPolicy.DESTROY)

        # Create lambda function to process the messages from SQS
        processing_lambda = _lambda.Function(self, 'processing_lambda',
                                             function_name='data_processing',
                                             description="Function pulls messages from the input SQS and triggers "
                                                         "the Textract Step Function",
                                             runtime=_lambda.Runtime.PYTHON_3_7,
                                             handler='processing_lambda.handler',
                                             code=_lambda.Code.from_asset('assets/lambda'),
                                             events=[SqsEventSource(data_queue)],
                                             timeout=cdk.Duration.seconds(180),
                                             retry_attempts=0,
                                             environment={'QueueUrl': data_queue.queue_url})

        processing_lambda.role.attach_inline_policy(_iam.Policy(self, 'access_fer_lambda',
                                                                statements=[
                                                                    _iam.PolicyStatement(effect=_iam.Effect.ALLOW,
                                                                                         actions=['s3:*'],
                                                                                         resources=['*'])]))

        # processing_lambda = _lambda.DockerImageFunction(self, 'processing_lambda',
        #                                                 function_name='data_processing',
        #                                                 description='Starts Docker Container in Lambda to process data',
        #                                                 code=_lambda.DockerImageCode.from_image_asset('assets/lambda/',
        #                                                                                               file='dockerfile'),
        #                                                 architecture=_lambda.Architecture.X86_64,
        #                                                 events=[SqsEventSource(data_queue)],
        #                                                 timeout=cdk.Duration.seconds(180),
        #                                                 retry_attempts=0,
        #                                                 environment={'QueueUrl': data_queue.queue_url})
        #
        # processing_lambda.role.attach_inline_policy(_iam.Policy(self, 'access_fer_lambda',
        #                                                         statements=[
        #                                                             _iam.PolicyStatement(effect=_iam.Effect.ALLOW,
        #                                                                                  actions=['s3:*'],
        #                                                                                  resources=['*'])]))
