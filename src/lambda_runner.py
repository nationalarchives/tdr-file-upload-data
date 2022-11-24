import lambda_handler
user_id = '030cf12c-8d5d-46b9-b86a-38e0920d0e1a'
consignment_id = 'e7073993-0bed-4d5f-bb2a-5bea1b2a87d3'
event = {'userId': user_id, 'consignmentId': consignment_id}
lambda_handler.handler(event, None)
