"""Mode2Agent: wrapper for price transfer specialized agent."""
from agent.core import PriceTransferAgent


class Mode2Agent(PriceTransferAgent):
    """Alias class to clarify Mode2 semantics."""

    # Inherit everything; this is just a semantic alias.
    ...
