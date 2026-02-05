from pydantic import BaseModel, Field


class CalculatorParams(BaseModel):
    expression: str = Field(description="Mathematical expression to evaluate")

async def calculator(params: CalculatorParams) -> str:
    """Evaluate a mathematical expression safely"""
    try:
        # Only allow safe operations
        allowed_chars = set("0123456789+-*/.() ")
        if not all(c in allowed_chars for c in params.expression):
            return "Error: Invalid characters in expression"

        result = eval(params.expression)  # Safe due to character filtering
        return f"Result: {result}"
    except Exception as e:
        return f"Error evaluating expression: {str(e)}"