"""Agent Engine package root.

The public API surface includes the Engine façade and the schema types exposed in
``agent_engine.schemas``. Example applications should import only from this
package (not from ``agent_engine.runtime`` modules).
"""

__version__ = "0.0.1"

from agent_engine.engine import Engine  # noqa: F401
from agent_engine.schemas import *  # noqa: F401,F403
from agent_engine.schemas import __all__ as SCHEMA_EXPORTS

__all__ = ["__version__", "Engine"] + SCHEMA_EXPORTS
