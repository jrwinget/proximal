class GuardianAgent:
    """Placeholder agent for monitoring burnout risk."""

    def assess(self, workload: int) -> str:
        """Dummy assess method."""
        if workload > 10:
            return "high"
        return "low"
