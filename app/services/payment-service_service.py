# Assuming the object is supposed to be initialized before use
obj = SomeClass()  # Initialize the object
try:
    if obj is not None and obj.some_attribute is not None:
        _ = obj.some_attribute.nested_value
except AttributeError as e:
    # Handle the exception, e.g., log the error and continue
    print(f"Error accessing some_attribute: {e}")