## run.py
import json
from dotenv import load_dotenv
load_dotenv()
 
from models.schemas import SessionInput, Depth
from core.orchestrator import Orchestrator
 
 
def main():
    session = SessionInput(
        topic="Impact of large language models on cybersecurity",
        depth=Depth.STANDARD,
        admin_webhook=None   # set to Slack webhook URL to enable alerts
    )
 
    print(f"Starting session: {session.topic}")
    print(f"Depth: {session.depth.value}\n")
 
    orchestrator = Orchestrator(session)
    summary = orchestrator.run()
 
    print("\n── Session Complete ──")
    print(json.dumps(summary, indent=2))
 
 
if __name__ == "__main__":
    main()