import lambda_handler
consignment_id = 'e7073993-0bed-4d5f-bb2a-5bea1b2a87d3'
event = {'consignmentId': consignment_id}
lambda_handler.handler(event, None)
