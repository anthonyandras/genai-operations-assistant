from ops_assistant.bedrock_client import (
    BedrockInferenceClient,
)

def main():
    client = BedrockInferenceClient()

    print("\nMODEL RESPONSE\n")
    result = client.generate(
        "A fictional production API has elevated "
        "HTTP 500 errors after a deployment. "
        "Give three safe diagnostic steps. "
        "Do not pretend to have accessed any systems.",
        on_text=lambda text: print(text, end="", flush=True),
    )
    print()

    print("\nINFERENCE METRICS\n")
    print(result.model_dump_json(indent=2, exclude={"text"}))


if __name__ == "__main__":
    main()
