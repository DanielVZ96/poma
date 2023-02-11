import os
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")


def anwser(query: str, context: str):
    prompt = f"""
I am a highly intelligent question answering bot. If you ask me a question that is rooted in truth, I will give you the answer. If you ask me a question that is nonsense, trickery, or has no clear answer, I will respond with "Unknown". If you give me context, I will use it to answer. The question might be in a non-english language, and I'll answer.

Q: What is human life expectancy in the United States?
A: Human life expectancy in the United States is 78 years.

C: Dwight D. Eisenhower ruled the United States from 1953 to 1961.
Q: Who was president of the United States in 1955?
A: Dwight D. Eisenhower was president of the United States in 1955.

Q: Which party did he belong to?
A: He belonged to the Republican Party.

Q: What is the square root of banana?
A: Unknown

C: Telescopes work by using mirrors and lenses.
Q: How does a telescope work?
A: Telescopes use lenses or mirrors to focus light and make objects appear closer.

Q: Donde se realizaron las olimpiadas de 1992?
A: Las olimpiadas de 1992 se realizaron en Barcelona, España.

Q: How many squigs are in a bonk?
A: Unknown

Context: \"\"\"
{context}
\"\"\"

Based only in the above context, and without adding any other information that's not in the context above, answer the following question in at least two and at most 6 sentences of a single paragraph:

Q: {query}
A:
    """
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=prompt,
        temperature=0.5,
        max_tokens=500,
        frequency_penalty=1,
        presence_penalty=1,
        echo=False,
    )
    text = response.get("choices", [None])[0]
    if text is None:
        return ""
    return text["text"]
