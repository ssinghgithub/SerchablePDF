import aws_cdk as cdk
import aws_cdk.aws_s3 as _s3
import aws_cdk.aws_sqs as _sqs
import aws_cdk.aws_iam as _iam
import aws_cdk.aws_lambda as _lambda
import aws_cdk.aws_s3_notifications as _s3n
import aws_cdk.aws_sns as _sns
import aws_cdk.aws_dynamodb as _ddb
import aws_cdk.aws_sns_subscriptions as _snssubscr
import aws_cdk.aws_events as _events
import aws_cdk.aws_events_targets as _targets
from aws_cdk.aws_lambda_event_sources import (S3EventSource, SqsEventSource, SnsEventSource, DynamoEventSource)
from aws_cdk import aws_events, aws_events_targets

from config import IDs, EnvSettings, Name, ARNs, ResourceNames

from stacks.pipeline_ingest_stack import *


class TrainingPipelineStack(cdk.Stack):

    def __init__(self, scope, construct_id, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # Create training pipeline Ingest Stack
        # ingest_stack = PipelineIngestStack(scope, "trn-ingest-stack", **kwargs)

        # The code that defines your stack goes here
        '''******************************SNS Topics****************************** '''
        jobCompletionTopic = _sns.Topic(self, 'jobCompletion')

        '''******************************IAM Roles****************************** '''

        textractServiceRole = _iam.Role(self, 'TextractServiceRole', assumed_by=_iam.ServicePrincipal('textract'
                                                                                                      '.amazonaws.com'))
        textractServiceRole.add_to_policy(_iam.PolicyStatement(effect=_iam.Effect.ALLOW,
                                                               actions=["sns:Publish"],
                                                               resources=[jobCompletionTopic.topic_arn]))

        '''******************************S3 Bath Operations Role ****************************** '''

        s3BatchOperationsRole = _iam.Role(self, 'S3BatchOperationsRole',
                                          assumed_by=_iam.ServicePrincipal('batchoperations.s3.amazonaws.com'))

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
                                   queue_name='input_job_queue',
                                   visibility_timeout=cdk.Duration.seconds(90),
                                   retention_period=cdk.Duration.seconds(1209600),
                                   dead_letter_queue=_sqs.DeadLetterQueue(max_receive_count=50, queue=dlq)
                                   )
        # Add notification events to the input bucket
        raw_bucket.add_event_notification(_s3.EventType.OBJECT_CREATED, _s3n.SqsDestination(inputDocQueue),
                                          _s3.NotificationKeyFilter(prefix="uploads", suffix=".pdf", )
                                          )

        # Queue for async jobs
        asyncJobsQueue = _sqs.Queue(self, 'AsyncJobs',
                                    queue_name='async_job_queue',
                                    visibility_timeout=cdk.Duration.seconds(30),
                                    retention_period=cdk.Duration.seconds(1209600),
                                    dead_letter_queue=_sqs.DeadLetterQueue(max_receive_count=50, queue=dlq)
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

        # add event source - NOT NEEDED
        # TestEventProcessor.add_event_source(SnsEventSource(jobCompletionTopic))

        '''------------------------------------------------------------'''

        # Lambda function to process Textraction output result

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




        # '''******************************Dynamo DB Table****************************** '''
        # # DynamoDB table with links to output in S3
        # outputTable = _ddb.Table(self, 'OutputTable',
        #                          partition_key=_ddb.Attribute(name="documentId", type=_ddb.AttributeType.STRING),
        #                          sort_key=_ddb.Attribute(name="outputType", type=_ddb.AttributeType.STRING))
        # # DynamoDB table with links to output in S3
        # documentsTable = _ddb.Table(self, 'DocumentsTable',
        #                             partition_key=_ddb.Attribute(name="documentId", type=_ddb.AttributeType.STRING),
        #                             stream=_ddb.StreamViewType.NEW_IMAGE)
        #
        # '''******************************Lambda Function****************************** '''
        # # Create Lambda layers
        # # helper layer with helper functions
        # helperLayer = _lambda.LayerVersion(self, 'HelperLayer',
        #                                    code=_lambda.Code.from_asset('assets/lambda/helper'),
        #                                    compatible_runtimes=[_lambda.Runtime.PYTHON_3_7],
        #                                    license='Apache-2.0',
        #                                    description='Helper layer')
        # # Textractor helper layer
        # textractorLayer = _lambda.LayerVersion(self, 'Textractor',
        #                                        code=_lambda.Code.from_asset('assets/lambda/textractor'),
        #                                        compatible_runtimes=[_lambda.Runtime.PYTHON_3_7],
        #                                        license='Apache-2.0',
        #                                        description='Textractor layer')
        # # Pandas layer
        # pandasLayer = _lambda.LayerVersion(self, 'PandasLayer',
        #                                    code=_lambda.Code.from_asset('assets/lambda/pdnp'),
        #                                    compatible_runtimes=[_lambda.Runtime.PYTHON_3_7],
        #                                    license='Apache-2.0',
        #                                    description='Pandas layer')
        #
        # # Lambda function to process input S3 events
        # '''------------------------------------------------------------'''
        # s3EventProcessor = _lambda.Function(self, 's3EventProcessor',
        #                                     function_name='input_s3_event_processor',
        #                                     description='Function to process input S3 events',
        #                                     runtime=_lambda.Runtime.PYTHON_3_7,
        #                                     handler='S3EventProcLambda.lambda_handler',
        #                                     code=_lambda.Code.from_asset('assets/lambda'),
        #                                     timeout=cdk.Duration.seconds(180),
        #                                     retry_attempts=0,
        #                                     layers=[helperLayer],
        #                                     environment={'DOCUMENTS_TABLE': documentsTable.table_name,
        #                                                  'OUTPUT_TABLE': outputTable.table_name
        #                                                  })
        # # Add Trigger between input s3 and lambda
        # s3EventProcessor.add_event_source(S3EventSource(raw_bucket,
        #                                                 events=[_s3.EventType.OBJECT_CREATED,
        #                                                         _s3.EventType.OBJECT_REMOVED],
        #                                                 filters=[
        #                                                     _s3.NotificationKeyFilter(prefix="uploads/", suffix=".pdf")]
        #                                                 )
        #                                   )
        #
        # # Add Trigger between input sqs and lambda
        # # s3EventProcessor.add_event_source(SqsEventSource(queue=inputDocQueue))
        #
        # # Permissions
        # documentsTable.grant_read_write_data(s3EventProcessor)
        # asyncJobsQueue.grant_send_messages(s3EventProcessor)
        #
        # '''------------------------------------------------------------'''
        # # Lambda function to process Documents from DDB stream
        # docProcessor = _lambda.Function(self, 'docProcessor',
        #                                 function_name='ddb_doc_processor',
        #                                 description='Function to process docs from DDB',
        #                                 runtime=_lambda.Runtime.PYTHON_3_7,
        #                                 handler='DocProcLambda.lambda_handler',
        #                                 code=_lambda.Code.from_asset('assets/lambda'),
        #                                 timeout=cdk.Duration.seconds(180),
        #                                 retry_attempts=0,
        #                                 layers=[helperLayer],
        #                                 environment={'ASYNC_QUEUE_URL': asyncJobsQueue.queue_url}
        #                                 )
        #
        # # Add Trigger DDB event and docProcessor lambda
        # docProcessor.add_event_source(DynamoEventSource(documentsTable,
        #                                                 starting_position=_lambda.StartingPosition.TRIM_HORIZON)
        #                               )
        #
        # # Permissions
        # documentsTable.grant_read_write_data(docProcessor)
        # asyncJobsQueue.grant_send_messages(docProcessor)
        #
        # '''------------------------------------------------------------'''
        #
        # # Lambda function to process Documents via Textract
        # asyncProcessor = _lambda.Function(self, 'ASyncProcessor',
        #                                   function_name='async_job_processor',
        #                                   description='Function to run Textract Jobs',
        #                                   runtime=_lambda.Runtime.PYTHON_3_7,
        #                                   handler='AsyncProcLambda.lambda_handler',
        #                                   code=_lambda.Code.from_asset('assets/lambda'),
        #                                   reserved_concurrent_executions=5,
        #                                   timeout=cdk.Duration.seconds(60),
        #                                   retry_attempts=0,
        #                                   layers=[helperLayer],
        #                                   environment={'ASYNC_QUEUE_URL': asyncJobsQueue.queue_url,
        #                                                'SNS_TOPIC_ARN': jobCompletionTopic.topic_arn,
        #                                                'SNS_ROLE_ARN': textractServiceRole.role_arn,
        #                                                }
        #                                   )
        #
        # # Triggers
        # # Run async job processor every 5 minutes
        #
        # lambda_schedule = aws_events.Schedule.rate(cdk.Duration.minutes(5))
        # event_lambda_target = aws_events_targets.LambdaFunction(handler=asyncProcessor)
        #
        # lambda_schedule_rule = aws_events.Rule(self, 'ScheduleRule',
        #                                        description='Every 5 minutes CloudWatch event trigger for the Lambda',
        #                                        enabled=True,
        #                                        schedule=lambda_schedule,
        #                                        targets=[event_lambda_target])
        #
        # # add event source
        # asyncProcessor.add_event_source(SnsEventSource(jobCompletionTopic))
        #
        # # permission
        # raw_bucket.grant_read(asyncProcessor)
        # asyncJobsQueue.grant_consume_messages(asyncProcessor)
        # asyncProcessor.add_to_role_policy(_iam.PolicyStatement(actions=["iam:PassRole"],
        #                                                        resources=[textractServiceRole.role_arn]))
        # asyncProcessor.add_to_role_policy(_iam.PolicyStatement(actions=["textract:*"],
        #                                                        resources=["*"]))
        #
        # '''------------------------------------------------------------'''
        #
        # # Lambda function to process Textraction output result
        #
        # jobResultProcessor = _lambda.Function(self, 'JobResultProcessor',
        #                                       function_name='job_result_processor',
        #                                       description="Function to run process Textract Output",
        #                                       runtime=_lambda.Runtime.PYTHON_3_7,
        #                                       handler='ResultProcLambda.lambda_handler',
        #                                       code=_lambda.Code.from_asset('assets/lambda'),
        #                                       reserved_concurrent_executions=5,
        #                                       timeout=cdk.Duration.seconds(60),
        #                                       retry_attempts=0,
        #                                       layers=[pandasLayer],
        #                                       environment={'bucketName': textract_output_bucket.bucket_name,
        #                                                    'PREFIX': 'textract-output',
        #                                                    'qUrl': jobResultsQueue.queue_url
        #                                                    }
        #                                       )
        #
        # # Permission
        # textract_output_bucket.grant_write(jobResultProcessor)
        # jobResultsQueue.grant_consume_messages(jobResultProcessor)
        # jobResultProcessor.add_to_role_policy(_iam.PolicyStatement(actions=["iam:PassRole"],
        #                                                            resources=[textractServiceRole.role_arn]))
        # jobResultProcessor.add_to_role_policy(_iam.PolicyStatement(actions=["textract:*"],
        #                                                            resources=["*"]))
        # # Add Trigger between sqs and lambda
        # ## Note: batchSize: Determines how many records are buffered before invoking your lambda function.
        # ## if using batchwindow- then apply recommended visibility timeout
        # # https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html#events-sqs-queueconfig
        #
        # jobResultProcessor.add_event_source(SqsEventSource(queue=jobResultsQueue))
        #
        # '''------------------------------------------------------------'''
        #
        # # processing_lambda = _lambda.Function(self, 'processing_lambda',
        # #                                      function_name='data_processing',
        # #                                      description="Function pulls messages from the input SQS and triggers "
        # #                                                  "the Textract Step Function",
        # #                                      runtime=_lambda.Runtime.PYTHON_3_7,
        # #                                      handler='processing_lambda.handler',
        # #                                      code=_lambda.Code.from_asset('assets/lambda'),
        # #                                      events=[SqsEventSource(data_queue)],
        # #                                      timeout=cdk.Duration.seconds(180),
        # #                                      retry_attempts=0,
        # #                                      environment={'QueueUrl': data_queue.queue_url,
        # #                                                   'ASYNC_QUEUE_URL': ocr_complete_queue.queue_url,
        # #                                                   })
        # #
        # # processing_lambda.role.attach_inline_policy(_iam.Policy(self, 'access_fer_lambda',
        # #                                                         statements=[
        # #                                                             _iam.PolicyStatement(effect=_iam.Effect.ALLOW,
        # #                                                                                  actions=['s3:*'],
        # #                                                                                  resources=['*'])]))
        #
        # # processing_lambda = _lambda.DockerImageFunction(self, 'processing_lambda',
        # #                                                 function_name='data_processing',
        # #                                                 description='Starts Docker Container in Lambda to process data',
        # #                                                 code=_lambda.DockerImageCode.from_image_asset('assets/lambda/',
        # #                                                                                               file='dockerfile'),
        # #                                                 architecture=_lambda.Architecture.X86_64,
        # #                                                 events=[SqsEventSource(data_queue)],
        # #                                                 timeout=cdk.Duration.seconds(180),
        # #                                                 retry_attempts=0,
        # #                                                 environment={'QueueUrl': data_queue.queue_url})
        # #
        # # processing_lambda.role.attach_inline_policy(_iam.Policy(self, 'access_fer_lambda',
        # #                                                         statements=[
        # #                                                             _iam.PolicyStatement(effect=_iam.Effect.ALLOW,
        # #                                                                                  actions=['s3:*'],
        # #                                                                                  resources=['*'])]))
