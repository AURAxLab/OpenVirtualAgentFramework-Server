import os
import json
import csv
import time
from datetime import datetime
import structlog
from pathlib import Path

from src.core.schemas import BaseCommand
from src.core.config import config_manager

class TelemetryLogger:
    """
    Handles structured logging of all interactions for experimental reproducibility.
    Logs are saved in JSONL format, and can be exported to CSV.
    """
    def __init__(self):
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_dir = Path("data/sessions")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.log_dir / f"session_{self.session_id}.jsonl"
        
        # Configure structlog to output to file
        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer()
            ],
            logger_factory=structlog.WriteLoggerFactory(
                file=open(self.jsonl_path, "a", encoding="utf-8")
            )
        )
        self.file_logger = structlog.get_logger()
        
        # Keep a console logger separate so we don't spam JSON to the stdout
        self.console_logger = structlog.get_logger("console")
        self.console_logger.info("Telemetry Session Started", session_id=self.session_id, file=str(self.jsonl_path))

    def log_interaction(self, command: BaseCommand):
        """Append a Command directly to the session logs with an atomic timestamp."""
        # Using time.time() for high precision float ms timestamps useful for XR data sync
        self.file_logger.info(
            event="interaction",
            host_timestamp=time.time(),
            sender=command.sender,
            target_device=command.target_device,
            target_agent=command.target_agent,
            command_type=command.command_type,
            command=command.command,
            subcommand=command.subcommand
        )

    def export_to_csv(self) -> Path:
        """Parses the current session JSONL and flattens it to CSV for statistical analysis software like SPSS/R."""
        csv_path = self.log_dir / f"session_{self.session_id}.csv"
        
        try:
            with open(self.jsonl_path, 'r', encoding="utf-8") as f_in, \
                 open(csv_path, 'w', newline='', encoding="utf-8") as f_out:
                 
                writer = csv.writer(f_out)
                # Write header
                writer.writerow([
                    "iso_time", "host_timestamp", "sender", "target_device", 
                    "target_agent", "command_type", "command", "subcommand_json"
                ])
                
                for line in f_in:
                    if not line.strip(): continue
                    data = json.loads(line)
                    if data.get("event") == "interaction":
                        writer.writerow([
                            data.get("timestamp", ""),
                            data.get("host_timestamp", ""),
                            data.get("sender", ""),
                            data.get("target_device", ""),
                            data.get("target_agent", ""),
                            data.get("command_type", ""),
                            data.get("command", ""),
                            json.dumps(data.get("subcommand", {}))
                        ])
            
            self.console_logger.info("Telemetry Exported successfully", csv_file=str(csv_path))            
            return csv_path
        except Exception as e:
            self.console_logger.error("Failed to export telemetry to CSV", error=str(e))
            return None

telemetry = TelemetryLogger()
