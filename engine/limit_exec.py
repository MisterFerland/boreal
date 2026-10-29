"""Set OS-enforced bounds, then replace this process with the native engine.

Used on Linux delivery runtimes; the parent supplies an allowlisted, hash-checked
executable and fixed arguments. No shell, user command text or child daemon.
"""

import os
import resource
import sys

resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024 * 1024, 2 * 1024 * 1024))
resource.setrlimit(resource.RLIMIT_CPU, (25, 25))
resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
os.execv(sys.argv[1], sys.argv[1:])
