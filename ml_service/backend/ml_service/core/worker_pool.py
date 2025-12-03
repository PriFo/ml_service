"""Worker pool system for parallel job execution"""
import logging
import uuid
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass, field

from ml_service.db.repositories import JobRepository
from ml_service.db.models import Job

logger = logging.getLogger(__name__)


class WorkerStatus(Enum):
    """Worker status"""
    IDLE = "idle"
    RUNNING = "running"


@dataclass
class Worker:
    """Represents a single worker"""
    worker_id: str
    model_key: str
    status: WorkerStatus = WorkerStatus.IDLE
    current_job: Optional[Job] = None
    created_at: datetime = field(default_factory=datetime.now)


class WorkerPool:
    """Pool of workers for a specific model"""
    
    def __init__(self, model_key: str, max_workers: int = 5):
        self.model_key = model_key
        self.max_workers = max_workers
        self.workers: List[Worker] = []
        self.pending_jobs: List[Job] = []
        
        # Initialize workers
        for i in range(max_workers):
            worker = Worker(
                worker_id=f"{model_key}_worker_{i}_{uuid.uuid4().hex[:8]}",
                model_key=model_key
            )
            self.workers.append(worker)
    
    def get_idle_worker(self) -> Optional[Worker]:
        """Get first idle worker"""
        for worker in self.workers:
            if worker.status == WorkerStatus.IDLE:
                return worker
        return None
    
    def get_worker_by_id(self, worker_id: str) -> Optional[Worker]:
        """Get worker by ID"""
        for worker in self.workers:
            if worker.worker_id == worker_id:
                return worker
        return None
    
    def distribute_job(self, job: Job) -> bool:
        """
        Distribute job to a worker or add to pending queue.
        
        Returns: True if job was assigned, False if added to pending
        """
        # Check if dataset is large (> 100,000 rows)
        dataset_size = job.dataset_size or 0
        
        if dataset_size > 100000:
            # Large dataset - will be handled separately
            logger.info(f"Large dataset detected ({dataset_size} rows) for job {job.job_id}")
            self.pending_jobs.append(job)
            return False
        
        # Small dataset - assign to idle worker
        idle_worker = self.get_idle_worker()
        if idle_worker:
            idle_worker.status = WorkerStatus.RUNNING
            idle_worker.current_job = job
            return True
        else:
            # No idle workers - add to pending
            self.pending_jobs.append(job)
            return False
    
    def release_worker(self, worker_id: str):
        """Release worker and assign next pending job if available"""
        worker = self.get_worker_by_id(worker_id)
        if not worker:
            return
        
        worker.status = WorkerStatus.IDLE
        worker.current_job = None
        
        # Assign next pending job if available
        if self.pending_jobs:
            next_job = self.pending_jobs.pop(0)
            worker.status = WorkerStatus.RUNNING
            worker.current_job = next_job


class WorkerPoolManager:
    """Manages all worker pools"""
    
    def __init__(self, max_workers_per_pool: int = 5):
        self.max_workers_per_pool = max_workers_per_pool
        self.pools: Dict[str, WorkerPool] = {}
    
    def get_pool(self, model_key: str) -> WorkerPool:
        """Get or create worker pool for model"""
        if model_key not in self.pools:
            self.pools[model_key] = WorkerPool(model_key, self.max_workers_per_pool)
        return self.pools[model_key]
    
    def distribute_job(self, job: Job) -> bool:
        """Distribute job to appropriate pool"""
        pool = self.get_pool(job.model_key)
        return pool.distribute_job(job)
    
    def get_worker_stats(self) -> Dict[str, Any]:
        """Get statistics about all workers"""
        total_workers = 0
        idle_workers = 0
        running_workers = 0
        pending_jobs = 0
        
        for pool in self.pools.values():
            total_workers += len(pool.workers)
            idle_workers += sum(1 for w in pool.workers if w.status == WorkerStatus.IDLE)
            running_workers += sum(1 for w in pool.workers if w.status == WorkerStatus.RUNNING)
            pending_jobs += len(pool.pending_jobs)
        
        return {
            "total_workers": total_workers,
            "idle_workers": idle_workers,
            "running_workers": running_workers,
            "pending_jobs": pending_jobs,
            "pools": len(self.pools)
        }
    
    async def process_large_dataset(self, job: Job, job_repo: JobRepository) -> Dict[str, Any]:
        """
        Process large dataset by splitting into chunks and processing in parallel.
        
        Steps:
        1. Calculate optimal number of workers
        2. Split dataset into chunks
        3. Create sub-jobs for each chunk
        4. Process chunks in parallel
        5. Aggregate results
        """
        import json
        
        dataset_size = job.dataset_size or 0
        
        # Calculate number of workers needed (1 per 10,000 rows, max = max_workers)
        num_workers_needed = min(dataset_size // 10000, self.max_workers_per_pool)
        if num_workers_needed < 1:
            num_workers_needed = 1
        
        chunk_size = dataset_size // num_workers_needed
        
        logger.info(
            f"Large dataset job {job.job_id}: {dataset_size} rows, "
            f"will use {num_workers_needed} workers, {chunk_size} rows per chunk"
        )
        
        # Parse request payload to get data
        request_data = json.loads(job.request_payload) if job.request_payload else {}
        items = request_data.get("items", []) or request_data.get("data", [])
        
        if not items:
            raise ValueError("No data found in job request payload")
        
        # Split into chunks
        chunks = []
        for i in range(num_workers_needed):
            start_idx = i * chunk_size
            end_idx = start_idx + chunk_size if i < num_workers_needed - 1 else len(items)
            chunk_data = items[start_idx:end_idx]
            chunks.append(chunk_data)
        
        # Create sub-jobs for each chunk
        sub_jobs = []
        for chunk_idx, chunk_data in enumerate(chunks):
            sub_job_id = f"{job.job_id}_chunk_{chunk_idx}"
            
            # Create sub-job request payload
            sub_request_data = request_data.copy()
            if "items" in sub_request_data:
                sub_request_data["items"] = chunk_data
            if "data" in sub_request_data:
                sub_request_data["data"] = chunk_data
            
            sub_job = Job(
                job_id=sub_job_id,
                model_key=job.model_key,
                job_type=job.job_type,
                status="queued",
                stage="chunk",
                source=job.source,
                dataset_size=len(chunk_data),
                created_at=datetime.now(),
                client_ip=job.client_ip,
                user_agent=job.user_agent,
                priority=job.priority,
                user_tier=job.user_tier,
                data_size_bytes=len(json.dumps(chunk_data).encode('utf-8')),
                progress_current=0,
                progress_total=100,
                model_version=job.model_version,
                request_payload=json.dumps(sub_request_data),
                user_os=job.user_os,
                user_device=job.user_device,
                user_cpu_cores=job.user_cpu_cores,
                user_ram_gb=job.user_ram_gb,
                user_gpu=job.user_gpu
            )
            
            job_repo.create(sub_job)
            sub_jobs.append(sub_job)
        
        # Process chunks in parallel (simplified - actual processing would happen in workers)
        # For now, return info about chunking
        return {
            "needs_chunking": True,
            "dataset_size": dataset_size,
            "num_chunks": num_workers_needed,
            "chunk_size": chunk_size,
            "job_id": job.job_id,
            "sub_jobs": [sj.job_id for sj in sub_jobs]
        }

