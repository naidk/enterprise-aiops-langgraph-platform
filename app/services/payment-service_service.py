# Assuming the object is initialized somewhere in the code
obj = None  # or some other initialization

# Add a null check before accessing the attribute
if obj is not None and hasattr(obj, 'some_attribute') and obj.some_attribute is not None:
    _ = obj.some_attribute.nested_value
else:
    # Handle the case where obj or obj.some_attribute is None
    # For example, log an error or set a default value
    print("Error: obj or obj.some_attribute is None")
    # or
    _ = None  # or some other default value