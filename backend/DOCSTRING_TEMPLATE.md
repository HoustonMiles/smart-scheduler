# Docstring Template

Use this template for all functions in the codebase.

## Functions

```python
async def function_name(
    param1: Type1,
    param2: Type2 = default_value
) -> ReturnType:
    """
    Brief one-line description of what the function does.
    
    More detailed description if needed. Explain the purpose,
    behavior, and any important implementation details.
    
    Args:
        param1: Description of param1
        param2: Description of param2 (optional, default: default_value)
        
    Returns:
        Description of return value
        
    Raises:
        ExceptionType: When and why this exception is raised
        
    Example:
        >>> result = await function_name(value1, value2)
        >>> print(result)
        Expected output
    """
    # Implementation
```

## Classes

```python
class ClassName:
    """
    Brief description of the class.
    
    More detailed description of what the class does and how it should be used.
    
    Attributes:
        attribute1: Description of attribute1
        attribute2: Description of attribute2
        
    Example:
        >>> obj = ClassName()
        >>> obj.method()
    """
```

## Apply to All New Code

- Every public function/method must have a docstring
- Every class must have a docstring
- Private functions (starting with _) should have docstrings if complex
- Use Google-style docstrings consistently
