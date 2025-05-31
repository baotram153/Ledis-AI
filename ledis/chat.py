from dotenv import load_dotenv
import os 

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

from google import genai
from google.genai import types

from ledis.chat_utils.prompt import FEW_SHOT_PROMPT

class LedisChat:
    """
    LedisChat is a class that interacts with the Gemini AI model to translate natural language commands
    into Ledis commands using few-shot prompting.
    """
    def __init__(self):
        """
        Initialize the LedisChat instance with the Gemini client.
        """
        if not API_KEY:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
        
        # initialize Gemini client with the API key
        self.client = genai.Client(api_key=API_KEY)
    

    # ------------------- SEND FEW SHOT PROMPT TO GEMINI -------------------
    def _query_gemini(self, prompt: str) -> str:
        prompt = FEW_SHOT_PROMPT.format(user_nl_command=prompt)
        response = self.client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
            max_output_tokens=512,
            temperature=0.0
            )
        )
        raw = response.text.strip()
        return raw

    def _parse_gemini_response(self, response: str) -> tuple[str, list[str]]:
        """
        Parse the response from Gemini into command and values.
        TODO: Implement something to reduce the risk of deleting the data store.
        """
        return response
        
    
    def translate(self, user_input: str) -> tuple[str, list[str]]:
        """
        Translate the user input into Ledis commands and execute them.
        """
        response = self._query_gemini(user_input)
        command = self._parse_gemini_response(response)
        
        if not command:
            raise ValueError("Failed to parse command from Gemini response.")

        return command


if __name__ == "__main__":
    chatbot = LedisChat()
    
    user_input = "CHAT 'Add pencil and eraser to my stationery list'"
    print("User Input:", user_input)
    print("Result:", chatbot.translate(user_input))
    
    user_input = "CHAT 'What is stored at key stationery_list?'"
    print("User Input:", user_input)
    print("Result:", chatbot.translate(user_input))
    
    user_input = "CHAT 'Show me the first item of my stationery list'"
    print("User Input:", user_input)
    print("Result:", chatbot.translate(user_input))
    
    user_input = "CHAT 'Delete my stationery list'"
    print("User Input:", user_input)
    print("Result", chatbot.translate(user_input))
    
    user_input = "CHAT 'How many items are in my stationery list?'"
    print("User Input:", user_input)
    print("Result:", chatbot.translate(user_input))