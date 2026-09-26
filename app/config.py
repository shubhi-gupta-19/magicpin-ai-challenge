import os

class Settings:
    TEAM_NAME: str = os.getenv("TEAM_NAME", "Team Vera")
    TEAM_MEMBERS: list[str] = ["magicpin AI Candidate"]
    MODEL: str = os.getenv("MODEL_NAME", "vera-deterministic-composer-v1")
    APPROACH: str = os.getenv(
        "APPROACH_DESCRIPTION",
        "4-context deterministic composer with vertical-specific strategies and multi-turn state machine"
    )
    CONTACT_EMAIL: str = os.getenv("CONTACT_EMAIL", "candidate@magicpin.ai")
    VERSION: str = "1.0.0"
    SUBMITTED_AT: str = "2026-04-26T08:00:00Z"
    
    # Dataset Paths
    EXPANDED_DIR: str = os.getenv("EXPANDED_DIR", "expanded")
    DATASET_DIR: str = os.getenv("DATASET_DIR", "dataset")

settings = Settings()
