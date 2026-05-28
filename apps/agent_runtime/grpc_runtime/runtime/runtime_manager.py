from apps.agent_runtime.agents.supervisor.intent_classifier import (
    IntentClassifier,
)


class RuntimeManager:

    def __init__(self):

        self.intent_classifier = IntentClassifier()


runtime_manager = RuntimeManager()
