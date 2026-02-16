import asyncio
import json
import os
from pathlib import Path
from typing import Any
import datetime

# Import from the forecasting bot
from forecasting_bot import (
    get_binary_gpt_prediction,
    get_numeric_gpt_prediction,
    get_multiple_choice_gpt_prediction,
    create_forecast_payload,
    NUM_RUNS_PER_QUESTION,
)


# Credit tracking globals
TOTAL_INPUT_TOKENS = 0
TOTAL_OUTPUT_TOKENS = 0
TOTAL_API_CALLS = 0


def estimate_tokens(text: str) -> int:
    """
    Rough estimate of tokens (approximately 4 characters per token).
    For more accurate counting, use tiktoken library.
    """
    return len(text) // 4


def track_api_call(input_text: str, output_text: str):
    """Track API usage for cost estimation."""
    global TOTAL_INPUT_TOKENS, TOTAL_OUTPUT_TOKENS, TOTAL_API_CALLS
    
    TOTAL_INPUT_TOKENS += estimate_tokens(input_text)
    TOTAL_OUTPUT_TOKENS += estimate_tokens(output_text)
    TOTAL_API_CALLS += 1


def calculate_cost(input_tokens: int, output_tokens: int, model: str = "anthropic/claude-opus-4.5") -> dict:
    """
    Calculate cost based on OpenRouter pricing.
    Prices as of Feb 2026 (check OpenRouter for current rates).
    """
    # OpenRouter pricing (per million tokens)
    pricing = {
        "anthropic/claude-opus-4.5": {"input": 15.00, "output": 75.00},
        "anthropic/claude-sonnet-4.5": {"input": 3.00, "output": 15.00},
        "anthropic/claude-haiku-4.5": {"input": 0.80, "output": 4.00},
    }
    
    if model not in pricing:
        model = "anthropic/claude-opus-4.5"  # default
    
    input_cost = (input_tokens / 1_000_000) * pricing[model]["input"]
    output_cost = (output_tokens / 1_000_000) * pricing[model]["output"]
    total_cost = input_cost + output_cost
    
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "input_cost_usd": round(input_cost, 4),
        "output_cost_usd": round(output_cost, 4),
        "total_cost_usd": round(total_cost, 4),
        "model": model,
    }


def reset_credit_tracking():
    """Reset credit tracking counters."""
    global TOTAL_INPUT_TOKENS, TOTAL_OUTPUT_TOKENS, TOTAL_API_CALLS
    TOTAL_INPUT_TOKENS = 0
    TOTAL_OUTPUT_TOKENS = 0
    TOTAL_API_CALLS = 0


def get_credit_summary(model: str = "anthropic/claude-opus-4.5") -> dict:
    """Get summary of credits used."""
    return {
        "total_api_calls": TOTAL_API_CALLS,
        **calculate_cost(TOTAL_INPUT_TOKENS, TOTAL_OUTPUT_TOKENS, model)
    }


def validate_question_data(data: dict[str, Any]) -> tuple[bool, str]:
    """
    Validate that the question data has all required fields.
    
    Returns:
        (is_valid, error_message)
    """
    # Check required common fields
    required_common = ["title", "description", "resolution_criteria", "type"]
    for field in required_common:
        if field not in data:
            return False, f"Missing required field: {field}"
        if not data[field]:
            return False, f"Field '{field}' cannot be empty"
    
    question_type = data["type"]
    valid_types = ["binary", "numeric", "discrete", "multiple_choice"]
    
    if question_type not in valid_types:
        return False, f"Invalid question type: {question_type}. Must be one of {valid_types}"
    
    # Validate type-specific fields
    if question_type in ["numeric", "discrete"]:
        if "scaling" not in data:
            return False, "Numeric/Discrete questions require 'scaling' field"
        
        scaling = data["scaling"]
        required_scaling = ["range_min", "range_max"]
        for field in required_scaling:
            if field not in scaling:
                return False, f"Missing required scaling field: {field}"
        
        if scaling["range_min"] >= scaling["range_max"]:
            return False, "range_min must be less than range_max"
        
        if "open_upper_bound" not in data or "open_lower_bound" not in data:
            return False, "Numeric/Discrete questions require 'open_upper_bound' and 'open_lower_bound' fields"
        
        if question_type == "discrete":
            if "inbound_outcome_count" not in scaling:
                return False, "Discrete questions require 'inbound_outcome_count' in scaling"
    
    elif question_type == "multiple_choice":
        if "options" not in data:
            return False, "Multiple choice questions require 'options' field"
        
        if not isinstance(data["options"], list) or len(data["options"]) < 2:
            return False, "Multiple choice questions must have at least 2 options"
    
    return True, ""


