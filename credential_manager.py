# credential_manager.py
import json
import os

class CredentialManager:
    _instance = None
    _credential_file = "credentials.json"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CredentialManager, cls).__new__(cls)
            cls._instance._load_or_initialize()
        return cls._instance

    def _load_or_initialize(self):
        if not os.path.exists(self._credential_file):
            self.credentials = {
                "NEO4J_URI": "",
                "NEO4J_USERNAME": "",
                "NEO4J_PASSWORD": "",
                "INSTAGRAM_USERNAME": "",
                "INSTAGRAM_USER_AGENT": ""
            }
            self._save()
        else:
            with open(self._credential_file, "r") as f:
                self.credentials = json.load(f)
    def reset(self):
        self.credentials = {
            "NEO4J_URI": "",
            "NEO4J_USERNAME": "",
            "NEO4J_PASSWORD": "",
            "INSTAGRAM_USERNAME": "",
            "INSTAGRAM_USER_AGENT": ""
        }
        self._save()

    def _save(self):
        with open(self._credential_file, "w") as f:
            json.dump(self.credentials, f, indent=4)

    def get(self, key):
        return self.credentials.get(key, "")

    def set(self, key, value):
        self.credentials[key] = value
        self._save()
