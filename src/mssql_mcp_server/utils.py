"""Utility functions for MSSQL MCP server."""

import os
import re
import logging
from dotenv import load_dotenv
import pathlib

# Load environment variables from .env file in project root
project_root = pathlib.Path(__file__).parent.parent.parent
load_dotenv(project_root / '.env')

logger = logging.getLogger("mssql_mcp_server")


def validate_table_name(table_name: str) -> str:
    """Validate and escape table name to prevent SQL injection."""
    # Allow only alphanumeric, underscore, and dot (for schema.table)
    if not re.match(r'^[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)?$', table_name):
        raise ValueError(f"Invalid table name: {table_name}")
    
    # Split schema and table if present
    parts = table_name.split('.')
    if len(parts) == 2:
        # Escape both schema and table name
        return f"[{parts[0]}].[{parts[1]}]"
    else:
        # Just table name
        return f"[{table_name}]"


def get_db_config():
    """Get database configuration from environment variables."""
    # Basic configuration
    server = os.getenv("MSSQL_SERVER", "localhost")
    logger.info(f"MSSQL_SERVER environment variable: {os.getenv('MSSQL_SERVER', 'NOT SET')}")
    logger.info(f"Using server: {server}")
    
    # Handle LocalDB connections (Issue #6)
    # LocalDB format: (localdb)\instancename
    if server.startswith("(localdb)\\"):
        # For LocalDB, pymssql needs special formatting
        # Convert (localdb)\MSSQLLocalDB to localhost\MSSQLLocalDB with dynamic port
        instance_name = server.replace("(localdb)\\", "")
        server = f".\\{instance_name}"
        logger.info(f"Detected LocalDB connection, converted to: {server}")
    
    config = {
        "server": server,
        "user": os.getenv("MSSQL_USER"),
        "password": os.getenv("MSSQL_PASSWORD"),
        "database": os.getenv("MSSQL_DATABASE"),
        "port": os.getenv("MSSQL_PORT", "1433"),  # Default MSSQL port
    }
    
    # Debug logging
    logger.info(f"MSSQL_USER: {config['user']}")
    logger.info(f"MSSQL_DATABASE: {config['database']}")
    logger.info(f"MSSQL_PASSWORD: {'SET' if config['password'] else 'NOT SET'}")    
    # Port support (Issue #8)
    port = os.getenv("MSSQL_PORT")
    if port:
        try:
            config["port"] = int(port)
        except ValueError:
            logger.warning(f"Invalid MSSQL_PORT value: {port}. Using default port.")
    
    # Encryption settings for Azure SQL (Issue #11)
    # Check if we're connecting to Azure SQL
    if config["server"] and ".database.windows.net" in config["server"]:
        config["tds_version"] = "7.4"  # Required for Azure SQL
        # Azure SQL requires encryption
        if os.getenv("MSSQL_ENCRYPT", "true").lower() == "true":
            config["encrypt"] = True
    else:
        # For non-Azure connections, respect the MSSQL_ENCRYPT setting
        encrypt_str = os.getenv("MSSQL_ENCRYPT", "false")
        config["encrypt"] = encrypt_str.lower() == "true"
    
    # Windows Authentication support (Issue #7)
    use_windows_auth = os.getenv("MSSQL_WINDOWS_AUTH", "false").lower() == "true"
    
    if use_windows_auth:
        # For Windows authentication, user and password are not required
        if not config["database"]:
            logger.error("MSSQL_DATABASE is required")
            raise ValueError("Missing required database configuration")
        # Remove user and password for Windows auth
        config.pop("user", None)
        config.pop("password", None)
        logger.info("Using Windows Authentication")
    else:
        # SQL Authentication - user and password are required
        logger.info(f"Checking required vars: user={bool(config['user'])}, password={bool(config['password'])}, database={bool(config['database'])}")
        if not all([config["user"], config["password"], config["database"]]):
            logger.error("Missing required database configuration. Please check environment variables:")
            logger.error("MSSQL_USER, MSSQL_PASSWORD, and MSSQL_DATABASE are required")
            logger.error(f"Current values: USER={config['user']}, DATABASE={config['database']}, PASSWORD={'***' if config['password'] else None}")
            raise ValueError("Missing required database configuration")
    
    return config


def get_command():
    """Get the command to execute SQL queries."""
    return os.getenv("MSSQL_COMMAND", "execute_sql")