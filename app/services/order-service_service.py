# Assuming the object is 'obj' and the attribute is 'some_attribute'
if obj is not None and hasattr(obj, 'some_attribute') and obj.some_attribute is not None:
    _ = obj.some_attribute.nested_value
else:
    # Handle the case when obj or obj.some_attribute is None
    # For example, log an error or set a default value
    logging.error("Object or its attribute is None")
    # or
    _ = None  # or some default value