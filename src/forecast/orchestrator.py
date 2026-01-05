"""
Forecast Orchestrator
Manages multi-horizon forecast execution and coordinates all forecast components
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from ..database.connection import get_db
from ..database.models import ForecastRun, LongTermForecast
from .context_curator import ForecastContextCurator
from .engine import ForecastEngine
from .scenario_modeler import ScenarioModeler

logger = logging.getLogger(__name__)


class ForecastOrchestrator:
    """
    Orchestrates multi-horizon forecast generation

    Coordinates:
    - Multiple time horizons (6mo, 1yr, 3yr, 5yr)
    - Context curation for each horizon
    - Forecast generation
    - Optional scenario modeling
    - Database storage
    """

    # Supported horizons
    SUPPORTED_HORIZONS = {
        '6mo': 6,
        '1yr': 12,
        '3yr': 36,
        '5yr': 60
    }

    def __init__(
        self,
        user_profile=None,
        topic_filters: dict | None = None
    ):
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
            user_profile=user_profile,
            topic_filters=topic_filters
        )
        self.scenario_modeler = ScenarioModeler()

    async def run_forecast(
        self,
        horizons: list[str] | None = None,
        scenario_count: int = 0
    ) -> dict[str, Any]:
        """
        Run forecast for specified horizons

        Args:
            horizons: List of horizon strings (e.g., ['6mo', '1yr', '3yr'])
                     If None, runs all default horizons
            scenario_count: Number of scenarios to generate per horizon (0 = skip)

        Returns:
            Dictionary with run_id and list of forecasts
        """
        # Default to all horizons if not specified
        if horizons is None:
            horizons = list(self.SUPPORTED_HORIZONS.keys())

        # Validate horizons
        for horizon in horizons:
            if horizon not in self.SUPPORTED_HORIZONS:
                raise ValueError(f"Unsupported horizon: {horizon}. Supported: {list(self.SUPPORTED_HORIZONS.keys())}")

        logger.info(f"Starting forecast run for horizons: {horizons}")

        # Create forecast run record
        with get_db() as session:
            forecast_run = ForecastRun(
                run_type='multi_horizon' if len(horizons) > 1 else 'single_horizon',
                horizons_requested=horizons,
                scenario_count=scenario_count,
                started_at=datetime.utcnow(),
                status='running',
                forecasts_generated=0
            )
            session.add(forecast_run)
            session.commit()
            run_id = forecast_run.id

        logger.info(f"Created forecast run {run_id}")

        # Generate forecasts for each horizon
        forecasts = []
        for horizon in horizons:
            try:
                forecast = await self._generate_horizon_forecast(
                    run_id=run_id,
                    horizon=horizon,
                    scenario_count=scenario_count
                )
                forecasts.append(forecast)

                # Update run progress
                with get_db() as session:
                    run = session.query(ForecastRun).get(run_id)
                    run.forecasts_generated += 1
                    session.commit()

            except Exception as e:
                logger.error(f"Failed to generate {horizon} forecast: {e}")
                # Continue with other horizons
                continue

        # Mark run as completed
        with get_db() as session:
            run = session.query(ForecastRun).get(run_id)
            run.status = 'completed' if forecasts else 'failed'
            run.completed_at = datetime.utcnow()
            if not forecasts:
                run.error_message = "All horizons failed"
            session.commit()

        logger.info(f"Forecast run {run_id} completed: {len(forecasts)}/{len(horizons)} horizons")

        return {
            'run_id': run_id,
            'forecasts': forecasts,
            'requested_horizons': horizons,
            'successful_horizons': len(forecasts)
        }

    async def _generate_horizon_forecast(
        self,
        run_id: int,
        horizon: str,
        scenario_count: int
    ) -> dict[str, Any]:
        """
        Generate forecast for a single horizon

        Args:
            run_id: Forecast run ID
            horizon: Horizon string (e.g., '1yr')
            scenario_count: Number of scenarios to generate

        Returns:
            Forecast dictionary with metadata
        """
        horizon_months = self.SUPPORTED_HORIZONS[horizon]

        logger.info(f"Generating {horizon} forecast...")

        # 1. Curate context
        logger.info(f"Curating context for {horizon} horizon...")
        context = await self.curator.curate_for_horizon(
            horizon_months=horizon_months,
            topic_filters=self.topic_filters
        )

        # 2. Generate base forecast
        logger.info(f"Generating base forecast for {horizon}...")
        forecast_data = await self.engine.generate_forecast(
            horizon=horizon,
            context=context
        )

        # 3. Optional: Generate scenarios
        if scenario_count > 0:
            logger.info(f"Generating {scenario_count} scenarios for {horizon}...")
            try:
                scenarios = await self.scenario_modeler.generate_scenarios(
                    baseline_forecast=forecast_data,
                    context=context,
                    scenario_count=scenario_count
                )
                forecast_data['detailed_scenarios'] = scenarios
            except Exception as e:
                logger.error(f"Scenario generation failed for {horizon}: {e}")
                # Continue without scenarios

        # 4. Calculate dates
        base_date = datetime.utcnow()
        target_date = base_date + timedelta(days=horizon_months * 30)

        # 5. Store in database
        with get_db() as session:
            forecast = LongTermForecast(
                forecast_run_id=run_id,
                time_horizon=horizon,
                horizon_months=horizon_months,
                base_date=base_date,
                target_date=target_date,
                forecast_data=forecast_data,
                articles_analyzed=context.get('article_count', 0),
                context_tokens=len(str(context)) // 4
            )
            session.add(forecast)
            session.commit()
            forecast_id = forecast.id

        logger.info(f"Stored {horizon} forecast as ID {forecast_id}")

        return {
            'id': forecast_id,
            'time_horizon': horizon,
            'horizon_months': horizon_months,
            'target_date': target_date.strftime('%B %Y'),
            'forecast_data': forecast_data,
            'articles_analyzed': context.get('article_count', 0)
        }

    def parse_custom_horizon(self, horizon_str: str) -> int:
        """
        Parse custom horizon string to months

        Args:
            horizon_str: String like "18 months", "2 years", "24mo"

        Returns:
            Number of months

        Raises:
            ValueError: If format is invalid
        """
        horizon_str = horizon_str.lower().strip()

        # Check if it's a standard horizon
        if horizon_str in self.SUPPORTED_HORIZONS:
            return self.SUPPORTED_HORIZONS[horizon_str]

        # Parse custom format
        if 'mo' in horizon_str:
            try:
                return int(horizon_str.replace('mo', '').strip())
            except ValueError:
                raise ValueError(f"Invalid horizon format: {horizon_str}")

        if 'year' in horizon_str or 'yr' in horizon_str:
            try:
                years = int(horizon_str.replace('years', '').replace('year', '').replace('yr', '').strip())
                return years * 12
            except ValueError:
                raise ValueError(f"Invalid horizon format: {horizon_str}")

        if 'month' in horizon_str:
            try:
                return int(horizon_str.replace('months', '').replace('month', '').strip())
            except ValueError:
                raise ValueError(f"Invalid horizon format: {horizon_str}")

        # Try parsing as just a number (assume months)
        try:
            return int(horizon_str)
        except ValueError:
            raise ValueError(f"Invalid horizon format: {horizon_str}. Use format like '6mo', '1yr', '18 months'")