def load_question_from_file(filename: str) -> dict[str, Any]:
    """
    Load and validate question data from a JSON file in the input_questions folder.
    
    Args:
        filename: Name of the JSON file (e.g., "my_question.json")
    
    Returns:
        Question data dictionary
    
    Raises:
        ValueError: If file is invalid or validation fails
    """
    # Construct path to input_questions folder
    input_dir = Path("input_questions")
    filepath = input_dir / filename
    
    # Check if input directory exists
    if not input_dir.exists():
        raise ValueError(
            f"Input directory 'input_questions' does not exist. "
            f"Please create it and place your question files there."
        )
    
    # Check if file exists
    if not filepath.exists():
        raise ValueError(
            f"Input file not found: {filepath}\n"
            f"Looking in: {filepath.absolute()}"
        )
    
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format in {filename}: {e}")
    
    is_valid, error_msg = validate_question_data(data)
    if not is_valid:
        raise ValueError(f"Validation error in {filename}: {error_msg}")
    
    # Set defaults for optional fields
    if "fine_print" not in data:
        data["fine_print"] = ""
    
    if data["type"] in ["numeric", "discrete"]:
        if "zero_point" not in data["scaling"]:
            data["scaling"]["zero_point"] = None
        if "unit" not in data:
            data["unit"] = None
    
    return data


async def forecast_custom_question(
    question_data: dict[str, Any], 
    num_runs: int = NUM_RUNS_PER_QUESTION,
    model: str = "anthropic/claude-opus-4.5"
) -> dict[str, Any]:
    """
    Generate a forecast for a custom question.
    
    Returns:
        Dictionary containing forecast, payload, comment, and credit usage
    """
    question_type = question_data["type"]
    
    print(f"\n{'='*80}")
    print(f"Forecasting custom {question_type} question")
    print(f"Title: {question_data['title']}")
    print(f"Model: {model}")
    print(f"Number of runs: {num_runs}")
    print(f"{'='*80}\n")
    
    # Reset credit tracking for this question
    reset_credit_tracking()
    
    # Generate forecast based on question type
    if question_type == "binary":
        forecast, comment = await get_binary_gpt_prediction(question_data, num_runs)
        
    elif question_type == "numeric":
        forecast, comment = await get_numeric_gpt_prediction(question_data, num_runs)
        
    elif question_type == "discrete":
        forecast, comment = await get_numeric_gpt_prediction(question_data, num_runs)
        
    elif question_type == "multiple_choice":
        forecast, comment = await get_multiple_choice_gpt_prediction(question_data, num_runs)
    
    else:
        raise ValueError(f"Unknown question type: {question_type}")
    
    # Create the payload that would be sent to Metaculus
    forecast_payload = create_forecast_payload(forecast, question_type)
    
    # Get credit summary
    credit_summary = get_credit_summary(model)
    
    # Prepare result
    result = {
        "timestamp": datetime.datetime.now().isoformat(),
        "question_title": question_data["title"],
        "question_type": question_type,
        "num_runs": num_runs,
        "model_used": model,
        "forecast": forecast,
        "forecast_payload": forecast_payload,
        "comment": comment,
        "question_data": question_data,
        "credit_usage": credit_summary,
    }
    
    return result


