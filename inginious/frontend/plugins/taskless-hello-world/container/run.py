from inginious_container_api import feedback, input

message = "Hello World!"
additional_message = f'I am {input.get_input("hello_world_name")}'

feedback.set_global_feedback(message + " " + additional_message)
feedback.set_global_result("success")