"""Priority queue system for job management"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from ml_service.db.repositories import JobRepository
from ml_service.db.models import Job

logger = logging.getLogger(__name__)


class PriorityQueue:
    """Manages job priority calculation and queue ordering"""
    
    def __init__(self):
        self.last_recalculation = datetime.now()
        self.recalculation_interval = 60  # seconds
    
    def calculate_priority(self, job: Job) -> int:
        """
        Calculate job priority (0-14).
        
        Priority calculation:
        1. Base priority by user tier (admin=10, premium=7, basic=5)
        2. Bonus for data size (+1-3 points)
        3. Bonus for wait time (+1 point per hour, max +1 per hour)
        
        Returns: priority value (0-14)
        """
        # Step 1: Base priority by user tier
        tier_priorities = {
            "system_admin": 10,
            "admin": 10,
            "user": 5
        }
        base_priority = tier_priorities.get(job.user_tier, 5)
        
        # Step 2: Bonus for data size
        size_bonus = 0
        if job.data_size_bytes:
            size_mb = job.data_size_bytes / (1024 * 1024)  # Convert to MB
            if size_mb < 10:
                size_bonus = 0
            elif size_mb < 100:
                size_bonus = 1
            elif size_mb < 1024:  # 1 GB
                size_bonus = 2
            else:
                size_bonus = 3
        
        # Step 3: Bonus for wait time (if queued)
        wait_bonus = 0
        if job.status == "queued" and job.created_at:
            wait_time = datetime.now() - job.created_at
            hours_waited = wait_time.total_seconds() / 3600
            # +1 point per full hour, but max +1 per hour (to prevent infinite growth)
            wait_bonus = min(int(hours_waited), 4)  # Cap at +4 for 4+ hours
        
        # Calculate final priority (0-14)
        final_priority = base_priority + size_bonus + wait_bonus
        final_priority = max(0, min(14, final_priority))  # Clamp to 0-14
        
        return final_priority
    
    def recalculate_priorities(self) -> int:
        """
        Recalculate priorities for all queued jobs.
        Should be called periodically (every 60 seconds).
        
        Returns: number of jobs updated
        """
        current_time = datetime.now()
        time_since_last = (current_time - self.last_recalculation).total_seconds()
        
        if time_since_last < self.recalculation_interval:
            return 0  # Too soon to recalculate
        
        job_repo = JobRepository()
        queued_jobs = job_repo.get_queued_jobs()
        
        updated_count = 0
        for job in queued_jobs:
            new_priority = self.calculate_priority(job)
            if new_priority != job.priority:
                job_repo.update_priority(job.job_id, new_priority)
                updated_count += 1
        
        self.last_recalculation = current_time
        logger.info(f"Recalculated priorities for {updated_count} jobs")
        return updated_count
    
    def get_next_job(self, model_key: Optional[str] = None) -> Optional[Job]:
        """
        Get the next job from queue based on priority.
        
        Jobs are sorted by:
        1. Priority DESC (higher priority first)
        2. Created_at ASC (older jobs first if same priority)
        
        Args:
            model_key: Optional filter by model
        
        Returns: Next job to process or None if queue is empty
        """
        # Recalculate priorities if needed
        self.recalculate_priorities()
        
        job_repo = JobRepository()
        queued_jobs = job_repo.get_queued_jobs(model_key=model_key)
        
        if not queued_jobs:
            return None
        
        # Sort by priority DESC, then created_at ASC
        queued_jobs.sort(key=lambda j: (-j.priority, j.created_at or datetime.min))
        
        return queued_jobs[0]
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the queue.
        
        Returns:
            - queued_count: Number of queued jobs
            - running_count: Number of running jobs
            - avg_wait_time: Average wait time in seconds
            - priority_distribution: Count of jobs per priority level
        """
        job_repo = JobRepository()
        queued_jobs = job_repo.get_queued_jobs()
        running_jobs = job_repo.get_by_status("running", limit=1000)
        
        # Calculate average wait time
        avg_wait_time = 0
        if queued_jobs:
            total_wait = sum(
                (datetime.now() - (job.created_at or datetime.now())).total_seconds()
                for job in queued_jobs
                if job.created_at
            )
            avg_wait_time = total_wait / len(queued_jobs)
        
        # Priority distribution
        priority_distribution = {}
        for job in queued_jobs:
            priority = job.priority
            priority_distribution[priority] = priority_distribution.get(priority, 0) + 1
        
        return {
            "queued_count": len(queued_jobs),
            "running_count": len(running_jobs),
            "avg_wait_time_seconds": int(avg_wait_time),
            "priority_distribution": priority_distribution
        }

