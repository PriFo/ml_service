"""Daily scheduler for drift monitoring"""
import asyncio
import logging
import json
from datetime import datetime, time, timedelta
from typing import List, Optional

from ml_service.core.config import settings
from ml_service.db.repositories import (
    ModelRepository, DriftCheckRepository, TrainingJobRepository, AlertRepository, EventRepository
)
from ml_service.ml.drift_detector import DriftDetector
from ml_service.db.models import Alert, TrainingJob, Event
import uuid

logger = logging.getLogger(__name__)


class DailyScheduler:
    """Schedule daily drift checks"""
    
    def __init__(self):
        self.running = False
        self.task: Optional[asyncio.Task] = None
    
    async def run_daily_drift_check(self):
        """
        Run daily drift check for all active models.
        Executes at 23:00 daily.
        """
        logger.info("Starting daily drift check")
        
        try:
            model_repo = ModelRepository()
            drift_repo = DriftCheckRepository()
            drift_detector = DriftDetector()
            
            # Get all active models
            models = model_repo.get_active_models()
            
            event_repo = EventRepository()
            
            for model in models:
                try:
                    logger.info(f"Checking drift for model: {model.model_key} v{model.version}")
                    
                    # Log system drift check event
                    event_id = str(uuid.uuid4())
                    event = Event(
                        event_id=event_id,
                        event_type="drift",
                        source="system",
                        model_key=model.model_key,
                        status="running",
                        stage="checking",
                        input_data=json.dumps({
                            "model_key": model.model_key,
                            "version": model.version,
                            "check_type": "daily_automatic"
                        }),
                        client_ip=None,  # System check, no client IP
                        user_agent=None,  # System check, no user agent
                        created_at=datetime.now()
                    )
                    event_repo.create(event)
                    
                    # Check drift (automatically loads baseline and current data)
                    drift_result = await drift_detector.check_drift(
                        model_key=model.model_key,
                        version=model.version
                    )
                    
                    # Save drift check result
                    drift_repo.create_drift_check(
                        model_key=model.model_key,
                        check_date=datetime.now().date(),
                        psi_value=drift_result.get("psi"),
                        js_divergence=drift_result.get("js_divergence"),
                        drift_detected=drift_result.get("drift_detected", False),
                        items_analyzed=drift_result.get("items_analyzed", 0)
                    )
                    
                    # Update event with result
                    event_repo.update_status(
                        event_id,
                        "completed",
                        stage="completed",
                        output_data=json.dumps(drift_result)
                    )
                    
                    # If drift detected, trigger auto-retraining and create alert
                    if drift_result.get("drift_detected"):
                        logger.warning(
                            f"Drift detected for {model.model_key} v{model.version}: "
                            f"PSI={drift_result.get('psi', 0):.4f}, "
                            f"JS={drift_result.get('js_divergence', 0):.4f}"
                        )
                        
                        # Create alert
                        alert_repo = AlertRepository()
                        alert = Alert(
                            alert_id=str(uuid.uuid4()),
                            type="drift_detected",
                            severity="warning",
                            model_key=model.model_key,
                            message=f"Data drift detected for model {model.model_key} v{model.version}",
                            details=json.dumps({
                                "psi": drift_result.get("psi"),
                                "js_divergence": drift_result.get("js_divergence"),
                                "items_analyzed": drift_result.get("items_analyzed")
                            }),
                            created_at=datetime.now()
                        )
                        alert_repo.create(alert)
                        
                        # Trigger auto-retraining
                        await self.trigger_auto_retraining(model.model_key, model.version)
                    
                except Exception as e:
                    logger.error(
                        f"Error checking drift for {model.model_key}: {e}",
                        exc_info=True
                    )
                    # Update event with error if it was created
                    try:
                        if 'event_id' in locals():
                            event_repo.update_status(
                                event_id,
                                "failed",
                                stage="failed",
                                error_message=str(e)[:1000]
                            )
                    except:
                        pass
            
            logger.info("Daily drift check completed")
            
        except Exception as e:
            logger.error(f"Error in daily drift check: {e}", exc_info=True)
    
    def parse_time(self, time_str: str) -> time:
        """Parse time string (HH:MM) to time object"""
        hour, minute = map(int, time_str.split(":"))
        return time(hour, minute)
    
    async def scheduler_loop(self):
        """Main scheduler loop"""
        check_time = self.parse_time(settings.ML_DAILY_DRIFT_CHECK_TIME)
        
        while self.running:
            now = datetime.now().time()
            
            # Calculate seconds until next check
            if now < check_time:
                # Today
                next_check = datetime.combine(datetime.now().date(), check_time)
            else:
                # Tomorrow
                next_check = datetime.combine(
                    datetime.now().date(),
                    check_time
                ) + timedelta(days=1)
            
            wait_seconds = (next_check - datetime.now()).total_seconds()
            
            logger.info(
                f"Next drift check scheduled for {next_check} "
                f"(in {wait_seconds:.0f} seconds)"
            )
            
            await asyncio.sleep(wait_seconds)
            
            # Run drift check
            await self.run_daily_drift_check()
    
    def start(self):
        """Start the scheduler"""
        if self.running:
            logger.warning("Scheduler already running")
            return
        
        self.running = True
        self.task = asyncio.create_task(self.scheduler_loop())
        logger.info("Daily scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        if self.task:
            self.task.cancel()
        logger.info("Daily scheduler stopped")
    
    async def trigger_auto_retraining(self, model_key: str, current_version: str):
        """Trigger automatic retraining when drift is detected"""
        try:
            logger.info(f"Triggering auto-retraining for {model_key} (current version: {current_version})")
            
            # Get model details to determine retraining parameters
            model_repo = ModelRepository()
            model = model_repo.get(model_key, current_version)
            
            if not model:
                logger.error(f"Model {model_key} v{current_version} not found for auto-retraining")
                return
            
            # Generate new version
            from ml_service.api.routes import process_training_job
            import uuid
            
            # Try to get recent training data from prediction logs
            # For now, we'll need to trigger manual retraining
            # In production, this could use stored training data or recent high-confidence predictions
            
            logger.warning(
                f"Auto-retraining triggered for {model_key}, but requires training data. "
                f"Please retrain manually via /train endpoint with appropriate dataset."
            )
            
            # Create alert about need for manual retraining
            alert_repo = AlertRepository()
            alert = Alert(
                alert_id=str(uuid.uuid4()),
                type="retraining_required",
                severity="warning",
                model_key=model_key,
                message=f"Auto-retraining required for {model_key} due to drift detection",
                details=json.dumps({
                    "current_version": current_version,
                    "reason": "drift_detected",
                    "action_required": "manual_retraining"
                }),
                created_at=datetime.now()
            )
            alert_repo.create(alert)
            
        except Exception as e:
            logger.error(f"Failed to trigger auto-retraining for {model_key}: {e}", exc_info=True)


# Global scheduler instance
scheduler = DailyScheduler()

