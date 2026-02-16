import asyncio
import json
import os
from pathlib import Path
from pprint import pprint

# import directly from your bot
from forecasting_bot import (
    EXAMPLE_QUESTIONS,
    get_post_details,
    get_binary_gpt_prediction,
    get_numeric_gpt_prediction,
    get_multiple_choice_gpt_prediction,
    create_forecast_payload,
    NUM_RUNS_PER_QUESTION,
)


async def inspect_and_save_forecast(question_id: int, post_id: int, output_dir: Path):
    print("\n" + "=" * 80)
    print(f"POST ID: {post_id} | QUESTION ID: {question_id}")
    print("Getting details for https://www.metaculus.com/api/posts/{}/".format(post_id))

    # Pull real Metaculus data
    post_details = await get_post_details(post_id)
    question = post_details["question"]
    
    print("\n--- QUESTION INFO ---")
    print(f"Title: {question.get('title')}")
    print(f"Type: {question.get('type')}")
    print(f"Status: {question.get('status')}")
    
    question_type = question.get('type')
    
    # Generate forecast based on question type
    print(f"\n--- GENERATING FORECAST FOR {question_type.upper()} QUESTION ---")
    
    if question_type == "binary":
        forecast, comment = await get_binary_gpt_prediction(question, NUM_RUNS_PER_QUESTION)
        forecast_payload = create_forecast_payload(forecast, question_type)
        
    elif question_type == "numeric":
        forecast, comment = await get_numeric_gpt_prediction(question, NUM_RUNS_PER_QUESTION)
        forecast_payload = create_forecast_payload(forecast, question_type)
        
    elif question_type == "discrete":
        forecast, comment = await get_numeric_gpt_prediction(question, NUM_RUNS_PER_QUESTION)
        forecast_payload = create_forecast_payload(forecast, question_type)
        
    elif question_type == "multiple_choice":
        forecast, comment = await get_multiple_choice_gpt_prediction(question, NUM_RUNS_PER_QUESTION)
        forecast_payload = create_forecast_payload(forecast, question_type)
        
    else:
        print(f"Unknown question type: {question_type}")
        return None
    
    # Prepare data to save
    forecast_data = {
        "question_id": question_id,
        "post_id": post_id,
        "question_type": question_type,
        "question_title": question.get('title'),
        "question_url": f"https://www.metaculus.com/questions/{post_id}/",
        "forecast": forecast,
        "forecast_payload": forecast_payload,
        "comment": comment,
        "post_details": post_details,
    }
    
    # Save to file
    filename = output_dir / f"forecast_{question_type}.json"
    with open(filename, 'w') as f:
        json.dump(forecast_data, f, indent=2)
    
    print(f"\n✓ Saved {question_type} forecast to {filename}")
    print(f"Forecast preview: {str(forecast)[:200]}...")
    print(f"Comment preview: {comment[:200]}...")
    
    return question_type


async def main():
    print("Generating forecasts and saving by question type\n")
    
    # Create output directory
    output_dir = Path("forecast_types")
    output_dir.mkdir(exist_ok=True)
    print(f"Output directory: {output_dir.absolute()}\n")

    # Track which types we've already saved
    saved_types = set()

    for question_id, post_id in EXAMPLE_QUESTIONS:
        try:
            question_type = await inspect_and_save_forecast(question_id, post_id, output_dir)
            
            if question_type and question_type not in saved_types:
                saved_types.add(question_type)
                print(f"\n✓ First {question_type} question saved!")
            elif question_type:
                print(f"\n✓ Another {question_type} question saved (overwriting previous)")
                
        except Exception as e:
            print(f"\n✗ Error processing question {question_id}: {e}")
            continue
        
    print("\n" + "=" * 80)
    print(f"DONE - Saved {len(saved_types)} question types: {saved_types}")
    print(f"All files saved in: {output_dir.absolute()}")


if __name__ == "__main__":
    asyncio.run(main())
