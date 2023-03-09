import aws_cdk as cdk
import aws_cdk.aws_s3 as _s3
import aws_cdk.aws_sqs as _sqs
import aws_cdk.aws_iam as _iam
import aws_cdk.aws_lambda as _lambda
import aws_cdk.aws_s3_notifications as _s3n
import aws_cdk.aws_sns as _sns
import aws_cdk.aws_sns_subscriptions as _snssubscr
import aws_cdk.aws_events as _events
import aws_cdk.aws_events_targets as _targets
from aws_cdk.aws_lambda_event_sources import (S3EventSource, SqsEventSource, SnsEventSource, DynamoEventSource)
from aws_cdk import aws_events, aws_events_targets

from config import IDs, EnvSettings, Name, ARNs, ResourceNames



class TrainingPipelineStack(cdk.Stack):

    def __init__(self, scope, construct_id, **kwargs):
        super().__init__(scope, construct_id, **kwargs)


        # The code that defines your stack goes here
        '''******************************SNS Topics****************************** '''
        jobCompletionTopic = _sns.Topic(self, 'jobCompletion')

        '''******************************IAM Roles****************************** '''

        textractServiceRole = _iam.Role(self, 'TextractServiceRole', assumed_by=_iam.ServicePrincipal('textract'
                                                                                                      '.amazonaws.com'))
        textractServiceRole.add_to_policy(_iam.PolicyStatement(effect=_iam.Effect.ALLOW,
                                                               actions=["sns:Publish"],
                                                               resources=[jobCompletionTopic.topic_arn]))

        '''******************************S3 Bucket****************************** '''
        # Create raw and textract output S3 buckets
        raw_bucket = _s3.Bucket(self, 'raw_bucket',
                                bucket_name=EnvSettings.INPUT_BUCKET_NAME,
                                auto_delete_objects=True,
                                removal_policy=cdk.RemovalPolicy.DESTROY,
                                lifecycle_rules=[_s3.LifecycleRule(
                                    transitions=[_s3.Transition(
                                        storage_class=_s3.StorageClass.GLACIER,
                                        transition_after=cdk.Duration.days(7))]
                                )])

        # textract output bucket
        textract_output_bucket = _s3.Bucket(self, 'textract_output_bucket',
                                            bucket_name=EnvSettings.TEXTRACT_OUTPUT_BUCKET_NAME,
                                            auto_delete_objects=True,
                                            removal_policy=cdk.RemovalPolicy.DESTROY)

        '''******************************SQS****************************** '''
        # DLQ
        dlq = _sqs.Queue(self, 'DLQ', visibility_timeout=cdk.Duration.seconds(30),
                         retention_period=cdk.Duration.seconds(1209600))

        # Queue for async jobs
        inputDocQueue = _sqs.Queue(self, 'InputDocs',
                                   queue_name='input_job_queue-1',
                                   visibility_timeout=cdk.Duration.seconds(90),
                                   retention_period=cdk.Duration.seconds(1209600),
                                   dead_letter_queue=_sqs.DeadLetterQueue(max_receive_count=50, queue=dlq)
                                   )
        # Add notification events to the input bucket
        raw_bucket.add_event_notification(_s3.EventType.OBJECT_CREATED, _s3n.SqsDestination(inputDocQueue),
                                          _s3.NotificationKeyFilter(prefix="uploads", suffix=".pdf", )
                                          )


        # Queue for async Textract jobs results
        jobResultsQueue = _sqs.Queue(self, 'JobResults',
                                     queue_name='job_results_queue',
                                     visibility_timeout=cdk.Duration.seconds(300),
                                     retention_period=cdk.Duration.seconds(1209600),
                                     dead_letter_queue=_sqs.DeadLetterQueue(max_receive_count=50, queue=dlq)
                                     )
        # Trigger between SNS -> SQS once Textract job is completed
        jobCompletionTopic.add_subscription(_snssubscr.SqsSubscription(jobResultsQueue))

        ## -----Test code starts from here
        # Lambda function to process Testing

        # Pandas layer
        pandasLayer = _lambda.LayerVersion(self, 'PandasLayer',
                                           code=_lambda.Code.from_asset('assets/lambda/pdnp'),
                                           compatible_runtimes=[_lambda.Runtime.PYTHON_3_7],
                                           license='Apache-2.0',
                                           description='Pandas layer')
        '''------------------------------------------------------------'''
        TestEventProcessor = _lambda.Function(self, 'TestEventProcessor',
                                              function_name='input_sqs_msg_processor',
                                              description='Function to process messages from input queue',
                                              runtime=_lambda.Runtime.PYTHON_3_7,
                                              handler='TestSqsLambda.lambda_handler',
                                              code=_lambda.Code.from_asset('assets/lambda'),
                                              timeout=cdk.Duration.seconds(60),
                                              retry_attempts=0,
                                              reserved_concurrent_executions=5,
                                              environment={
                                                            'SNS_TOPIC_ARN': jobCompletionTopic.topic_arn,
                                                            'SNS_ROLE_ARN': textractServiceRole.role_arn
                                                            }
                                              )

        # Permissions
        raw_bucket.grant_read_write(TestEventProcessor)
        inputDocQueue.grant_consume_messages(TestEventProcessor)
        TestEventProcessor.add_to_role_policy(_iam.PolicyStatement(actions=["iam:PassRole"],
                                                               resources=[textractServiceRole.role_arn]))
        TestEventProcessor.add_to_role_policy(_iam.PolicyStatement(actions=["textract:*"],
                                                               resources=["*"]))

        # Add Trigger between input sqs (input sqs)  and lambda
        TestEventProcessor.add_event_source(SqsEventSource(queue=inputDocQueue))

        '''------------------------------------------------------------'''

        # Lambda function to process Textract output result

        jobResultProcessor = _lambda.Function(self, 'JobResultProcessor',
                                              function_name='job_result_processor',
                                              description="Function to run process Textract Output",
                                              runtime=_lambda.Runtime.PYTHON_3_7,
                                              handler='ResultProcLambda.lambda_handler',
                                              code=_lambda.Code.from_asset('assets/lambda'),
                                              timeout=cdk.Duration.seconds(300),
                                              retry_attempts=0,
                                              reserved_concurrent_executions=5,
                                              layers=[pandasLayer],
                                              environment={'bucketName': textract_output_bucket.bucket_name,
                                                           'PREFIX': 'textract-output',
                                                           'qUrl': jobResultsQueue.queue_url
                                                           }
                                              )



        # Permission
        textract_output_bucket.grant_write(jobResultProcessor)
        jobResultsQueue.grant_consume_messages(jobResultProcessor)
        jobResultProcessor.add_to_role_policy(_iam.PolicyStatement(actions=["iam:PassRole"],
                                                                   resources=[textractServiceRole.role_arn]))
        jobResultProcessor.add_to_role_policy(_iam.PolicyStatement(actions=["textract:*"],
                                                                   resources=["*"]))

        # Add Trigger between sqs (where textract sns pushes messages) and lambda

        '''Note: batchSize: Determines how many records are buffered before invoking your lambda function.
        if using batchwindow- then apply recommended visibility timeout
        https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html#events-sqs-queueconfig'''

        jobResultProcessor.add_event_source(SqsEventSource(queue=jobResultsQueue))


        # -----test code ends here
