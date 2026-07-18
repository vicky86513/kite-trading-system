"""
Orchestration: Run multiple trackers in parallel.

Starts all trading trackers (futures + options + market flow analysis)
in separate processes, monitors them, and handles graceful shutdown.

Run:
    python -m src.orchestration.run_all
"""

import subprocess
import signal
import time
import sys
from pathlib import Path

from src.shared.logger import get_logger

log = get_logger("ORCHESTRATION")

PROJECT_ROOT = Path(__file__).parent.parent.parent

# List of all trackers to run
# Format: (display_name, module_path)
TRACKERS = [
    ("🔍 NIFTY FLOW",     "src.trackers.nifty_futures_flow_tracker"),
    ("📊 NIFTY FUTURES",  "src.trackers.nifty_tracker"),
    ("⚫ MCX CRUDE OIL",   "src.trackers.mcx_crude_oil_tracker"),
    ("🔷 SENSEX FUTURES", "src.trackers.sensex_tracker"),
    ("📈 OPTIONS CE/PE",  "src.trackers.options_tracker"),
]

processes = []


def start_tracker(name, module):
    """Start a tracker subprocess."""
    log.info(f"🚀 Starting {name} tracker...")
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", module],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        processes.append((name, module, proc))
        log.info(f"✓ {name} tracker started (PID: {proc.pid})")
        return proc
    except Exception as e:
        log.error(f"✗ Failed to start {name}: {e}")
        return None


def monitor_trackers():
    """
    Monitor running processes and log their status.
    
    Checks every 5 seconds if any process has exited unexpectedly.
    Logs a warning if process dies, but doesn't restart (manual restart required).
    """
    while True:
        try:
            for name, module, proc in processes[:]:
                if proc.poll() is not None:  # Process exited
                    exit_code = proc.returncode
                    log.warning(f"⚠ {name} tracker exited with code {exit_code}")
                    
                    # Optionally try to get stderr output
                    try:
                        _, stderr = proc.communicate(timeout=1)
                        if stderr:
                            log.error(f"  Error output: {stderr.decode()[:200]}")
                    except:
                        pass
                    
                    # Remove from list
                    processes.remove((name, module, proc))
                    
                    log.warning(f"⚠ {name} is no longer running. To restart all, use Ctrl+C and re-run.")
            
            time.sleep(5)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            log.error(f"Error in monitor loop: {e}", exc_info=True)
            time.sleep(5)


def shutdown_all():
    """Gracefully shutdown all trackers."""
    log.info("=" * 70)
    log.info("🛑 Initiating graceful shutdown of all trackers...")
    log.info("=" * 70)
    
    shutdown_timeout = 10
    processes_to_kill = []
    
    # Phase 1: Terminate gracefully
    for name, module, proc in processes:
        try:
            log.info(f"  Terminating {name} (PID: {proc.pid})...")
            proc.terminate()
        except Exception as e:
            log.error(f"  ✗ Error terminating {name}: {e}")
    
    # Phase 2: Wait for graceful shutdown
    start_time = time.time()
    while time.time() - start_time < shutdown_timeout:
        still_running = []
        for name, module, proc in processes:
            if proc.poll() is None:  # Still running
                still_running.append((name, module, proc))
        
        if not still_running:
            break
        
        time.sleep(0.5)
    
    # Phase 3: Force kill remaining processes
    for name, module, proc in processes:
        if proc.poll() is None:  # Still running after timeout
            try:
                log.warning(f"  ⚠ Force-killing {name} (PID: {proc.pid}) - graceful shutdown timeout")
                proc.kill()
                processes_to_kill.append((name, proc))
            except Exception as e:
                log.error(f"  ✗ Error killing {name}: {e}")
    
    # Phase 4: Final verification
    time.sleep(1)
    for name, proc in processes_to_kill:
        try:
            proc.wait(timeout=2)
            log.info(f"  ✓ {name} killed")
        except subprocess.TimeoutExpired:
            log.error(f"  ✗ Failed to kill {name}")
        except Exception as e:
            log.error(f"  ✗ Error verifying {name}: {e}")
    
    log.info("=" * 70)
    log.info("✓ All trackers shutdown complete")
    log.info("=" * 70)


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    log.info("\n" + "=" * 70)
    log.info("📍 Ctrl+C received - initiating graceful shutdown...")
    log.info("=" * 70)
    shutdown_all()
    exit(0)


def print_startup_banner():
    """Print startup banner."""
    banner = """
╔════════════════════════════════════════════════════════════════════════╗
║                                                                        ║
║        🚀 NIFTY FUTURES MARKET FLOW TRADING SYSTEM 🚀                 ║
║                                                                        ║
║  Starting all trackers:                                               ║
"""
    log.info(banner)
    
    for name, _ in TRACKERS:
        log.info(f"    • {name}")
    
    log.info("""
║                                                                        ║
║  📊 Dashboard: http://localhost:8000/dashboard.html                   ║
║  📁 Logs: data/Logs/trading_logs_<date>.txt                           ║
║  💾 Data: data/Excel/                                                 ║
║                                                                        ║
║  Press Ctrl+C to shutdown gracefully                                  ║
║                                                                        ║
╚════════════════════════════════════════════════════════════════════════╝
    """)


def print_status_report():
    """Print current status of all trackers."""
    log.info("=" * 70)
    log.info("📊 TRACKER STATUS")
    log.info("=" * 70)
    
    for name, module, proc in processes:
        status = "✓ Running" if proc.poll() is None else "✗ Stopped"
        log.info(f"  {name:20} {status:12} (PID: {proc.pid})")
    
    log.info("=" * 70)


def run_all():
    """
    Main orchestration: start all trackers and monitor them.
    """
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Print banner
    print_startup_banner()

    log.info("Starting all trackers with staggered launch...\n")

    # Start all trackers
    for name, module in TRACKERS:
        start_tracker(name, module)
        time.sleep(2)  # Stagger starts to avoid concurrent auth requests

    # Print initial status
    time.sleep(1)
    print_status_report()

    log.info("\n✓ All trackers started. Monitoring in progress...\n")

    # Monitor trackers
    try:
        monitor_trackers()
    except KeyboardInterrupt:
        shutdown_all()


def main():
    """Entry point."""
    try:
        run_all()
    except Exception as e:
        log.error(f"✗ Fatal error: {e}", exc_info=True)
        shutdown_all()
        sys.exit(1)


if __name__ == "__main__":
    main()