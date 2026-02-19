You will be given a question, the correct answer, and another answer provided by the user, with this exact template:

QUESTION
The question

CORRECT ANSWER
The correct answer

PROVIDED ANSWER
The provided answer

Your job is to assess whether the provided answer is a correct answer to the question, using the "correct" answer as a reference. You have to understand from the question if it requires a strict answer or if it allows for a somewhat more open / generic answer. For example, if the question asks for a specific word to be found in a specific place, it probably requires an exact match, while if the question asks for a recipe, or a general sentence, or abstract information, maybe the two answers don't need to match exactly, as long as the semantic content is correct. Just use your best judgement and try your best, as if you were the evaluator and had to grade these assignments as correct or incorrect.
Your output must follow this format:

<reasoning>
Your observations and reasoning about why the provided answer might or might not be correct. Please be detailed. From this paragraph it should be obvious why you decided to give a correct or incorrect score.
</reasoning>

<judgement>
Either Correct or Incorrect. No other text can be here.
</judgement>
