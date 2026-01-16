"""
Forecast Orchestrator
Manages forecast execution using certainty-based categorization
"""

import logging
from datetime import datetime
from typing import Any

from ..database.connection import get_db
from ..database.models import ForecastRun, LongTermForecast
from .context_curator import ForecastContextCurator
from .engine import ForecastEngine

logger = logging.getLogger(__name__)


class ForecastOrchestrator:
    """
    Orchestrates forecast generation using certainty-based categorization

    Generates forecasts organized by:
    - Known Knowns (certain/near-certain)
    - Known Unknowns (evidence-based projections)
    - Unknown Unknowns (weak signal speculation)

    Each forecast includes its own timeline.
    """

    def __init__(self, user_profile=None, topic_filters: dict | None = None):
        """
        Initialize forecast orchestrator

        Args:
            user_profile: User profile for personalization
            topic_filters: Optional topic/scope filters
        """
        self.user_profile = user_profile
        self.topic_filters = topic_filters
        self.engine = ForecastEngine()
        self.curator = ForecastContextCurator(
            user_profile=user_profile, topic_filters=topic_filters
        )

    async def run_forecast(self) -> dict[str, Any]:
        """
        Run certainty-based forecast generation

        Returns:
            Dictionary with run_id and forecast data
        """
        logger.info("Starting certainty-based forecast run")

        # Create forecast run record
        with get_db() as session:
            forecast_run = ForecastRun(
                run_type="certainty_based",
                horizons_requested=["unified"],
                scenario_count=0,
                started_at=datetime.utcnow(),
                status="running",
                forecasts_generated=0,
            )
            session.add(forecast_run)
            session.commit()
            run_id = forecast_run.id

        logger.info(f"Created forecast run {run_id}")

        try:
            # Generate the unified forecast
            forecast = await self._generate_forecast(run_id=run_id)

            # Mark run as completed
            with get_db() as session:
                run = session.query(ForecastRun).get(run_id)
                run.status = "completed"
                run.completed_at = datetime.utcnow()
                run.forecasts_generated = 1
                session.commit()

            logger.info(f"Forecast run {run_id} completed successfully")

            return {
                "run_id": run_id,
                "forecast": forecast,
                "status": "completed",
            }

        except Exception as e:
            logger.error(f"Forecast generation failed: {e}")

            # Mark run as failed
            with get_db() as session:
                run = session.query(ForecastRun).get(run_id)
                run.status = "failed"
                run.completed_at = datetime.utcnow()
                run.error_message = str(e)
                session.commit()

            raise

    async def _generate_forecast(self, run_id: int) -> dict[str, Any]:
        """
        Generate certainty-based forecast

        Args:
            run_id: Forecast run ID

        Returns:
            Forecast dictionary with metadata
        """
        logger.info("Curating context for forecast...")

        # Curate context with broad historical range (12 months)
        context = await self.curator.curate_for_horizon(
            horizon_months=12, topic_filters=self.topic_filters
        )

        # Generate forecast
        logger.info("Generating certainty-based forecast...")
        forecast_data = await self.engine.generate_forecast(context=context)

        # Store in database
        base_date = datetime.utcnow()

        with get_db() as session:
            forecast = LongTermForecast(
                forecast_run_id=run_id,
                time_horizon="unified",
                horizon_months=0,  # Not applicable for certainty-based
                base_date=base_date,
                target_date=base_date,  # Individual forecasts have their own timelines
                forecast_data=forecast_data,
                articles_analyzed=context.get("article_count", 0),
                context_tokens=len(str(context)) // 4,
            )
            session.add(forecast)
            session.commit()
            forecast_id = forecast.id

        logger.info(f"Stored forecast as ID {forecast_id}")

        return {
            "id": forecast_id,
            "generated_at": base_date.isoformat(),
            "forecast_data": forecast_data,
            "articles_analyzed": context.get("article_count", 0),
        }
