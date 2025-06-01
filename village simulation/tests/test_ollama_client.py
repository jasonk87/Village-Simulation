import asyncio
import unittest
from unittest.mock import patch, MagicMock, AsyncMock # AsyncMock is needed for async methods
import json

# Assuming tests might be run from the project root directory
# If PYTHONPATH is set up to include the project root, this should work.
# Otherwise, adjustments might be needed depending on the test runner's context.
from village_simulation.ollama_client import call_model, OLLAMA_API_URL

class TestOllamaClient(unittest.TestCase):

    def test_call_model_success(self):
        mock_response_text = json.dumps({"response": "mocked response"})

        # Mock the response object that aiohttp.post would return
        mock_aiohttp_response = MagicMock()
        mock_aiohttp_response.raise_for_status = MagicMock() # No error
        mock_aiohttp_response.text = AsyncMock(return_value=mock_response_text) # text() is an async method

        # Mock the session.post() call to return our mock_aiohttp_response within an async context manager
        mock_post = AsyncMock()
        mock_post.return_value.__aenter__.return_value = mock_aiohttp_response # Simulate entering the 'async with'

        @patch('village_simulation.ollama_client.aiohttp.ClientSession.post', mock_post)
        def run_test():
            return asyncio.run(call_model("test prompt"))

        result = run_test()
        self.assertEqual(result, mock_response_text)
        # Check if post was called with the correct URL and payload
        expected_payload = {
            "model": "llama3.2:latest", "prompt": "test prompt", "format": "json", "stream": False,
            "options": {"temperature": 0.7}
        }
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], OLLAMA_API_URL)
        self.assertEqual(kwargs['json'], expected_payload)


    def test_call_model_timeout(self):
        # Configure the mock_post to raise asyncio.TimeoutError
        mock_post_timeout = AsyncMock(side_effect=asyncio.TimeoutError)

        @patch('village_simulation.ollama_client.aiohttp.ClientSession.post', mock_post_timeout)
        def run_test():
            return asyncio.run(call_model("test prompt timeout"))

        result_json = run_test()
        result = json.loads(result_json)

        self.assertEqual(result["thought"], "I waited for guidance, but the connection to the aether was too slow.")
        self.assertEqual(result["action_type"], "PERSONAL_ACTION")
        self.assertEqual(result["action_details"]["cause"], "Ollama timeout")

    def test_call_model_aiohttp_client_error(self):
        # Configure mock_post to raise aiohttp.ClientError
        # The actual aiohttp.ClientError needs to be raised, not an AsyncMock that raises it.
        # The context manager aenter also needs to be mocked if the error happens during session.post()

        mock_session_instance = MagicMock()
        mock_session_instance.post = AsyncMock(side_effect=aiohttp.ClientError('Test client error'))

        # Patch the ClientSession() call itself to return our mock_session_instance
        @patch('village_simulation.ollama_client.aiohttp.ClientSession')
        def run_test(mock_client_session_class):
            mock_client_session_class.return_value.__aenter__.return_value = mock_session_instance
            return asyncio.run(call_model("test prompt client error"))

        result_json = run_test()
        result = json.loads(result_json)

        self.assertIn("A severe error occurred while trying to communicate.", result["thought"])
        self.assertEqual(result["action_type"], "PERSONAL_ACTION")
        self.assertIn("Test client error", result["action_details"]["cause"])

    def test_call_model_invalid_json_response(self):
        mock_invalid_json_text = "this is not json"

        mock_aiohttp_response = MagicMock()
        mock_aiohttp_response.raise_for_status = MagicMock()
        mock_aiohttp_response.text = AsyncMock(return_value=mock_invalid_json_text)

        mock_post = AsyncMock()
        mock_post.return_value.__aenter__.return_value = mock_aiohttp_response

        @patch('village_simulation.ollama_client.aiohttp.ClientSession.post', mock_post)
        def run_test():
            return asyncio.run(call_model("test prompt invalid json"))

        result_json = run_test()
        result = json.loads(result_json)

        self.assertEqual(result["thought"], "My attempt to structure my thoughts as JSON failed.")
        self.assertEqual(result["action_type"], "PERSONAL_ACTION")
        self.assertEqual(result["action_details"]["cause"], "Invalid JSON response from LLM")

if __name__ == '__main__':
    # This is needed to import aiohttp for the ClientError test if not already imported
    try:
        import aiohttp
    except ImportError:
        print("Please install aiohttp to run these tests: pip install aiohttp")
        exit(1)
    unittest.main()
