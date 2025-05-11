from openai import OpenAI

client = OpenAI(api_key="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")

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}]
)

print(response.choices[0].message.content)
