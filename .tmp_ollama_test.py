from chatbot.ollama import OllamaClient
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import traceback

client = OllamaClient(timeout_seconds=90)
print("is_available:", client.is_available(), flush=True)
print("list_models:", client.list_models(), flush=True)

with ThreadPoolExecutor(max_workers=1) as ex:
    fut = ex.submit(client.generate, "ඔබට කොහොමද?", "llama3.2:3b")
    try:
        result = fut.result(timeout=75)
        print("generate_success:", True, flush=True)
        print("generate_output:", result, flush=True)
    except FutureTimeoutError as e:
        print("generate_success:", False, flush=True)
        print("generate_error_type:", type(e).__name__, flush=True)
        print("generate_error:", str(e), flush=True)
    except Exception as e:
        print("generate_success:", False, flush=True)
        print("generate_error_type:", type(e).__name__, flush=True)
        print("generate_error:", str(e), flush=True)
        traceback.print_exc()
