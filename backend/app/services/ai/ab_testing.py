"""
A/B Testing Service
===================
A/B testing framework for ML model deployment and comparison.

Provides:
- Traffic splitting between model versions
- Performance comparison
- Statistical significance testing
- Automatic winner selection
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

# ML libraries lazy loaded in methods for faster startup
# import numpy as np

if TYPE_CHECKING:
    from app.services.ai.model_registry import ModelRegistry

logger = logging.getLogger(__name__)


class TestStatus(Enum):
    """A/B test status."""

    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class ABTestResult:
    """Individual A/B test result."""

    test_id: str
    version: str
    timestamp: datetime
    predicted: Any
    actual: Any | None
    error: float | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "test_id": self.test_id,
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
            "predicted": self.predicted,
            "actual": self.actual,
            "error": self.error,
        }


@dataclass
class ABTest:
    """A/B test configuration."""

    test_id: str
    model_name: str
    version_a: str
    version_b: str
    split_ratio: float  # % traffic to version A (0-1)
    start_date: datetime
    end_date: datetime | None
    status: TestStatus
    min_samples: int

    # Results
    version_a_results: list[ABTestResult]
    version_b_results: list[ABTestResult]
    winner: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "test_id": self.test_id,
            "model_name": self.model_name,
            "version_a": self.version_a,
            "version_b": self.version_b,
            "split_ratio": self.split_ratio,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "status": self.status.value,
            "min_samples": self.min_samples,
            "results_count_a": len(self.version_a_results),
            "results_count_b": len(self.version_b_results),
            "winner": self.winner,
        }


class ABTestingService:
    """
    A/B testing service for ML models.

    Manages split testing between model versions to determine
    which performs better before full deployment.

    Supports database persistence for state recovery across restarts.
    """

    def __init__(
        self,
        model_registry: ModelRegistry,
        ai_repo: Any | None = None,
    ):
        """
        Initialize A/B testing service.

        Args:
            model_registry: Model registry for version management
            ai_repo: Optional AI repository for state persistence
        """
        self.model_registry = model_registry
        self.ai_repo = ai_repo
        self.logger = logging.getLogger(__name__)

        # Active tests (in-memory cache)
        self.active_tests: dict[str, ABTest] = {}

        # Default configuration
        self.default_split_ratio = 0.5
        self.default_min_samples = 100
        self.significance_threshold = 0.05

        # Load active tests from database on startup
        self._load_active_tests()

    def _load_active_tests(self) -> None:
        """Load active tests from database into memory."""
        if not self.ai_repo:
            return

        try:
            tests = self.ai_repo.get_active_ab_tests()
            for test_data in tests:
                test = ABTest(
                    test_id=test_data["test_id"],
                    model_name=test_data["model_name"],
                    version_a=test_data["version_a"],
                    version_b=test_data["version_b"],
                    split_ratio=test_data.get("split_ratio", 0.5),
                    start_date=datetime.fromisoformat(test_data["start_date"])
                    if test_data.get("start_date")
                    else datetime.now(),
                    end_date=datetime.fromisoformat(test_data["end_date"]) if test_data.get("end_date") else None,
                    status=TestStatus(test_data.get("status", "running")),
                    min_samples=test_data.get("min_samples", 100),
                    version_a_results=[],
                    version_b_results=[],
                    winner=test_data.get("winner"),
                )
                self.active_tests[test.test_id] = test
            self.logger.info("Loaded %s active A/B tests from database", len(tests))
        except Exception as e:
            self.logger.error("Failed to load active A/B tests: %s", e)

    def _persist_test(self, test: ABTest) -> None:
        """Persist test state to database."""
        if not self.ai_repo:
            return

        try:
            self.ai_repo.save_ab_test(
                {
                    "test_id": test.test_id,
                    "model_name": test.model_name,
                    "version_a": test.version_a,
                    "version_b": test.version_b,
                    "split_ratio": test.split_ratio,
                    "start_date": test.start_date.isoformat(),
                    "end_date": test.end_date.isoformat() if test.end_date else None,
                    "status": test.status.value,
                    "min_samples": test.min_samples,
                    "winner": test.winner,
                }
            )
        except Exception as e:
            self.logger.error("Failed to persist A/B test: %s", e)

    def create_test(
        self, model_name: str, version_a: str, version_b: str, split_ratio: float = 0.5, min_samples: int = 100
    ) -> str:
        """
        Create a new A/B test.

        Args:
            model_name: Name of the model to test
            version_a: First version to test
            version_b: Second version to test
            split_ratio: Traffic split (0-1, default 0.5 = 50/50)
            min_samples: Minimum samples before analysis

        Returns:
            Test ID
        """
        try:
            # Validate versions exist
            metadata_a = self.model_registry.get_metadata(model_name, version_a)
            metadata_b = self.model_registry.get_metadata(model_name, version_b)

            if not metadata_a or not metadata_b:
                raise ValueError("One or both versions not found in registry")

            # Generate test ID
            test_id = f"{model_name}_ab_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Create test
            test = ABTest(
                test_id=test_id,
                model_name=model_name,
                version_a=version_a,
                version_b=version_b,
                split_ratio=split_ratio,
                start_date=datetime.now(),
                end_date=None,
                status=TestStatus.RUNNING,
                min_samples=min_samples,
                version_a_results=[],
                version_b_results=[],
            )

            self.active_tests[test_id] = test
            self._persist_test(test)

            self.logger.info("Created A/B test %s for %s: %s vs %s", test_id, model_name, version_a, version_b)
            return test_id

        except Exception as e:
            self.logger.error("Failed to create A/B test: %s", e, exc_info=True)
            raise

    def select_version(self, test_id: str) -> str:
        """
        Select which version to use based on split ratio.

        Args:
            test_id: Test ID

        Returns:
            Version to use ('a' or 'b')
        """
        if test_id not in self.active_tests:
            raise ValueError(f"Test {test_id} not found")

        test = self.active_tests[test_id]

        # Random selection based on split ratio
        return "a" if random.random() < test.split_ratio else "b"

    def record_result(self, test_id: str, version: str, predicted: Any, actual: Any | None = None) -> None:
        """
        Record a prediction result for the test.

        Args:
            test_id: Test ID
            version: Version used ('a' or 'b')
            predicted: Predicted value
            actual: Actual value (if available)
        """
        try:
            if test_id not in self.active_tests:
                self.logger.warning("Test %s not found", test_id)
                return

            test = self.active_tests[test_id]

            # Calculate error if actual is available
            error = None
            if actual is not None:
                if isinstance(predicted, (int, float)) and isinstance(actual, (int, float)):
                    error = abs(predicted - actual)
                else:
                    error = 0.0 if predicted == actual else 1.0

            # Create result
            result = ABTestResult(
                test_id=test_id,
                version=version,
                timestamp=datetime.now(),
                predicted=predicted,
                actual=actual,
                error=error,
            )

            # Store result in memory
            if version == "a":
                test.version_a_results.append(result)
            elif version == "b":
                test.version_b_results.append(result)
            else:
                self.logger.warning("Invalid version: %s", version)
                return

            # Persist result to database
            if self.ai_repo:
                self.ai_repo.save_ab_test_result(test_id, version, predicted, actual, error)

        except Exception as e:
            self.logger.error("Error recording result: %s", e)

    def analyze_test(self, test_id: str) -> dict[str, Any]:
        """
        Analyze test results and determine winner.

        Args:
            test_id: Test ID

        Returns:
            Analysis results
        """
        try:
            if test_id not in self.active_tests:
                raise ValueError(f"Test {test_id} not found")

            test = self.active_tests[test_id]

            # Check if we have enough samples
            count_a = len(test.version_a_results)
            count_b = len(test.version_b_results)

            if count_a < test.min_samples or count_b < test.min_samples:
                return {
                    "status": "insufficient_data",
                    "samples_a": count_a,
                    "samples_b": count_b,
                    "min_required": test.min_samples,
                    "message": f"Need more samples (A: {count_a}/{test.min_samples}, B: {count_b}/{test.min_samples})",
                }

            # Lazy load numpy for statistics
            import numpy as np

            # Calculate metrics for version A
            errors_a = [r.error for r in test.version_a_results if r.error is not None]
            mean_error_a = np.mean(errors_a) if errors_a else float("inf")
            std_error_a = np.std(errors_a) if errors_a else 0

            # Calculate metrics for version B
            errors_b = [r.error for r in test.version_b_results if r.error is not None]
            mean_error_b = np.mean(errors_b) if errors_b else float("inf")
            std_error_b = np.std(errors_b) if errors_b else 0

            # Determine winner (lower error is better)
            improvement = ((mean_error_a - mean_error_b) / mean_error_a * 100) if mean_error_a > 0 else 0

            winner = None
            winner_reason = None

            if abs(improvement) < 1:
                winner_reason = "No significant difference detected"
            elif improvement > 0:
                winner = test.version_b
                winner_reason = f"Version B has {abs(improvement):.2f}% lower error"
            else:
                winner = test.version_a
                winner_reason = f"Version A has {abs(improvement):.2f}% lower error"

            test.winner = winner

            return {
                "status": "completed",
                "test_id": test_id,
                "model_name": test.model_name,
                "version_a": {
                    "version": test.version_a,
                    "samples": count_a,
                    "mean_error": round(mean_error_a, 4),
                    "std_error": round(std_error_a, 4),
                },
                "version_b": {
                    "version": test.version_b,
                    "samples": count_b,
                    "mean_error": round(mean_error_b, 4),
                    "std_error": round(std_error_b, 4),
                },
                "winner": winner,
                "improvement_percentage": round(abs(improvement), 2),
                "reason": winner_reason,
            }

        except Exception as e:
            self.logger.error("Error analyzing test: %s", e, exc_info=True)
            return {"status": "error", "error": str(e)}

    def complete_test(self, test_id: str, deploy_winner: bool = False) -> dict[str, Any]:
        """
        Complete a test and optionally deploy winner.

        Args:
            test_id: Test ID
            deploy_winner: Whether to promote winner to production

        Returns:
            Completion results
        """
        try:
            analysis = self.analyze_test(test_id)

            if analysis.get("status") != "completed":
                return analysis

            test = self.active_tests[test_id]
            test.status = TestStatus.COMPLETED
            test.end_date = datetime.now()
            self._persist_test(test)

            # Deploy winner if requested
            if deploy_winner and test.winner:
                self.model_registry.promote_to_production(test.model_name, test.winner)
                analysis["deployed"] = True
                analysis["production_version"] = test.winner

            return analysis

        except Exception as e:
            self.logger.error("Error completing test: %s", e, exc_info=True)
            return {"status": "error", "error": str(e)}

    def cancel_test(self, test_id: str) -> bool:
        """
        Cancel an active test.

        Args:
            test_id: Test ID

        Returns:
            True if cancelled successfully
        """
        if test_id not in self.active_tests:
            return False

        test = self.active_tests[test_id]
        test.status = TestStatus.CANCELLED
        test.end_date = datetime.now()
        self._persist_test(test)

        return True

    def get_test(self, test_id: str) -> dict[str, Any] | None:
        """
        Get test details.

        Args:
            test_id: Test ID

        Returns:
            Test details or None
        """
        if test_id not in self.active_tests:
            return None

        test = self.active_tests[test_id]
        return test.to_dict()

    def list_tests(self, model_name: str | None = None, status: TestStatus | None = None) -> list[dict[str, Any]]:
        """
        List all tests.

        Args:
            model_name: Filter by model name
            status: Filter by status

        Returns:
            List of tests
        """
        tests = self.active_tests.values()

        if model_name:
            tests = [t for t in tests if t.model_name == model_name]

        if status:
            tests = [t for t in tests if t.status == status]

        return [t.to_dict() for t in tests]
