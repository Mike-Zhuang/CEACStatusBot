import signal
import time
import uuid

from .case_service import claimNextQueryJob, migrateEncryptedFields, runQueryJob
from .config import getSettings
from .database import initializeDatabase
from .secrets import getCredentialMasterKey


shouldStop = False


def handleStopSignal(_signum, _frame) -> None:
    global shouldStop
    shouldStop = True


def main() -> None:
    settings = getSettings()
    workerId = f"ceac-worker-{uuid.uuid4()}"
    getCredentialMasterKey()
    initializeDatabase()
    migrateEncryptedFields()
    signal.signal(signal.SIGTERM, handleStopSignal)
    signal.signal(signal.SIGINT, handleStopSignal)
    print(f"[worker] started {workerId}")
    while not shouldStop:
        job = claimNextQueryJob(workerId)
        if not job:
            time.sleep(settings.workerPollIntervalSeconds)
            continue
        print(f"[worker] running job={job['id']} case={job['caseId']} trigger={job['triggerType']}")
        completed = runQueryJob(job)
        print(f"[worker] completed job={completed['id']} status={completed['status']}")
    print(f"[worker] stopped {workerId}")


if __name__ == "__main__":
    main()
