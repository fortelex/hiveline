import datetime

import pymongo.errors

from hiveline import get_database
from hiveline.jobs.jobs import JobsDataSource, JobStatus


class MongoJob:
    """
    A calculation job of some sort. Used to track the status of a job. A job is uniquely identified by the key (
    service_name, sim_id, job_id)

    :param service_name: the name of the service
    :param sim_id: the simulation ID
    :param job_id: the job ID
    :param status: the job status
    """

    service_name: str
    sim_id: str | None = None
    job_id: str | None = None
    status: str | None = None
    created: datetime.datetime | None = None
    started: datetime.datetime | None = None
    finished: datetime.datetime | None = None
    error: str | None = None

    def __init__(self, service_name: str, sim_id: str | None = None, job_id: str | None = None,
                 status: str | None = None, created: datetime.datetime | None = None,
                 started: datetime.datetime | None = None, finished: datetime.datetime | None = None,
                 error: str | None = None):
        self.service_name = service_name
        self.sim_id = sim_id
        self.job_id = job_id
        self.status = status
        self.created = created
        self.started = started
        self.finished = finished
        self.error = error

    def to_dict(self):
        return {
            "service-name": self.service_name,
            "sim-id": self.sim_id,
            "job-id": self.job_id,
            "status": self.status,
            "created": self.created,
            "started": self.started,
            "finished": self.finished,
            "error": self.error
        }

    @staticmethod
    def from_dict(d: dict):
        return MongoJob(
            service_name=d["service-name"],
            sim_id=d["sim-id"],
            job_id=d["job-id"],
            status=d["status"],
            created=d["created"],
            started=d["started"],
            finished=d["finished"],
            error=d["error"]
        )


class MongoJobsDataSource(JobsDataSource):
    def __init__(self, db=None):
        self.db = db
        if self.db is None:
            self.db = get_database()
        self.coll = self.db["jobs"]

    def create_jobs(self, sim_id: str, service_name: str, job_ids: list[str]):
        for job_id in job_ids:
            try:
                self.coll.insert_one(MongoJob(
                    service_name=service_name,
                    sim_id=sim_id,
                    job_id=job_id,
                    status="pending",
                    created=datetime.datetime.now()
                ).to_dict())
            except pymongo.errors.DuplicateKeyError:
                pass

    def reset_jobs(self, sim_id: str, service_name: str, status: list[JobStatus] = None, max_started_date=None):
        jobs_filter = {
            "service-name": service_name,
            "sim-id": sim_id
        }

        if status is not None:
            jobs_filter["status"] = {
                "$in": [str(s) for s in status]
            }

        if max_started_date is not None:
            jobs_filter["started"] = {
                "$lte": max_started_date
            }

        self.coll.update_many(jobs_filter, {
            "$set": {
                "status": "pending"
            },
            "$unset": {
                "error": "",
                "started": "",
                "finished": ""
            }
        })

    def pop_job(self, sim_id: str, service_name: str) -> str | None:
        job = self.coll.find_one_and_update({
            "service-name": service_name,
            "sim-id": sim_id,
            "status": "pending"
        }, {
            "$set": {
                "status": "started",
                "started": datetime.datetime.now()
            }
        })
        return job["job-id"] if job is not None else None

    def update_job(self, sim_id: str, service_name: str, job_id: str, status: JobStatus, error: str | None = None):
        update = {
            "$set": {
                "status": str(status),
                "finished": datetime.datetime.now()
            }
        }

        if error is not None:
            update["$set"]["error"] = error

        if status == JobStatus.STARTED:
            update["$set"]["started"] = datetime.datetime.now()

        if status == JobStatus.FINISHED or status == JobStatus.FAILED:
            update["$set"]["finished"] = datetime.datetime.now()

        self.coll.update_one({
            "service-name": service_name,
            "sim-id": sim_id,
            "job-id": job_id
        }, update)

    def count_jobs(self, sim_id: str, service_name: str, status: JobStatus = None) -> int:
        jobs_filter = {
            "service-name": service_name,
            "sim-id": sim_id
        }

        if status is not None:
            jobs_filter["status"] = str(status)

        return self.coll.count_documents(jobs_filter)

    def delete_jobs(self, sim_id: str, service_name: str):
        self.coll.delete_many({
            "service-name": service_name,
            "sim-id": sim_id
        })
