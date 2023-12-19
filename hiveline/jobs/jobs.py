import datetime
import threading
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Callable


class JobStatus(Enum):
    PENDING = "pending"
    STARTED = "started"
    FINISHED = "finished"
    FAILED = "failed"

    def __str__(self):
        return self.value

    def __repr__(self):
        return self.value

    def to_str(self):
        return self.value

    @staticmethod
    def from_str(s: str):
        if s == "pending":
            return JobStatus.PENDING
        elif s == "started":
            return JobStatus.STARTED
        elif s == "finished":
            return JobStatus.FINISHED
        elif s == "failed":
            return JobStatus.FAILED
        else:
            raise ValueError(f"Invalid job status: {s}")


class JobsDataSource(ABC):
    @abstractmethod
    def create_jobs(self, sim_id: str, service_name: str, job_ids: list[str]):
        """
        Creates the jobs in the data source. If the job already exists (uniquely identified by service_name, sim_id, job_id),
        it is not created again. Use reset_jobs and reset_failed_jobs to reset the status of existing jobs.
        :param sim_id: the simulation ID
        :param service_name: the name of the service
        :param job_ids: the job IDs
        :return:
        """
        pass

    @abstractmethod
    def reset_jobs(self, sim_id: str, service_name: str, status: list[JobStatus] = None,
                   max_started_date: datetime.datetime = None):
        """
        Resets the status of the jobs to pending. If status is not None, only jobs with the specified status are reset.
        :param sim_id: the simulation ID
        :param service_name: the name of the service
        :param status: (optional) the status of the jobs to reset
        :param max_started_date: (optional) the maximum started date of the jobs to reset
        :return:
        """
        pass

    @abstractmethod
    def pop_job(self, sim_id: str, service_name: str) -> str | None:
        """
        Pops a job from the data source. If no job is available, returns None. It will automatically set the status of
        the job to "started".
        :param sim_id: the simulation ID
        :param service_name: the name of the service
        :return: the job ID or None if no job is available
        """
        pass

    @abstractmethod
    def update_job(self, sim_id: str, service_name: str, job_id: str, status: JobStatus, error: str | None = None):
        """
        Updates the status of a job.
        :param sim_id: the simulation ID
        :param service_name: the name of the service
        :param job_id: the job ID
        :param status: the new status
        :param error: (optional) the error message
        :return:
        """
        pass

    @abstractmethod
    def count_jobs(self, sim_id: str, service_name: str, status: JobStatus = None) -> int:
        """
        Counts the number of jobs. If status is not None, only jobs with the specified status are counted.
        :param sim_id: the simulation ID
        :param service_name: the name of the service
        :param status: (optional) the status of the jobs to count
        :return:
        """
        pass

    @abstractmethod
    def delete_jobs(self, sim_id: str, service_name: str):
        """
        Deletes all jobs for a simulation.
        :param sim_id: the simulation ID
        :param service_name: the name of the service
        :return:
        """
        pass


class JobHandler:
    def __init__(self, service_name: str, sim_id: str, data_source: JobsDataSource):
        self.service_name = service_name
        self.sim_id = sim_id
        self.data_source = data_source

    def create_jobs(self, job_ids: list[str]):
        self.data_source.create_jobs(self.sim_id, self.service_name, job_ids)

    def reset_jobs(self):
        self.data_source.reset_jobs(self.sim_id, self.service_name)

    def reset_timed_out_jobs(self):
        self.data_source.reset_jobs(self.sim_id, self.service_name, status=[JobStatus.STARTED],
                                    max_started_date=datetime.datetime.now() - datetime.timedelta(minutes=5))

    def reset_failed_jobs(self):
        self.data_source.reset_jobs(self.sim_id, self.service_name, status=[JobStatus.FAILED])

    def iterate_jobs(self, handler: Callable[[str], None], threads=4, debug_progress=True, max_consecutive_errors=5):
        if threads > 1:
            self._spawn_threads(handler, threads, debug_progress, max_consecutive_errors)
            return

        self._iterate_jobs(handler, debug_progress, max_consecutive_errors)

    def _spawn_threads(self, handler: Callable[[str], None], num_threads=4, debug_progress=True,
                       max_consecutive_errors=5):
        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=self._iterate_jobs,
                                 args=(handler, debug_progress and i == 0, max_consecutive_errors))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

    def _iterate_jobs(self, handler: Callable[[str], None], debug_progress=True, max_consecutive_errors=5):
        # get the total number of jobs
        total_jobs = 0
        if debug_progress:
            total_jobs = self.data_source.count_jobs(self.sim_id, self.service_name, status=JobStatus.PENDING)

        # by default, we will not stop the process if there is one error, but if there are multiple consecutive errors,
        # we will stop the process
        consecutive_error_number = 0

        last_print = 0

        while True:
            job_id = self.data_source.pop_job(self.sim_id, self.service_name)
            if job_id is None:
                break

            current_time = time.time()
            if debug_progress and current_time - last_print > 1:
                last_print = current_time
                pending_jobs = self.data_source.count_jobs(self.sim_id, self.service_name, status=JobStatus.PENDING)
                print("Progress: ~{:.2f}% {:}".format(100 * (1 - pending_jobs / total_jobs), job_id))

            try:
                handler(job_id)

                consecutive_error_number = 0

                self.data_source.update_job(self.sim_id, self.service_name, job_id, JobStatus.FINISHED)
            except Exception as e:
                consecutive_error_number += 1
                print(f"Error processing job {job_id}: {e}")

                # set status to failed
                self.data_source.update_job(self.sim_id, self.service_name, job_id, JobStatus.FAILED, str(e))

                if consecutive_error_number > max_consecutive_errors:
                    raise e

    def count_jobs(self, status):
        return self.data_source.count_jobs(self.sim_id, self.service_name, status=status)
