import json
import requests # For making HTTP requests to Ollama

# Define your Ollama API endpoint
OLLAMA_API_URL = "http://localhost:11434/api/generate"

def call_model(prompt_text, model_name="llama3.2:latest", temperature=0.7):
    """
    Sends a prompt to a local LLM via the Ollama API and returns the JSON response.
    """
    # print(f"\n--- OLLAMA CLIENT (Attempting Call to {model_name}) ---") # Less verbose

    payload = {
        "model": model_name,
        "prompt": prompt_text,
        "format": "json",
        "stream": False,
        "options": {
            "temperature": temperature,
        }
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=90)
        response.raise_for_status()
        json_response_string = response.text
        try:
            json.loads(json_response_string)
            # print(f"Raw JSON from Ollama: {json_response_string[:100].strip()}...") # Keep this commented unless debugging
            return json_response_string
        except json.JSONDecodeError as e:
            print(f"!!! Game Warning: The spirits' message was garbled (Invalid JSON from LLM {model_name}): {e}")
            print(f"    Received: {json_response_string[:300]}...") # Show what was received for diagnosis
            error_action = {
                "thought": "My attempt to structure my thoughts as JSON failed.",
                "action_type": "PERSONAL_ACTION",
                "action_details": {"activity": "error_idle", "cause": "Invalid JSON response from LLM"},
                "speech": "I... seem to have stumbled in my thoughts."
            }
            return json.dumps(error_action)

    except requests.exceptions.Timeout:
        print(f"!!! Game Warning: The spirits seem distant... (Ollama call timed out for '{model_name}')")
        error_action = {
            "thought": "I waited for guidance, but the connection to the aether was too slow.",
            "action_type": "PERSONAL_ACTION",
            "action_details": {"activity": "error_idle", "cause": "Ollama timeout"},
            "speech": "The spirits... are quiet today."
        }
        return json.dumps(error_action)
    except requests.exceptions.RequestException as e:
        print(f"!!! Game Warning: A powerful interference disrupts contact with the spirits! (Ollama API Error for {model_name}): {e}")
        error_action = {
            "thought": f"A severe error occurred while trying to communicate. Details: {str(e)}",
            "action_type": "PERSONAL_ACTION",
            "action_details": {"activity": "error_idle", "cause": str(e)},
            "speech": "The connection to the guiding voices is broken!"
        }
        return json.dumps(error_action)
    # finally:
        # print(f"--- OLLAMA CLIENT (Call Attempt Finished for {model_name}) ---") # Less verbose

if __name__ == '__main__':
    print("Executing direct test of ollama_client.py...")
    example_prompt = """
You are TestAgent007. Respond ONLY in JSON format like this:
{"thought": "This is a test thought.", "action_type": "PERSONAL_ACTION", "action_details": {"activity": "observe"}, "speech": "Testing, 1, 2, 3."}"""
    test_model = "llama3.2:latest" # <--- CHANGE THIS IF NEEDED! (e.g., "mistral")
    print(f"\nAttempting test call with model: '{test_model}'...")
    json_response = call_model(example_prompt, model_name=test_model, temperature=0.6)
    print("\n--- Parsed Test Response from Ollama ---")
    try:
        parsed = json.loads(json_response)
        print(json.dumps(parsed, indent=2))
    except json.JSONDecodeError:
        print(f"Error: Test response was not valid JSON.\nRaw response: {json_response}")
    print("--------------------------------------")