from prompt_toolkit.completion import Completer, Completion
from sql_autofill import generate_suggestions


class SQLCompleter(Completer):

    def __init__(self, schema_text):
        self.schema_text = schema_text

    def get_completions(self, document, complete_event):
        text = document.text

        if not text.endswith("?"):
            return

        suggestions = generate_suggestions(text, self.schema_text)

        for suggestion in suggestions:
            yield Completion(
                suggestion,
                start_position=-1  # only replace '?'
            )