async def main(
    input_filename: str, 
    output_file: str = None, 
    num_runs: int = NUM_RUNS_PER_QUESTION,
    model: str = "anthropic/claude-opus-4.5"
):
    """
    Main function to forecast a custom question and save results.
    
    Args:
        input_filename: Name of JSON file in input_questions/ folder (e.g., "my_question.json")
        output_file: Path to output JSON file (optional, auto-generated if not provided)
        num_runs: Number of LLM runs for median aggregation
        model: OpenRouter model to use
    """
    print(f"Loading question from: input_questions/{input_filename}")
    
    try:
        question_data = load_question_from_file(input_filename)
        print("✓ Question data loaded and validated successfully")
    except ValueError as e:
        print(f"✗ Error loading question: {e}")
        return
    
    try:
        result = await forecast_custom_question(question_data, num_runs, model)
        print("\n✓ Forecast generated successfully")
        
        # Create output directory
        output_dir = Path("test_results")
        output_dir.mkdir(exist_ok=True)
        
        # Generate output filename if not provided
        if output_file is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            question_type = question_data["type"]
            # Use input filename (without .json) as base for output
            input_base = Path(input_filename).stem
            output_file = output_dir / f"forecast_{input_base}_{timestamp}.json"
        else:
            output_file = output_dir / Path(output_file).name
        
        # Save results
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"\n✓ Results saved to: {output_file}")
        print(f"\nForecast Summary:")
        print(f"  Type: {result['question_type']}")
        if result['question_type'] in ['numeric', 'discrete']:
            print(f"  Forecast (CDF): {str(result['forecast'])[:100]}...")
        else:
            print(f"  Forecast: {result['forecast']}")
        print(f"  Comment length: {len(result['comment'])} characters")
        
        # Display credit usage
        print(f"\n{'='*80}")
        print(f"CREDIT USAGE SUMMARY")
        print(f"{'='*80}")
        credit = result['credit_usage']
        print(f"  Model: {credit['model']}")
        print(f"  Total API calls: {credit['total_api_calls']}")
        print(f"  Input tokens: {credit['input_tokens']:,}")
        print(f"  Output tokens: {credit['output_tokens']:,}")
        print(f"  Total tokens: {credit['total_tokens']:,}")
        print(f"  Input cost: ${credit['input_cost_usd']:.4f}")
        print(f"  Output cost: ${credit['output_cost_usd']:.4f}")
        print(f"  TOTAL COST: ${credit['total_cost_usd']:.4f}")
        print(f"{'='*80}\n")
        
    except Exception as e:
        print(f"\n✗ Error during forecasting: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Forecast a custom Metaculus-style question with credit tracking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python forecast_custom_question.py my_question.json
  python forecast_custom_question.py unsc_ai_meeting.json --output my_forecast.json
  python forecast_custom_question.py china_us_hotline.json --num-runs 3
  python forecast_custom_question.py my_question.json --model anthropic/claude-sonnet-4.5

Note: All input files should be placed in the 'input_questions/' folder.
      Output files will be saved to the 'test_results/' folder.
        """
    )
    
    parser.add_argument(
        "input_filename",
        type=str,
        help="Name of JSON file in input_questions/ folder (e.g., 'my_question.json')"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output filename (saved in test_results/). If not specified, auto-generated based on input filename."
    )
    
    parser.add_argument(
        "--num-runs",
        type=int,
        default=NUM_RUNS_PER_QUESTION,
        help=f"Number of LLM runs per question (default: {NUM_RUNS_PER_QUESTION})"
    )
    
    parser.add_argument(
        "--model",
        type=str,
        default="anthropic/claude-opus-4.5",
        choices=[
            "anthropic/claude-opus-4.5",
            "anthropic/claude-sonnet-4.5",
            "anthropic/claude-haiku-4.5"
        ],
        help="OpenRouter model to use (default: claude-opus-4.5)"
    )
    
    args = parser.parse_args()
    
    asyncio.run(main(args.input_filename, args.output, args.num_runs, args.model))